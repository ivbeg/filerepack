"""Photoshop PSB optimization with structural and decoded-channel verification."""

import hashlib
import logging
import struct
import zlib
from typing import Any, List, Optional, Tuple

from . import candidates as tx
from .images import _PsdBuf, _PsdError, _recompress_psd_bytes
from .models import PackResult
from .native import MAX_NATIVE_BYTES, inflate_exact, read_native
from .transactions import guard_packer


def _channel(block: bytes, expected: int) -> bytes:
    if len(block) < 2:
        raise ValueError('Missing PSB channel compression')
    codec = int.from_bytes(block[:2], 'big')
    if codec in (2, 3):
        return block[:2] + hashlib.sha256(inflate_exact(block[2:], expected)).digest()
    if codec == 0:
        if len(block) != expected + 2:
            raise ValueError('Invalid raw PSB channel length')
    elif codec != 1:
        raise ValueError('Unsupported PSB compression')
    return block


def _layer_info(payload: bytes, depth: int) -> bytes:
    if not payload:
        return b''
    buf = _PsdBuf(payload)
    count = buf.i16()
    records: List[bytes] = []
    channels: List[Tuple[int, int]] = []
    decoded = 0
    for _ in range(abs(count)):
        start = buf.pos
        top, left, bottom, right = struct.unpack('>4i', buf.read(16))
        if bottom < top or right < left:
            raise ValueError('Invalid PSB layer bounds')
        offsets = []
        for _channel_index in range(buf.u16()):
            channel_id = buf.i16()
            offsets.append(buf.pos - start)
            size = buf.u64()
            # Mask channels have dimensions in layer extra data. Preserve their
            # compressed bytes; unsupported mask rewrites are rejected later.
            expected = (bottom - top) * (right - left) * (depth // 8)
            channels.append((size, expected if channel_id >= -1 else -1))
            decoded += expected
            if decoded > MAX_NATIVE_BYTES:
                raise ValueError('PSB decoded layers exceed supported bounds')
        buf.skip(12)
        buf.skip(buf.u32())
        record = bytearray(payload[start:buf.pos])
        for offset in offsets:
            record[offset:offset + 8] = b'\0' * 8
        records.append(bytes(record))
    content = [count.to_bytes(2, 'big', signed=True), *records]
    for size, expected in channels:
        block = buf.read(size)
        if expected < 0 and block[:2] in (b'\0\2', b'\0\3'):
            raise ValueError('Compressed PSB mask channels are unsupported')
        content.append(block if expected < 0 else _channel(block, expected))
    if buf.remaining() not in (0, 1):
        raise ValueError('Unsupported PSB layer trailing data')
    content.append(buf.read(buf.remaining()))
    checksum = hashlib.sha256()
    for part in content:
        checksum.update(len(part).to_bytes(8, 'big') + part)
    return checksum.digest()


def psb_fingerprint(data: bytes) -> bytes:
    if len(data) < 26 or data[:6] != b'8BPS\0\2' or any(data[6:12]):
        raise ValueError('Not a supported PSB file')
    channels, height, width, depth, mode = struct.unpack('>HIIHH', data[12:26])
    if (not 1 <= channels <= 56 or not width or not height or depth not in (8, 16, 32)
            or mode not in (1, 2, 3, 4, 7, 8, 9)):
        raise ValueError('Unsupported PSB image attributes')
    expected = channels * height * width * (depth // 8)
    if expected > MAX_NATIVE_BYTES:
        raise ValueError('PSB composite exceeds supported bounds')
    buf = _PsdBuf(data, 26)
    colors = buf.read(buf.u32())
    resources = buf.read(buf.u32())
    layers = buf.read(buf.u64())
    if layers:
        layer_buf = _PsdBuf(layers)
        normalized = _layer_info(layer_buf.read(layer_buf.u64()), depth)
        layer_tail = layer_buf.read(layer_buf.remaining())
    else:
        normalized, layer_tail = b'', b''
    composite = _channel(buf.read(buf.remaining()), expected)
    checksum = hashlib.sha256()
    for part in (data[:26], colors, resources, normalized, layer_tail, composite):
        checksum.update(len(part).to_bytes(8, 'big') + part)
    return checksum.digest()


@guard_packer
def pack_psb(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    out_temp = tx.make_temp('.psb')
    try:
        original = read_native(filepath)
        expected = psb_fingerprint(original)
        payload = _recompress_psd_bytes(original)
        if payload is None or payload == original:
            return None
        with open(out_temp, 'wb') as target:
            target.write(payload)
        if psb_fingerprint(read_native(out_temp)) != expected:
            return None
        return tx.commit_output(
            out_temp, filepath, len(original), verify='psb', **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError, _PsdError, struct.error, zlib.error) as error:
        logging.debug('PSB optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)
