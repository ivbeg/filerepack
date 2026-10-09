"""Bounded byte-level primitives for native lossless format handlers."""

import zlib
import os

MAX_NATIVE_BYTES = 256 * 1024 * 1024


def read_native(path: str) -> bytes:
    from .format_support import current_budget
    budget = current_budget()
    if budget:
        budget.memory(os.path.getsize(path) * 8)
    with open(path, 'rb') as source:
        data = source.read(MAX_NATIVE_BYTES + 1)
    if len(data) > MAX_NATIVE_BYTES:
        raise ValueError('Native format exceeds the supported 256 MiB limit')
    return data


def inflate_exact(data: bytes, expected: int, *, wbits: int = zlib.MAX_WBITS) -> bytes:
    from .format_support import current_budget
    budget = current_budget()
    if budget:
        budget.memory(expected * 4 + len(data))
    if not 0 <= expected <= MAX_NATIVE_BYTES:
        raise ValueError('Decoded native payload exceeds supported bounds')
    decoder = zlib.decompressobj(wbits)
    raw = decoder.decompress(data, expected + 1)
    if (len(raw) != expected or not decoder.eof or decoder.unconsumed_tail
            or decoder.unused_data):
        raise ValueError('Invalid compressed payload, size mismatch or trailing bytes')
    if budget:
        budget.consume(decoded=len(raw))
    return raw
