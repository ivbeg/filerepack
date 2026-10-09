"""Bounded encoded raster precision checks shared by PDF and image validators."""

import hashlib
from typing import Iterator, Tuple

from .verification import VerificationUnavailable


def _jp2_boxes(data: memoryview) -> Iterator[Tuple[bytes, memoryview]]:
    """Walk bounded JP2 boxes without duplicating their payloads."""
    offset = 0
    count = 0
    while offset < len(data):
        count += 1
        if count > 4096 or len(data) - offset < 8:
            raise VerificationUnavailable('Unsupported JP2 box inventory')
        size = int.from_bytes(data[offset:offset + 4], 'big')
        name = bytes(data[offset + 4:offset + 8])
        header = 8
        if size == 1:
            if len(data) - offset < 16:
                raise ValueError('Truncated JP2 extended box')
            size = int.from_bytes(data[offset + 8:offset + 16], 'big')
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or size > len(data) - offset:
            raise ValueError('Invalid JP2 box extent')
        yield name, data[offset + header:offset + size]
        offset += size


def _jpx_layout(data: bytes) -> tuple:
    """Read unsigned component precision from SIZ, before Pillow can truncate it.

    Layout follows OpenJPEG 2.5.4's opj_j2k_read_siz and JP2 box reader.
    https://github.com/uclouvain/openjpeg/tree/v2.5.4/src/lib/openjp2
    """
    stream = memoryview(data)
    semantics = []
    if data.startswith(b'\x00\x00\x00\x0cjP  \r\n\x87\n'):
        streams = []
        for name, payload in _jp2_boxes(stream):
            if name == b'jp2c':
                streams.append(payload)
            elif name == b'jp2h':
                for field, value in _jp2_boxes(payload):
                    if field in (b'colr', b'pclr', b'cmap', b'cdef', b'bpcc'):
                        semantics.append((field, hashlib.sha256(value).hexdigest()))
        if len(streams) != 1:
            raise VerificationUnavailable('JP2 requires one complete codestream')
        stream = streams[0]
    if len(stream) < 42 or bytes(stream[:4]) != b'\xffO\xffQ':
        raise VerificationUnavailable('Unsupported JPEG 2000 SIZ header')
    length = int.from_bytes(stream[4:6], 'big')
    count = int.from_bytes(stream[40:42], 'big')
    if count not in (1, 3, 4) or length != 38 + count * 3 or 4 + length > len(stream):
        raise VerificationUnavailable('Unsupported JPEG 2000 component inventory')
    components = tuple(tuple(stream[42 + index * 3:45 + index * 3])
                       for index in range(count))
    if any(precision != 7 or dx != 1 or dy != 1 for precision, dx, dy in components):
        raise VerificationUnavailable('JPX requires unsigned 8-bit unsampled components')
    width = int.from_bytes(stream[8:12], 'big') - int.from_bytes(stream[16:20], 'big')
    height = int.from_bytes(stream[12:16], 'big') - int.from_bytes(stream[20:24], 'big')
    if width < 1 or height < 1:
        raise ValueError('Invalid JPEG 2000 dimensions')
    return (width, height), components, tuple(semantics)


def _jpeg_layout(data: bytes) -> tuple:
    if not data.startswith(b'\xff\xd8'):
        raise ValueError('Invalid JPEG signature')
    offset = 2
    for _ in range(4096):
        if offset >= len(data) or data[offset] != 255:
            break
        while offset < len(data) and data[offset] == 255:
            offset += 1
        if offset + 3 > len(data):
            break
        marker = data[offset]
        offset += 1
        size = int.from_bytes(data[offset:offset + 2], 'big')
        if size < 2 or offset + size > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2):
            if size < 8:
                break
            precision, count = data[offset + 2], data[offset + 7]
            if precision != 8 or count not in (1, 3, 4) or size != 8 + 3 * count:
                raise VerificationUnavailable('DCT requires supported 8-bit components')
            height = int.from_bytes(data[offset + 3:offset + 5], 'big')
            width = int.from_bytes(data[offset + 5:offset + 7], 'big')
            return (width, height), count
        if marker in (0xD9, 0xDA):
            break
        offset += size
    raise VerificationUnavailable('Unsupported JPEG frame header')


