"""Preserve Avro encoded records, schema bytes, sync identity and custom metadata."""

import hashlib
import io
import struct
import zlib
from typing import Any, BinaryIO, Dict, Iterator, Optional, Tuple

from .format_support import Budget, FormatLimit, UnsupportedFormat, inflate


def _long(source: BinaryIO, *, eof: bool = False) -> Optional[int]:
    value = 0
    for index in range(10):
        byte = source.read(1)
        if not byte:
            if index == 0 and eof:
                return None
            raise ValueError('Truncated Avro integer')
        part = byte[0]
        if index == 9 and part > 1:
            raise ValueError('Invalid Avro integer')
        value |= (part & 127) << (7 * index)
        if not part & 128:
            return (value >> 1) ^ -(value & 1)
    raise ValueError('Avro integer exceeds 64 bits')


def _encode_long(value: int) -> bytes:
    number = (value << 1) ^ (value >> 63)
    result = bytearray()
    while number > 127:
        result.append((number & 127) | 128)
        number >>= 7
    result.append(number)
    return bytes(result)


def _bytes(source: BinaryIO, maximum: int) -> bytes:
    size = _long(source)
    if size is None or size < 0:
        raise ValueError('Invalid Avro field length')
    if size > maximum:
        raise FormatLimit('Avro field exceeds supported byte budget')
    data = source.read(size)
    if len(data) != size:
        raise ValueError('Truncated Avro field')
    return data


def _header(source: BinaryIO) -> Tuple[Dict[bytes, bytes], bytes]:
    if source.read(4) != b'Obj\x01':
        raise ValueError('Not an Avro object container')
    metadata: Dict[bytes, bytes] = {}
    while True:
        count = _long(source)
        if count == 0:
            break
        if count is None or abs(count) > 10000:
            raise FormatLimit('Avro header entry budget exceeded')
        block_size = _long(source) if count < 0 else None
        before = source.tell()
        for _ in range(abs(count)):
            key, value = _bytes(source, 1048576), _bytes(source, 1048576)
            key.decode('utf-8')
            if key in metadata:
                raise ValueError('Duplicate Avro metadata key')
            metadata[key] = value
            if source.tell() > 1048576:
                raise FormatLimit('Avro header exceeds one MiB')
        if block_size is not None and source.tell() - before != block_size:
            raise ValueError('Invalid Avro metadata block length')
    if b'avro.schema' not in metadata:
        raise ValueError('Missing Avro schema')
    sync = source.read(16)
    if len(sync) != 16:
        raise ValueError('Truncated Avro sync marker')
    return metadata, sync


def _decode(data: bytes, codec: str, budget: Budget) -> bytes:
    maximum = min(budget.limits.memory // 8, budget.limits.decoded - budget.decoded)
    if codec == 'null':
        if len(data) > maximum:
            raise FormatLimit('Avro decoded block exceeds supported budget')
        budget.consume(decoded=len(data))
        return data
    formats = {'deflate': 'raw-deflate', 'bzip2': 'bzip2', 'xz': 'xz'}
    if codec in formats:
        return inflate(data, budget, formats[codec], maximum=maximum)
    if codec == 'zstandard':
        import zstandard
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)) as reader:
            raw: bytes = reader.read(maximum + 1)
        if len(raw) > maximum:
            raise FormatLimit('Avro decoded block exceeds supported budget')
        budget.consume(decoded=len(raw))
        return raw
    raise UnsupportedFormat('Unsupported Avro block codec: ' + codec)


def _blocks(
    source: BinaryIO, codec: str, sync: bytes, budget: Budget,
) -> Iterator[Tuple[int, bytes]]:
    while True:
        count = _long(source, eof=True)
        if count is None:
            return
        if count <= 0:
            raise ValueError('Invalid Avro record count')
        data = _bytes(source, budget.limits.memory // 8)
        if source.read(16) != sync:
            raise ValueError('Invalid Avro block sync marker')
        budget.consume(nodes=count)
        yield count, _decode(data, codec, budget)


def _write(target: BinaryIO, data: bytes, budget: Budget) -> None:
    budget.consume(written=len(data))
    target.write(data)


def _native_check(path: str, budget: Budget) -> None:
    import fastavro
    try:
        with open(path, 'rb') as source:
            for _ in fastavro.reader(source):
                budget.check()
    except UnicodeDecodeError as exc:
        raise UnsupportedFormat('Avro metadata is outside the native UTF-8 reader profile') from exc


def _read_operation(
    source: str, candidate: Optional[str], budget: Budget,
) -> Tuple[Dict[bytes, bytes], bytes, str]:
    from contextlib import ExitStack
    digest = hashlib.sha256()
    with ExitStack() as stack:
        reader = stack.enter_context(open(source, 'rb'))
        metadata, sync = _header(reader)
        codec = metadata.get(b'avro.codec', b'null').decode('ascii')
        target = stack.enter_context(open(candidate, 'wb')) if candidate else None
        if target is not None:
            output_metadata = {**metadata, b'avro.codec': b'deflate'}
            _write(target, b'Obj\x01' + _encode_long(len(output_metadata)), budget)
            for key, value in output_metadata.items():
                _write(target, _encode_long(len(key)) + key + _encode_long(len(value)) + value,
                       budget)
            _write(target, b'\x00' + sync, budget)
        for count, raw in _blocks(reader, codec, sync, budget):
            digest.update(struct.pack('<QQ', count, len(raw)))
            digest.update(raw)
            if target is not None:
                encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
                encoded = encoder.compress(raw) + encoder.flush()
                _write(target, _encode_long(count) + _encode_long(len(encoded)) + encoded + sync,
                       budget)
    _native_check(candidate or source, budget)
    preserved = {key: value for key, value in metadata.items() if key != b'avro.codec'}
    return preserved, sync, digest.hexdigest()


def operate(
    kind: str, action: str, source: str, candidate: Optional[str],
    options: Dict[str, Any], budget: Budget,
) -> Dict[str, Any]:
    if kind != 'avro-native':
        raise UnsupportedFormat('Unsupported Avro operation')
    if action == 'rewrite' and candidate is not None:
        _read_operation(source, candidate, budget)
        return {'changed': True, 'details': {'codec': 'deflate', 'encoded_records_preserved': True}}
    if action == 'inspect':
        _read_operation(source, None, budget)
        return {'details': {'format': 'avro'}}
    if action == 'compare' and candidate is not None:
        return {'equal': _read_operation(source, None, budget) ==
                         _read_operation(candidate, None, budget)}
    raise UnsupportedFormat('Unsupported Avro operation')
