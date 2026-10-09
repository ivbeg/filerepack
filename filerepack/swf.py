"""Lossless FWS/CWS compression with bounded movie/tag framing checks."""

import logging
import struct
import zlib
from typing import Any, Optional, Tuple

from . import candidates as tx
from .models import PackResult
from .native import MAX_NATIVE_BYTES, inflate_exact, read_native
from .transactions import guard_packer


def decode_swf(data: bytes) -> Tuple[bytes, bytes]:
    if len(data) < 9 or data[:3] not in (b'FWS', b'CWS'):
        raise ValueError('Unsupported SWF signature (only FWS/CWS)')
    version = data[3]
    length = struct.unpack_from('<I', data, 4)[0]
    if not 1 <= version <= 50 or not 9 <= length <= MAX_NATIVE_BYTES:
        raise ValueError('Unsupported SWF version or size')
    if data[:3] == b'CWS':
        if version < 6:
            raise ValueError('Compressed SWF requires version 6 or newer')
        body = inflate_exact(data[8:], length - 8)
    else:
        if len(data) != length:
            raise ValueError('SWF declared size differs from payload')
        body = data[8:]
    bits = body[0] >> 3
    if not bits:
        raise ValueError('Invalid SWF frame rectangle')
    offset = (5 + 4 * bits + 7) // 8 + 4  # RECT, frame rate, frame count.
    if offset > len(body):
        raise ValueError('Truncated SWF frame header')
    while offset < len(body):
        if offset + 2 > len(body):
            raise ValueError('Truncated SWF tag header')
        record = struct.unpack_from('<H', body, offset)[0]
        offset += 2
        code, size = record >> 6, record & 63
        if size == 63:
            if offset + 4 > len(body):
                raise ValueError('Truncated SWF long tag header')
            size = struct.unpack_from('<I', body, offset)[0]
            offset += 4
        if offset + size > len(body):
            raise ValueError('Truncated SWF tag payload')
        offset += size
        if code == 0:
            if size or offset != len(body):
                raise ValueError('Invalid SWF End tag or trailing data')
            return data[3:8], body
    raise ValueError('Missing SWF End tag')


@guard_packer
def pack_swf(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    temporary = tx.make_temp('.swf')
    try:
        original = read_native(filepath)
        header, body = decode_swf(original)
        if header[0] < 6:
            return None
        with open(temporary, 'wb') as target:
            target.write(b'CWS' + header + zlib.compress(body, 9))
        return tx.commit_output(
            temporary, filepath, len(original), verify='swf', lossless=True,
            **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError, struct.error, zlib.error) as error:
        logging.debug('SWF optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(temporary)
