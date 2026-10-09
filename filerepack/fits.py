"""Verified FITS tiled GZIP compression without floating-point quantization."""

import hashlib
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import warnings

from . import candidates as tx
from .models import PackResult
from .native import MAX_NATIVE_BYTES
from .transactions import guard_packer


def _backend() -> Any:
    try:
        from astropy.io import fits
        return fits
    except ImportError:
        return None


def _metadata(header: Any) -> Dict[str, List[Tuple[str, str]]]:
    # Compressed-image framing may move keywords. Keep their values/comments
    # and the order of repetitions, including COMMENT and HISTORY records.
    result: Dict[str, List[Tuple[str, str]]] = {}
    for card in header.cards:
        if card.keyword in ('CHECKSUM', 'DATASUM'):
            continue
        result.setdefault(card.keyword, []).append((repr(card.value), card.comment))
    return result


def _raw_hash(path: str, offset: int, length: int) -> str:
    checksum = hashlib.sha256()
    with open(path, 'rb') as source:
        source.seek(offset)
        while length:
            block = source.read(min(length, tx.COPY_BUF))
            if not block:
                raise ValueError('Truncated FITS data segment')
            checksum.update(block)
            length -= len(block)
    return checksum.hexdigest()


def _image_size(header: Any) -> int:
    axes = int(header.get('NAXIS', 0))
    if not 0 <= axes <= 6 or header.get('GROUPS', False):
        raise ValueError('Unsupported FITS dimensions or random groups')
    bitpix = header.get('BITPIX')
    if bitpix not in (8, 16, 32, 64, -32, -64):
        raise ValueError('Unsupported FITS image type')
    size = abs(bitpix) // 8 if axes else 0
    for axis in range(1, axes + 1):
        length = int(header.get('NAXIS' + str(axis), -1))
        if length < 0:
            raise ValueError('Invalid FITS image dimension')
        size *= length
        if size > MAX_NATIVE_BYTES:
            raise ValueError('Decoded FITS image exceeds supported bounds')
    return size


def _image_hash(data: Any) -> Tuple[str, Tuple[int, ...], str]:
    if data is None:
        return '', (), ''
    big_endian = data.astype(data.dtype.newbyteorder('>'), copy=False)
    return (data.dtype.kind + str(data.dtype.itemsize), tuple(data.shape),
            hashlib.sha256(big_endian.tobytes(order='C')).hexdigest())


def _hdu_fingerprint(hdu: Any, path: str, backend: Any) -> Any:
    header = hdu.header.copy()
    if isinstance(hdu, backend.CompImageHDU):
        # Some Astropy versions drop identity scaling and scaling comments from
        # the logical view. The physical cards are the persisted metadata.
        with open(path, 'rb') as source:
            source.seek(hdu.fileinfo()['hdrLoc'])
            physical = backend.Header.fromfile(source)
        for keyword in ('BSCALE', 'BZERO'):
            header.remove(keyword, remove_all=True, ignore_missing=True)
            for card in physical.cards:
                if card.keyword == keyword:
                    header.append(card, end=True)
    if isinstance(hdu, (backend.PrimaryHDU, backend.ImageHDU, backend.CompImageHDU)):
        _image_size(header)
        return 'image', _metadata(header), _image_hash(hdu.data)
    if not isinstance(hdu, (backend.BinTableHDU, backend.TableHDU)):
        raise ValueError('Unsupported FITS extension type')
    info = hdu.fileinfo()
    return 'table', _metadata(header), _raw_hash(path, info['datLoc'], info['datSpan'])


def _check_file(path: str, backend: Any) -> None:
    size = os.path.getsize(path)
    if size > MAX_NATIVE_BYTES or size % 2880:
        raise ValueError('FITS file exceeds bounds or has truncated blocks')
    with open(path, 'rb') as source:
        if source.read(9) != b'SIMPLE  =':
            raise ValueError('Not a standard FITS file')
    with backend.open(path, disable_image_compression=True, memmap=False) as hdus:
        hdus.verify('exception')
        for hdu in hdus:
            if hdu.verify_checksum() == 0 or hdu.verify_datasum() == 0:
                raise ValueError('Invalid FITS checksum')


def _tile_shape(shape: Tuple[int, ...]) -> Tuple[int, ...]:
    if len(shape) == 1:
        return (min(shape[0], 65536),)
    return (1,) * (len(shape) - 2) + (min(shape[-2], 64), shape[-1])


def validate_fits(path: str) -> None:
    backend = _backend()
    if backend is None:
        raise ValueError('FITS validation requires filerepack[fits]')
    _check_file(path, backend)
    with backend.open(path, memmap=False, do_not_scale_image_data=True, uint=False) as hdus:
        size = sum(_image_size(hdu.header) for hdu in hdus if isinstance(
            hdu, (backend.PrimaryHDU, backend.ImageHDU, backend.CompImageHDU),
        ))
        if size > MAX_NATIVE_BYTES:
            raise ValueError('FITS decoded image set exceeds supported bounds')
        for hdu in hdus:
            _hdu_fingerprint(hdu, path, backend)


def _restore_image_metadata(target: Any, source: Any, backend: Any) -> None:
    # Astropy versions can omit duplicate user cards or primary-header comments.
    # Rebuild the source cards using standard tiled-image keyword remapping.
    remapped = {'SIMPLE': 'ZSIMPLE', 'XTENSION': 'ZTENSION', 'BITPIX': 'ZBITPIX',
                'NAXIS': 'ZNAXIS', 'EXTEND': 'ZEXTEND', 'BLOCKED': 'ZBLOCKED',
                'PCOUNT': 'ZPCOUNT', 'GCOUNT': 'ZGCOUNT'}
    cards = []
    for card in source.cards:
        if card.keyword in ('CHECKSUM', 'DATASUM'):
            continue
        keyword = remapped.get(card.keyword, card.keyword)
        if re.fullmatch(r'NAXIS[1-9][0-9]*', keyword):
            keyword = 'Z' + keyword
        cards.append(backend.Card(keyword, card.value, card.comment))
    for keyword in {card.keyword for card in cards}:
        target.remove(keyword, remove_all=True, ignore_missing=True)
    for card in cards:
        target.append(card, end=True)


def _compress_fits(source_path: str, output: str, backend: Any) -> bool:
    with backend.open(source_path, memmap=False, do_not_scale_image_data=True,
                      uint=False) as source:
        source.verify('exception')
        total = sum(_image_size(hdu.header) for hdu in source if isinstance(
            hdu, (backend.PrimaryHDU, backend.ImageHDU, backend.CompImageHDU),
        ))
        if total > MAX_NATIVE_BYTES:
            raise ValueError('FITS decoded image set exceeds supported bounds')
        primary_image = source[0].data is not None
        output_hdus: List[Any] = [backend.PrimaryHDU()] if primary_image else []
        image_pairs = []
        for hdu in source:
            if isinstance(hdu, (backend.PrimaryHDU, backend.ImageHDU, backend.CompImageHDU)):
                if hdu.data is not None and hdu.data.size:
                    header = hdu.header.copy()
                    compressed = backend.CompImageHDU(
                        hdu.data, header=header, compression_type='GZIP_2', quantize_level=0,
                        quantize_method=-1, tile_shape=_tile_shape(tuple(hdu.data.shape)),
                        do_not_scale_image_data=True, uint=False,
                    )
                    image_pairs.append((len(output_hdus), header))
                    output_hdus.append(compressed)
                    continue
            output_hdus.append(hdu.copy())
        if not image_pairs:
            return False
        with backend.HDUList(output_hdus) as candidate:
            candidate.writeto(output, overwrite=True, checksum=True, output_verify='exception')
        # Restore source metadata and remove invented extension names.
        with backend.open(output, mode='update', disable_image_compression=True,
                          memmap=False) as physical:
            for index, header in image_pairs:
                target = physical[index].header
                if 'EXTNAME' not in header:
                    target.remove('EXTNAME', remove_all=True, ignore_missing=True)
                _restore_image_metadata(target, header, backend)
                physical[index].add_checksum()
            physical.flush(output_verify='exception')
        return primary_image


def verify_fits(
    source_path: str, candidate_path: str, *, primary_image: Optional[bool] = None,
) -> bool:
    backend = _backend()
    if backend is None:
        return False
    _check_file(source_path, backend)
    _check_file(candidate_path, backend)
    with backend.open(source_path, memmap=False, do_not_scale_image_data=True,
                      uint=False) as source:
        with backend.open(candidate_path, memmap=False, do_not_scale_image_data=True,
                          uint=False) as candidate:
            for hdus in (source, candidate):
                size = sum(_image_size(hdu.header) for hdu in hdus if isinstance(
                    hdu, (backend.PrimaryHDU, backend.ImageHDU, backend.CompImageHDU),
                ))
                if size > MAX_NATIVE_BYTES:
                    return False
            if primary_image is None:
                primary_image = source[0].data is not None
            offset = int(primary_image)
            if len(candidate) != len(source) + offset:
                return False
            if offset:
                placeholder = candidate[0]
                if placeholder.data is not None or set(placeholder.header) - {
                    'SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND', 'CHECKSUM', 'DATASUM',
                }:
                    return False
            return all(_hdu_fingerprint(left, source_path, backend) ==
                       _hdu_fingerprint(right, candidate_path, backend)
                       for left, right in zip(source, candidate[offset:]))


@guard_packer
def pack_fits(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    backend = _backend()
    if backend is None:
        logging.debug('FITS optimization requires filerepack[fits]')
        return None
    out_temp = tx.make_temp('.fits')
    try:
        from astropy.io.fits.verify import VerifyWarning
        with warnings.catch_warnings():
            warnings.simplefilter('error', VerifyWarning)
            _check_file(filepath, backend)
            primary_image = _compress_fits(filepath, out_temp, backend)
            if not os.path.getsize(out_temp) or not verify_fits(
                filepath, out_temp, primary_image=primary_image,
            ):
                return None
        return tx.commit_output(
            out_temp, filepath, os.path.getsize(filepath), verify='fits',
            **tx.commit_kwargs(**commit),
        )
    except Exception as error:
        logging.debug('FITS optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)
