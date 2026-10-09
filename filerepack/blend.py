"""Compress Blender projects while preserving the entire decoded file stream."""

from contextlib import ExitStack
import gzip
import logging
import os
import struct
from typing import Any, Optional

from . import candidates as tx
from .models import PackResult
from .native import MAX_NATIVE_BYTES
from .transactions import digest, guard_packer


def _zstandard() -> Any:
    try:
        import zstandard
        return zstandard
    except ImportError:
        return None


def decode_blend(path: str, output: str) -> str:
    with ExitStack() as stack:
        source = stack.enter_context(open(path, 'rb'))
        header = source.read(4)
        source.seek(0)
        reader: Any
        if header[:2] == b'\x1f\x8b':
            reader = stack.enter_context(gzip.GzipFile(fileobj=source))
            codec = 'gzip'
        elif header == b'\x28\xb5\x2f\xfd':
            zstd = _zstandard()
            if zstd is None:
                raise ValueError('Zstandard Blender files require filerepack[blend]')
            reader = stack.enter_context(
                zstd.ZstdDecompressor(max_window_size=MAX_NATIVE_BYTES).stream_reader(
                    source, read_across_frames=True,
                ),
            )
            codec = 'zstd'
        elif header == b'BLEN':
            reader, codec = source, 'raw'
        else:
            raise ValueError('Unsupported Blender stream signature')
        target = stack.enter_context(open(output, 'wb'))
        size = 0
        while True:
            block = reader.read(tx.COPY_BUF)
            if not block:
                break
            size += len(block)
            if size > MAX_NATIVE_BYTES:
                raise ValueError('Decoded Blender stream exceeds supported bounds')
            target.write(block)
    return codec


def validate_blend(path: str) -> int:
    with open(path, 'rb') as source:
        header = source.read(12)
        if (len(header) != 12 or header[:7] != b'BLENDER' or header[7:8] not in (b'-', b'_')
                or header[8:9] not in (b'v', b'V') or not header[9:12].isdigit()):
            raise ValueError('Unsupported Blender header')
        endian = '<' if header[8:9] == b'v' else '>'
        form = endian + ('4siQii' if header[7:8] == b'-' else '4siIii')
        block_size = struct.calcsize(form)
        remaining = os.path.getsize(path) - 12
        dna = False
        while remaining:
            if remaining < block_size:
                raise ValueError('Truncated Blender block header')
            code, length, _address, sdna, count = struct.unpack(form, source.read(block_size))
            remaining -= block_size
            if length < 0 or length > remaining or sdna < 0 or count < 0:
                raise ValueError('Invalid Blender block length or attributes')
            if code == b'ENDB':
                if length or remaining or not dna:
                    raise ValueError('Invalid Blender end block')
                return int(header[9:12])
            if code == b'DNA1':
                if dna or length < 4 or source.read(4) != b'SDNA':
                    raise ValueError('Invalid Blender DNA block')
                source.seek(length - 4, os.SEEK_CUR)
                dna = True
            else:
                source.seek(length, os.SEEK_CUR)
            remaining -= length
    raise ValueError('Missing Blender end block')


def _encode_blend(source: str, output: str, codec: str) -> None:
    with ExitStack() as stack:
        original = stack.enter_context(open(source, 'rb'))
        target = stack.enter_context(open(output, 'wb'))
        if codec == 'zstd':
            writer = stack.enter_context(
                _zstandard().ZstdCompressor(level=19).stream_writer(target),
            )
        else:
            writer = stack.enter_context(
                gzip.GzipFile(filename='', mode='wb', fileobj=target, compresslevel=9, mtime=0),
            )
        for block in iter(lambda: original.read(tx.COPY_BUF), b''):
            writer.write(block)


@guard_packer
def pack_blend(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    decoded = tx.make_temp('.blend-raw')
    out_temp = tx.make_temp('.blend')
    verified = tx.make_temp('.blend-verify')
    try:
        codec = decode_blend(filepath, decoded)
        version = validate_blend(decoded)
        if codec == 'raw':
            codec = 'zstd' if version >= 300 and _zstandard() is not None else 'gzip'
        expected = digest(decoded)
        _encode_blend(decoded, out_temp, codec)
        decode_blend(out_temp, verified)
        if validate_blend(verified) != version or digest(verified) != expected:
            return None
        return tx.commit_output(
            out_temp, filepath, os.path.getsize(filepath), verify='blend',
            **tx.commit_kwargs(**commit),
        )
    except Exception as error:
        logging.debug('Blender optimization skipped: %s', error)
        return None
    finally:
        for path in (decoded, out_temp, verified):
            tx.remove_quietly(path)
