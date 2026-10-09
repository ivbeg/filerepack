"""Optional semantic and decoded-pixel verification for lossless DICOM output."""

import logging
import warnings
from itertools import zip_longest
from typing import Any, Iterator, Optional

from .dicom import DicomInspection, TS_JPEG_LS_LOSSLESS, inspect_dicom

_LOG = logging.getLogger(__name__)
# Encoding bookkeeping only. All other dataset attributes, including private data,
# identity, frame interpretation and sequences, must remain equivalent.
_ENCODING_TAGS = {0x7FE00010, 0x7FE00001, 0x7FE00002, 0xFFFCFFFC}
_META_ENCODING_TAGS = {0x00020000, 0x00020001, 0x00020010, 0x00020012, 0x00020013}


def _dependencies() -> Any:
    import numpy
    import pydicom
    from pydicom.pixel_data_handlers import jpeg_ls_handler
    if not jpeg_ls_handler.is_available():
        raise ImportError('JPEG-LS decoder unavailable')
    return numpy, pydicom


def _read_dataset(pydicom: Any, path: str) -> Any:
    # Keep deferred pixel/large values on disk until required; read past Pixel Data.
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        return pydicom.dcmread(path, force=False, defer_size=1024)


def _image_check(ds: Any) -> None:
    for name in ('Rows', 'Columns', 'SamplesPerPixel', 'BitsAllocated', 'BitsStored',
                 'HighBit', 'PixelRepresentation', 'PhotometricInterpretation'):
        if name not in ds:
            raise ValueError('missing image attribute: ' + name)
    frames = int(ds.get('NumberOfFrames', 1))
    if frames < 1 or int(ds.Rows) < 1 or int(ds.Columns) < 1:
        raise ValueError('invalid frame count or dimensions')
    if (int(ds.SamplesPerPixel) not in (1, 3) or int(ds.BitsAllocated) not in (8, 16)
            or not 1 <= int(ds.BitsStored) <= int(ds.BitsAllocated)
            or int(ds.HighBit) != int(ds.BitsStored) - 1
            or int(ds.PixelRepresentation) not in (0, 1)):
        raise ValueError('unsupported image interpretation')
    if not ds.file_meta.TransferSyntaxUID.is_compressed:
        expected = frames * int(ds.Rows) * int(ds.Columns) * int(ds.SamplesPerPixel)
        expected *= int(ds.BitsAllocated) // 8
        # Access the raw element length without loading its pixel value.
        raw = ds._dict[0x7FE00010]
        length = raw.length if hasattr(raw, 'length') else len(raw.value)
        if length != expected + expected % 2:
            raise ValueError('Pixel Data length does not match image attributes')


def verification_ready(path: str) -> DicomInspection:
    """Require semantic/parser/decoder support before invoking an encoder."""
    try:
        _, pydicom = _dependencies()
        ds = _read_dataset(pydicom, path)
        _image_check(ds)
        return DicomInspection(True, 'verification available')
    except ImportError:
        return DicomInspection(False, 'verification unavailable: install filerepack[dicom]')
    except Exception as exc:
        return DicomInspection(False, 'invalid image attributes (' + type(exc).__name__ + ')')


def _same_dataset(left: Any, right: Any, *, exclude: Optional[set] = None) -> bool:
    excluded = exclude or set()
    left_tags = {tag for tag in left.keys() if tag.element != 0 and int(tag) not in excluded}
    right_tags = {tag for tag in right.keys() if tag.element != 0 and int(tag) not in excluded}
    if left_tags != right_tags:
        return False
    for tag in left_tags:
        a, b = left[tag], right[tag]
        if a.VR != b.VR:
            return False
        if a.VR == 'SQ':
            if len(a.value) != len(b.value):
                return False
            if not all(_same_dataset(x, y) for x, y in zip(a.value, b.value)):
                return False
        elif a.value != b.value:
            return False
        elif a.VR in ('DS', 'IS') and str(a.value) != str(b.value):
            # pydicom's numeric wrappers can compare rounded floats as equal.
            return False
    return True


def _frames(pydicom: Any, path: str, ds: Any) -> Iterator[Any]:
    if hasattr(pydicom, 'pixels'):
        yield from pydicom.pixels.iter_pixels(path, raw=True)
    else:  # pydicom 2.4 supports the package's Python 3.9 floor.
        pixels = ds.pixel_array
        if int(ds.get('NumberOfFrames', 1)) == 1:
            yield pixels
        else:
            yield from pixels


def verify_dicom(path: str, source_path: Optional[str] = None) -> bool:
    """Require JPEG-LS structure and source equivalence; magic alone is insufficient."""
    if source_path is None:
        _LOG.warning('DICOM verification requires a source for pixel/attribute comparison')
        return False
    for filename, candidate in ((source_path, False), (path, True)):
        inspection = inspect_dicom(filename, candidate=candidate)
        if not inspection.eligible:
            _LOG.warning('DICOM verification rejected: %s', inspection.reason)
            return False
    try:
        numpy, pydicom = _dependencies()
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            source, output = (_read_dataset(pydicom, p) for p in (source_path, path))
            _image_check(source)
            _image_check(output)
            if str(output.file_meta.TransferSyntaxUID) != TS_JPEG_LS_LOSSLESS:
                return False
            if not _same_dataset(source, output, exclude=_ENCODING_TAGS):
                _LOG.warning('DICOM verification rejected changed dataset attributes')
                return False
            meta_excluded = set(_META_ENCODING_TAGS)
            if 0x00020016 not in source.file_meta:
                meta_excluded.add(0x00020016)  # Encoder may add its application title.
            if not _same_dataset(source.file_meta, output.file_meta, exclude=meta_excluded):
                _LOG.warning('DICOM verification rejected changed File Meta attributes')
                return False
            if source.preamble != output.preamble:
                return False
            frames = 0
            missing: Any = object()
            for a, b in zip_longest(_frames(pydicom, source_path, source),
                                   _frames(pydicom, path, output), fillvalue=missing):
                if a is missing or b is missing or a.shape != b.shape:
                    return False
                if a.dtype.kind != b.dtype.kind or not numpy.array_equal(a, b):
                    _LOG.warning('DICOM verification rejected changed decoded pixels')
                    return False
                frames += 1
            return frames == int(source.get('NumberOfFrames', 1))
    except ImportError:
        _LOG.warning('DICOM verification unavailable: install filerepack[dicom]')
    except Exception as exc:
        _LOG.warning('DICOM verification failed (%s)', type(exc).__name__)
    return False
