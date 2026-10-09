"""Recompress Aseprite cels without changing frames, layers or unknown chunks."""

import hashlib
import logging
import struct
import zlib
from typing import Any, List, Optional, Tuple

from . import candidates as tx
from .models import PackResult
from .native import MAX_NATIVE_BYTES, inflate_exact, read_native
from .transactions import guard_packer


def _cel(chunk: bytes, depth: int, frames: int) -> Tuple[bytes, bytes, int]:
    if len(chunk) < 22:
        raise ValueError('Truncated Aseprite cel')
    kind = struct.unpack_from('<H', chunk, 13)[0]
    if kind == 1:
        if len(chunk) != 24 or struct.unpack_from('<H', chunk, 22)[0] >= frames:
            raise ValueError('Invalid linked Aseprite cel')
        return chunk, chunk[4:], 0
    if kind not in (0, 2, 3):
        raise ValueError('Unsupported Aseprite cel type')
    if len(chunk) < (26 if kind in (0, 2) else 54):
        raise ValueError('Truncated compressed Aseprite cel')
    width, height = struct.unpack_from('<HH', chunk, 22)
    if kind in (0, 2):
        offset, bits = 26, depth
    else:
        offset, bits = 54, struct.unpack_from('<H', chunk, 26)[0]
        if bits not in (8, 16, 32):
            raise ValueError('Unsupported Aseprite tile depth')
    expected = width * height * (bits // 8)
    if kind == 0:
        if len(chunk) != expected + offset:
            raise ValueError('Invalid raw Aseprite cel size')
        return chunk, chunk[4:], expected
    raw = inflate_exact(chunk[offset:], expected)
    normalized = chunk[4:offset] + hashlib.sha256(raw).digest()
    compressed = zlib.compress(raw, 9)
    if len(compressed) < len(chunk) - offset:
        body = chunk[4:offset] + compressed
        chunk = struct.pack('<I', len(body) + 4) + body
    return chunk, normalized, expected


def rewrite_aseprite(data: bytes) -> Tuple[bytes, bytes]:
    if len(data) < 128:
        raise ValueError('Truncated Aseprite header')
    size, magic, frames, width, height, depth = struct.unpack_from('<I5H', data)
    if (size != len(data) or magic != 0xA5E0 or not frames or not width or not height
            or depth not in (8, 16, 32)):
        raise ValueError('Invalid Aseprite header')
    fingerprint = hashlib.sha256(data[4:128])
    output: List[bytes] = []
    position = 128
    decoded = 0
    for _ in range(frames):
        if position + 16 > len(data):
            raise ValueError('Truncated Aseprite frame')
        header = data[position:position + 16]
        length, magic, old_count = struct.unpack_from('<IHH', header)
        count = struct.unpack_from('<I', header, 12)[0] or old_count
        end = position + length
        if magic != 0xF1FA or length < 16 or end > len(data):
            raise ValueError('Invalid Aseprite frame length')
        fingerprint.update(header[4:])
        cursor = position + 16
        chunks: List[bytes] = []
        for _chunk in range(count):
            if cursor + 6 > end:
                raise ValueError('Truncated Aseprite chunk')
            chunk_length, kind = struct.unpack_from('<IH', data, cursor)
            if chunk_length < 6 or cursor + chunk_length > end:
                raise ValueError('Invalid Aseprite chunk length')
            chunk = data[cursor:cursor + chunk_length]
            if kind == 0x2005:
                rewritten, normalized, expanded = _cel(chunk, depth, frames)
                decoded += expanded
                if decoded > MAX_NATIVE_BYTES:
                    raise ValueError('Aseprite decoded cels exceed supported bounds')
            else:
                rewritten, normalized = chunk, chunk[4:]
            fingerprint.update(len(normalized).to_bytes(8, 'little') + normalized)
            chunks.append(rewritten)
            cursor += chunk_length
        if cursor != end:
            raise ValueError('Aseprite frame count does not match its length')
        body = b''.join(chunks)
        output.append(struct.pack('<I', len(body) + 16) + header[4:] + body)
        position = end
    if position != len(data):
        raise ValueError('Unexpected Aseprite trailing data')
    body = data[4:128] + b''.join(output)
    return struct.pack('<I', len(body) + 4) + body, fingerprint.digest()


@guard_packer
def pack_aseprite(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    out_temp = tx.make_temp('.aseprite')
    try:
        original = read_native(filepath)
        payload, expected = rewrite_aseprite(original)
        with open(out_temp, 'wb') as target:
            target.write(payload)
        if rewrite_aseprite(read_native(out_temp))[1] != expected:
            return None
        return tx.commit_output(
            out_temp, filepath, len(original), verify='aseprite', **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError, struct.error, zlib.error) as error:
        logging.debug('Aseprite optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)
