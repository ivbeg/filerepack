# -*- coding: utf-8 -*-

"""Minimal DICOM reader used to decide whether a file is safe to recompress."""

import os
import struct
from typing import BinaryIO, FrozenSet, NamedTuple, Optional, Tuple

DICM_OFFSET = 128
DICM_MAGIC = b'DICM'

TS_IMPLICIT_VR_LE = '1.2.840.10008.1.2'
TS_EXPLICIT_VR_LE = '1.2.840.10008.1.2.1'
TS_EXPLICIT_VR_BE = '1.2.840.10008.1.2.2'
TS_RLE_LOSSLESS = '1.2.840.10008.1.2.5'

PACKABLE_TRANSFER_SYNTAXES: FrozenSet[str] = frozenset({
    TS_IMPLICIT_VR_LE,
    TS_EXPLICIT_VR_LE,
    TS_EXPLICIT_VR_BE,
    TS_RLE_LOSSLESS,
})

_TAG_META_GROUP_LENGTH = (0x0002, 0x0000)
_TAG_TRANSFER_SYNTAX = (0x0002, 0x0010)
_TAG_PIXEL_DATA = (0x7FE0, 0x0010)
_TAG_SIGNATURES = (0xFFFA, 0xFFFA)

_ITEM = (0xFFFE, 0xE000)
_ITEM_DELIM = (0xFFFE, 0xE00D)
_SEQ_DELIM = (0xFFFE, 0xE0DD)
_UNDEFINED = 0xFFFFFFFF
_MAX_ELEMENTS = 100000

_LONG_VR = frozenset({
    'OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'SQ', 'SV', 'UC', 'UN', 'UR', 'UT', 'UV',
})


class _Hdr(NamedTuple):
    tag: Tuple[int, int]
    vr: Optional[str]
    length: int
    start: int


def has_dicm_magic(path: str) -> bool:
    """True when bytes 128–131 are DICM."""
    try:
        if os.path.getsize(path) < DICM_OFFSET + 4:
            return False
        with open(path, 'rb') as fh:
            fh.seek(DICM_OFFSET)
            return fh.read(4) == DICM_MAGIC
    except OSError:
        return False


def dicom_is_packable(path: str) -> bool:
    """True when the file is an uncompressed or RLE image DICOM we may rewrite."""
    try:
        return _inspect_packable(path)
    except (OSError, struct.error, ValueError, EOFError, UnicodeDecodeError):
        return False


def _inspect_packable(path: str) -> bool:
    with open(path, 'rb') as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        if size < DICM_OFFSET + 4:
            return False
        fh.seek(DICM_OFFSET)
        if fh.read(4) != DICM_MAGIC:
            return False
        ts = _read_transfer_syntax(fh, size)
        if ts is None or ts not in PACKABLE_TRANSFER_SYNTAXES:
            return False
        explicit = ts != TS_IMPLICIT_VR_LE
        endian = '>' if ts == TS_EXPLICIT_VR_BE else '<'
        return _dataset_ok(fh, size, explicit, endian)


def _read_transfer_syntax(fh: BinaryIO, size: int) -> Optional[str]:
    ts: Optional[str] = None
    meta_end: Optional[int] = None
    for _ in range(_MAX_ELEMENTS):
        start = fh.tell()
        if meta_end is not None and start >= meta_end:
            break
        hdr = _read_header(fh, size, True, '<')
        if hdr is None:
            break
        if hdr.tag[0] != 0x0002:
            fh.seek(hdr.start)
            break
        if hdr.length == _UNDEFINED:
            raise ValueError('undefined length in file meta')
        value = _read_exact(fh, hdr.length, size)
        if hdr.tag == _TAG_META_GROUP_LENGTH and hdr.length == 4:
            meta_end = fh.tell() + struct.unpack('<I', value)[0]
        elif hdr.tag == _TAG_TRANSFER_SYNTAX:
            ts = value.rstrip(b' \x00').decode('ascii')
    return ts


def _dataset_ok(fh: BinaryIO, size: int, explicit: bool, endian: str) -> bool:
    has_pixel = False
    for _ in range(_MAX_ELEMENTS):
        hdr = _read_header(fh, size, explicit, endian)
        if hdr is None:
            break
        if hdr.tag == _TAG_SIGNATURES:
            return False
        if hdr.tag == _TAG_PIXEL_DATA:
            has_pixel = True
            break
        _skip_value(fh, size, hdr.length, explicit, endian)
    return has_pixel


def _read_header(
    fh: BinaryIO, size: int, explicit: bool, endian: str,
) -> Optional[_Hdr]:
    start = fh.tell()
    if start + 8 > size:
        return None
    tag_bytes = fh.read(4)
    if len(tag_bytes) < 4:
        return None
    group, element = struct.unpack(endian + 'HH', tag_bytes)
    tag = (group, element)
    if tag in (_ITEM, _ITEM_DELIM, _SEQ_DELIM):
        length = struct.unpack(endian + 'I', _read_exact(fh, 4, size))[0]
        return _Hdr(tag, None, length, start)
    if explicit:
        vr = _read_exact(fh, 2, size).decode('ascii')
        if vr in _LONG_VR:
            _read_exact(fh, 2, size)
            length = struct.unpack(endian + 'I', _read_exact(fh, 4, size))[0]
        else:
            length = struct.unpack(endian + 'H', _read_exact(fh, 2, size))[0]
        return _Hdr(tag, vr, length, start)
    length = struct.unpack(endian + 'I', _read_exact(fh, 4, size))[0]
    return _Hdr(tag, None, length, start)


def _skip_value(
    fh: BinaryIO, size: int, length: int, explicit: bool, endian: str,
) -> None:
    if length != _UNDEFINED:
        end = fh.tell() + length
        if end > size:
            raise ValueError('truncated value')
        fh.seek(end)
        return
    for _ in range(_MAX_ELEMENTS):
        hdr = _read_header(fh, size, explicit, endian)
        if hdr is None:
            raise ValueError('truncated undefined-length value')
        if hdr.tag == _SEQ_DELIM:
            return
        if hdr.tag == _ITEM:
            if hdr.length == _UNDEFINED:
                _skip_until(fh, size, explicit, endian, _ITEM_DELIM)
            else:
                _skip_value(fh, size, hdr.length, explicit, endian)
            continue
        _skip_value(fh, size, hdr.length, explicit, endian)
    raise ValueError('too many nested items')


def _skip_until(
    fh: BinaryIO, size: int, explicit: bool, endian: str,
    stop: Tuple[int, int],
) -> None:
    for _ in range(_MAX_ELEMENTS):
        hdr = _read_header(fh, size, explicit, endian)
        if hdr is None:
            raise ValueError('truncated sequence item')
        if hdr.tag == stop:
            return
        _skip_value(fh, size, hdr.length, explicit, endian)
    raise ValueError('too many nested elements')


def _read_exact(fh: BinaryIO, n: int, size: int) -> bytes:
    if fh.tell() + n > size:
        raise ValueError('truncated read')
    data = fh.read(n)
    if len(data) < n:
        raise ValueError('truncated read')
    return data
