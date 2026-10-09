"""Lossless compression of attached NRRD arrays with unchanged header metadata."""

import bz2
import gzip
import logging
import re
import zlib
from typing import Any, Dict, Optional, Tuple

from . import candidates as tx
from .models import PackResult
from .native import MAX_NATIVE_BYTES, inflate_exact, read_native
from .transactions import guard_packer

_TYPE_SIZES = {
    **dict.fromkeys(('signed char', 'int8', 'int8_t', 'uchar', 'unsigned char',
                     'uint8', 'uint8_t'), 1),
    **dict.fromkeys(('short', 'short int', 'signed short', 'signed short int', 'int16',
                     'int16_t', 'ushort', 'unsigned short', 'unsigned short int',
                     'uint16', 'uint16_t'), 2),
    **dict.fromkeys(('int', 'signed int', 'int32', 'int32_t', 'uint', 'unsigned int',
                     'uint32', 'uint32_t', 'float'), 4),
    **dict.fromkeys(('longlong', 'long long', 'long long int', 'signed long long',
                     'signed long long int', 'int64', 'int64_t', 'ulonglong',
                     'unsigned long long', 'unsigned long long int', 'uint64',
                     'uint64_t', 'double'), 8),
}
_ENCODING = re.compile(rb'([^:]+:[ \t]*)([^ \t\r\n]+)([ \t]*(?:\r?\n)?)\Z')


def _fields(lines: list) -> Tuple[Dict[str, str], int]:
    fields: Dict[str, str] = {}
    encoding_line = -1
    for index, line in enumerate(lines[1:], 1):
        if not line.strip() or line.startswith(b'#') or b':=' in line:
            continue
        key, separator, value = line.partition(b':')
        if not separator:
            raise ValueError('Malformed NRRD header field')
        name = key.decode('ascii').strip().lower()
        if name in fields:
            raise ValueError('Duplicate NRRD field')
        fields[name] = value.decode('ascii').strip()
        if name == 'encoding':
            encoding_line = index
    if any(key in fields for key in ('data file', 'datafile')):
        raise ValueError('Detached NRRD data is unsupported')
    for field_name in ('line skip', 'lineskip', 'byte skip', 'byteskip'):
        if int(fields.get(field_name, '0')) != 0:
            raise ValueError('NRRD data offsets are unsupported')
    return fields, encoding_line


def _array_size(fields: Dict[str, str]) -> int:
    dimension = int(fields.get('dimension', '0'))
    sizes = [int(value) for value in fields.get('sizes', '').split()]
    size = _TYPE_SIZES.get(fields.get('type', '').lower(), 0)
    if fields.get('type') == 'block':
        size = int(fields.get('block size', fields.get('blocksize', '0')))
    if size <= 0 or not 1 <= dimension <= 16 or len(sizes) != dimension or min(sizes) <= 0:
        raise ValueError('Unsupported NRRD type or dimensions')
    if size > 1 and fields.get('type') != 'block' and fields.get('endian') not in ('little', 'big'):
        raise ValueError('Missing or unsupported NRRD endian')
    expected = size
    for axis in sizes:
        expected *= axis
        if expected > MAX_NATIVE_BYTES:
            raise ValueError('NRRD array exceeds supported bounds')
    return expected


def _header(data: bytes) -> Tuple[bytes, bytes, int, int, str]:
    boundary = re.search(rb'\r?\n\r?\n', data)
    if boundary is None:
        raise ValueError('Missing attached NRRD header boundary')
    header = data[:boundary.end()]
    if len(header) > 1024 * 1024:
        raise ValueError('NRRD header exceeds supported bounds')
    lines = header.splitlines(keepends=True)
    if lines[0].rstrip(b'\r\n') not in (b'NRRD0001', b'NRRD0002', b'NRRD0003',
                                       b'NRRD0004', b'NRRD0005'):
        raise ValueError('Unsupported NRRD version')
    fields, encoding_line = _fields(lines)
    expected = _array_size(fields)
    encoding = fields.get('encoding', '')
    if encoding not in ('raw', 'gzip', 'gz', 'bzip2', 'bz2') or encoding_line < 0:
        raise ValueError('Unsupported NRRD encoding')
    if _ENCODING.fullmatch(lines[encoding_line]) is None:
        raise ValueError('Unsupported NRRD encoding field syntax')
    return header, data[boundary.end():], expected, encoding_line, encoding


def _array(payload: bytes, size: int, encoding: str) -> bytes:
    if encoding in ('gzip', 'gz'):
        return inflate_exact(payload, size, wbits=31)
    if encoding in ('bzip2', 'bz2'):
        decoder = bz2.BZ2Decompressor()
        raw = decoder.decompress(payload, max_length=size + 1)
        if len(raw) != size or not decoder.eof or decoder.unused_data:
            raise ValueError('Invalid NRRD bzip2 array')
        return raw
    if len(payload) != size:
        raise ValueError('NRRD array does not match its declared dimensions')
    return payload


def decode_nrrd(data: bytes) -> Tuple[bytes, bytes]:
    header, payload, size, index, encoding = _header(data)
    lines = header.splitlines(keepends=True)
    lines[index] = _ENCODING.sub(lambda match: match[1] + b'raw' + match[3], lines[index])
    return b''.join(lines), _array(payload, size, encoding)


def _compress_nrrd(data: bytes) -> bytes:
    header, payload, size, index, encoding = _header(data)
    raw = _array(payload, size, encoding)
    if encoding in ('bzip2', 'bz2'):
        compressed = bz2.compress(raw, compresslevel=9)
    else:
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        if encoding == 'raw':
            lines = header.splitlines(keepends=True)
            lines[index] = _ENCODING.sub(lambda match: match[1] + b'gzip' + match[3], lines[index])
            header = b''.join(lines)
    return header + compressed


@guard_packer
def pack_nrrd(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    out_temp = tx.make_temp('.nrrd')
    try:
        original = read_native(filepath)
        expected = decode_nrrd(original)
        with open(out_temp, 'wb') as target:
            target.write(_compress_nrrd(original))
        if decode_nrrd(read_native(out_temp)) != expected:
            return None
        return tx.commit_output(
            out_temp, filepath, len(original), verify='nrrd', **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError, EOFError, zlib.error) as error:
        logging.debug('NRRD optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)
