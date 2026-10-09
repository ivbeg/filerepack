"""Isolated standard-library stream codecs with capped reads and LZMA dictionaries."""

import bz2
import gzip
import hashlib
import lzma
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from .format_support import Budget, UnsupportedFormat

CHUNK = 65536


def _lzma_blocks(path: str, codec: str, budget: Budget) -> Iterator[bytes]:
    format = lzma.FORMAT_ALONE if codec == 'lzma' else lzma.FORMAT_XZ
    with open(path, 'rb') as source:
        decoder = lzma.LZMADecompressor(format=format, memlimit=budget.limits.memory // 2)
        while True:
            data = source.read(CHUNK) if decoder.needs_input else b''
            if not data and decoder.needs_input:
                if not decoder.eof:
                    raise ValueError('Truncated compressed stream')
                return
            while True:
                raw = decoder.decompress(data, max_length=CHUNK)
                if raw:
                    budget.consume(decoded=len(raw))
                    yield raw
                if not decoder.eof:
                    break
                data = decoder.unused_data
                if not data:
                    data = source.read(CHUNK)
                if not data:
                    return
                decoder = lzma.LZMADecompressor(format=format,
                                               memlimit=budget.limits.memory // 2)


def decoded_blocks(path: str, codec: str, budget: Budget) -> Iterator[bytes]:
    if codec in ('xz', 'lzma'):
        yield from _lzma_blocks(path, codec, budget)
        return
    reader: Any = {'gz': gzip.open, 'svgz': gzip.open, 'bz2': bz2.open}.get(codec)
    if reader is None:
        raise UnsupportedFormat('Unsupported standard stream codec')
    with reader(path, 'rb') as source:
        for raw in iter(lambda: source.read(CHUNK), b''):
            budget.consume(decoded=len(raw))
            yield raw


@contextmanager
def _writer(path: str, codec: str, level: int) -> Iterator[Any]:
    writer: Any
    if codec == 'gz':
        writer = gzip.open(path, 'wb', compresslevel=level)
    elif codec == 'bz2':
        writer = bz2.open(path, 'wb', compresslevel=level)
    elif codec in ('xz', 'lzma'):
        writer = lzma.open(path, 'wb', preset=level,
                           format=lzma.FORMAT_ALONE if codec == 'lzma' else lzma.FORMAT_XZ)
    else:
        raise UnsupportedFormat('Unsupported standard stream codec')
    with writer:
        yield writer


def operate(kind: str, action: str, source: str, candidate: Optional[str],
            options: Dict[str, Any], budget: Budget) -> Dict[str, Any]:
    codec = options['stream_codec']
    budget.memory(CHUNK * 4)
    if action == 'fingerprint':
        checksum = hashlib.sha256()
        for raw in decoded_blocks(source, codec, budget):
            checksum.update(raw)
        return {'fingerprint': checksum.hexdigest()}
    if not candidate:
        raise ValueError('Stream output path required')
    budget.own(candidate)
    if action == 'decode':
        with open(candidate, 'wb') as target:
            for raw in decoded_blocks(source, codec, budget):
                budget.consume(written=len(raw))
                target.write(raw)
                budget.check_scratch()
    elif action == 'encode':
        with open(source, 'rb') as payload, _writer(
            candidate, codec, options.get('compression_level', 9),
        ) as target:
            for raw in iter(lambda: payload.read(CHUNK), b''):
                budget.check()
                target.write(raw)
                budget.check_scratch()
        budget.consume(written=os.path.getsize(candidate))
    else:
        raise ValueError('Unsupported stream operation')
    budget.check_scratch()
    return {'changed': True}
