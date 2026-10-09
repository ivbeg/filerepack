# -*- coding: utf-8 -*-

"""Bounded, seek-based Part-10 inspection; pixels are not decoded here."""

import os
import struct
from dataclasses import dataclass
from typing import Any, BinaryIO, FrozenSet, Optional, Tuple

DICM_OFFSET = 128
DICM_MAGIC = b'DICM'
TS_IMPLICIT_VR_LE = '1.2.840.10008.1.2'
TS_EXPLICIT_VR_LE = '1.2.840.10008.1.2.1'
TS_EXPLICIT_VR_BE = '1.2.840.10008.1.2.2'
TS_RLE_LOSSLESS = '1.2.840.10008.1.2.5'
TS_JPEG_LS_LOSSLESS = '1.2.840.10008.1.2.4.80'
PACKABLE_TRANSFER_SYNTAXES: FrozenSet[str] = frozenset({
    TS_IMPLICIT_VR_LE, TS_EXPLICIT_VR_LE, TS_EXPLICIT_VR_BE, TS_RLE_LOSSLESS,
})
_TAG_TRANSFER_SYNTAX = (0x0002, 0x0010)
_TAG_PIXEL_DATA = (0x7FE0, 0x0010)
_TAG_SIGNATURES = (0xFFFA, 0xFFFA)
_ITEM = (0xFFFE, 0xE000)
_ITEM_DELIM = (0xFFFE, 0xE00D)
_SEQ_DELIM = (0xFFFE, 0xE0DD)
_UNDEFINED = 0xFFFFFFFF
_MAX_ELEMENTS = 100000
_MAX_DEPTH = 64
_MAX_META_BYTES = 4 * 1024 * 1024
_LONG_VR = frozenset('OB OD OF OL OV OW SQ SV UC UN UR UT UV'.split())
_VALID_VR = _LONG_VR | frozenset(
    'AE AS AT CS DA DS DT FD FL IS LO LT PN SH SL SS ST TM UI UL US'.split()
)


@dataclass(frozen=True)
class DicomInspection:
    eligible: bool
    reason: str
    transfer_syntax: Optional[str] = None


def has_dicm_magic(path: str) -> bool:
    try:
        with open(path, 'rb') as fh:
            fh.seek(DICM_OFFSET)
            return fh.read(4) == DICM_MAGIC
    except OSError:
        return False


def inspect_dicom(path: str, *, candidate: bool = False) -> DicomInspection:
    """Inspect every element/item under one shared element and nesting budget."""
    try:
        with open(path, 'rb') as fh:
            size = os.fstat(fh.fileno()).st_size
            fh.seek(DICM_OFFSET)
            if fh.read(4) != DICM_MAGIC:
                raise ValueError('missing DICM preamble')
            scanner = _Scanner(fh, size)
            syntax = scanner.meta()
            allowed = {TS_JPEG_LS_LOSSLESS} if candidate else PACKABLE_TRANSFER_SYNTAXES
            if syntax not in allowed:
                raise ValueError('unsupported transfer syntax: ' + syntax)
            scanner.configure(syntax)
            scanner.dataset(size, 0)
            if not scanner.has_pixel:
                raise ValueError('missing Pixel Data')
            return DicomInspection(True, 'eligible', syntax)
    except (OSError, ValueError, EOFError, struct.error, UnicodeError) as exc:
        return DicomInspection(False, str(exc))


def dicom_is_packable(path: str) -> bool:
    return inspect_dicom(path).eligible


class _Scanner:
    def __init__(self, fh: BinaryIO, size: int):
        self.fh = fh
        self.size = size
        self.explicit = True
        self.endian = '<'
        self.encapsulated = False
        self.count = 0
        self.has_pixel = False
        self.dictionary: Any = None

    def configure(self, syntax: str) -> None:
        self.explicit = syntax != TS_IMPLICIT_VR_LE
        self.endian = '>' if syntax == TS_EXPLICIT_VR_BE else '<'
        self.encapsulated = syntax in (TS_RLE_LOSSLESS, TS_JPEG_LS_LOSSLESS)
        if not self.explicit:
            try:
                from pydicom.datadict import dictionary_VR
            except ImportError as exc:
                raise ValueError(
                    'implicit VR inspection unavailable: install filerepack[dicom]'
                ) from exc
            self.dictionary = dictionary_VR

    def read(self, length: int, end: int) -> bytes:
        if self.fh.tell() + length > end:
            raise ValueError('truncated value or header')
        value = self.fh.read(length)
        if len(value) != length:
            raise ValueError('truncated read')
        return value

    def header(self, end: int) -> Tuple[Tuple[int, int], Optional[str], int]:
        self.count += 1
        if self.count > _MAX_ELEMENTS:
            raise ValueError('DICOM element limit exceeded')
        tag = struct.unpack(self.endian + 'HH', self.read(4, end))
        vr = None
        if tag[0] == 0xFFFE or not self.explicit:
            length = struct.unpack(self.endian + 'I', self.read(4, end))[0]
            if self.dictionary and tag[0] != 0xFFFE:
                try:
                    vr = self.dictionary(tag[0] * 65536 + tag[1])
                except KeyError:
                    pass  # Unknown private values remain opaque, except item-shaped sequences.
        else:
            vr = self.read(2, end).decode('ascii')
            if vr not in _VALID_VR:
                raise ValueError('invalid value representation')
            if vr in _LONG_VR:
                if self.read(2, end) != b'\0\0':
                    raise ValueError('invalid reserved header bytes')
                length = struct.unpack(self.endian + 'I', self.read(4, end))[0]
            else:
                length = struct.unpack(self.endian + 'H', self.read(2, end))[0]
        if length != _UNDEFINED and (length % 2 or self.fh.tell() + length > end):
            raise ValueError('odd or truncated value length')
        return tag, vr, length

    def meta(self) -> str:
        expected_end = None
        syntax = None
        previous = (-1, -1)
        while self.fh.tell() < self.size:
            start = self.fh.tell()
            group = struct.unpack('<H', self.read(2, self.size))[0]
            self.fh.seek(start)
            if group != 2:
                break
            tag, vr, length = self.header(self.size)
            if tag <= previous or length == _UNDEFINED:
                raise ValueError('invalid File Meta ordering/length')
            previous = tag
            if self.fh.tell() + length - 132 > _MAX_META_BYTES:
                raise ValueError('File Meta byte limit exceeded')
            if tag == (2, 0):
                if vr != 'UL' or length != 4:
                    raise ValueError('invalid File Meta group length')
                expected_end = self.fh.tell() + 4 + struct.unpack('<I', self.read(4, self.size))[0]
            elif tag == _TAG_TRANSFER_SYNTAX:
                if vr != 'UI' or not 0 < length <= 64:
                    raise ValueError('invalid Transfer Syntax UID')
                syntax = self.read(length, self.size).rstrip(b'\0 ').decode('ascii')
            else:
                self.fh.seek(length, os.SEEK_CUR)
        if expected_end is None or expected_end != self.fh.tell():
            raise ValueError('invalid File Meta boundary')
        if syntax is None:
            raise ValueError('missing Transfer Syntax UID')
        return syntax

    def dataset(self, end: int, depth: int, *, undefined: bool = False) -> None:
        if depth > _MAX_DEPTH:
            raise ValueError('DICOM nesting limit exceeded')
        previous = (-1, -1)
        while self.fh.tell() < end:
            tag, vr, length = self.header(end)
            if tag == _ITEM_DELIM and undefined and length == 0:
                return
            if tag <= previous or tag[0] in (0, 2, 6, 0xFFFE, 0xFFFF):
                raise ValueError('invalid dataset tag ordering or delimiter')
            previous = tag
            if tag == _TAG_SIGNATURES:
                raise ValueError('Digital Signatures Sequence present')
            if tag == _TAG_PIXEL_DATA:
                if vr not in (None, 'OB', 'OW', 'OB or OW'):
                    raise ValueError('invalid Pixel Data VR')
                self.pixels(length, end, depth)
            elif self.is_sequence(vr, length, end):
                self.sequence(length, end, depth + 1)
            elif length == _UNDEFINED:
                raise ValueError('unsupported undefined-length value')
            else:
                self.fh.seek(length, os.SEEK_CUR)
        if undefined:
            raise ValueError('missing Item Delimitation')

    def is_sequence(self, vr: Optional[str], length: int, end: int) -> bool:
        if vr == 'SQ':
            return True
        if vr == 'UN' and length == _UNDEFINED:
            raise ValueError('undefined UN sequence encoding is unsupported')
        if vr == 'UN' and length >= 8:
            start = self.fh.tell()
            tag = struct.unpack(self.endian + 'HH', self.read(4, end))
            self.fh.seek(start)
            if tag == _ITEM:
                raise ValueError('opaque UN sequence encoding is unsupported')
        if not self.explicit and vr is None:
            if length == _UNDEFINED:
                return True
            if length >= 8:
                start = self.fh.tell()
                tag = struct.unpack(self.endian + 'HH', self.read(4, end))
                self.fh.seek(start)
                return tag == _ITEM
        return False

    def sequence(self, length: int, parent_end: int, depth: int) -> None:
        if depth > _MAX_DEPTH:
            raise ValueError('DICOM nesting limit exceeded')
        end = parent_end if length == _UNDEFINED else self.fh.tell() + length
        while self.fh.tell() < end:
            tag, _, item_length = self.header(end)
            if tag == _SEQ_DELIM and length == _UNDEFINED and item_length == 0:
                return
            if tag != _ITEM:
                raise ValueError('invalid sequence item or delimiter')
            item_end = end if item_length == _UNDEFINED else self.fh.tell() + item_length
            self.dataset(item_end, depth, undefined=item_length == _UNDEFINED)
        if length == _UNDEFINED:
            raise ValueError('missing Sequence Delimitation')

    def pixels(self, length: int, end: int, depth: int) -> None:
        if depth == 0:
            self.has_pixel = True
        if self.encapsulated:
            if length != _UNDEFINED:
                raise ValueError('compressed Pixel Data must be encapsulated')
            self.fragments(end)
        else:
            if length in (0, _UNDEFINED):
                raise ValueError('invalid native Pixel Data length')
            self.fh.seek(length, os.SEEK_CUR)

    def fragments(self, end: int) -> None:
        count = 0
        while self.fh.tell() < end:
            tag, _, length = self.header(end)
            if tag == _SEQ_DELIM and length == 0 and count >= 2:
                return
            if tag != _ITEM or length == _UNDEFINED:
                raise ValueError('invalid encapsulated pixel fragment')
            if (count == 0 and length % 4) or (count > 0 and length == 0):
                raise ValueError('invalid offset table or empty pixel fragment')
            count += 1
            self.fh.seek(length, os.SEEK_CUR)
        raise ValueError('truncated encapsulated Pixel Data')
