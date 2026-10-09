"""Streams packers using the shared candidate lifecycle."""

import logging
import gzip
import bz2
import lzma
import os
from typing import Any, Callable, ContextManager, List, Literal, Optional, Protocol

from . import candidates as tx
from .models import PackResult
from .outcomes import record, Status
from .tools import resolve_tool
from .transactions import guard_packer
from .commands import run_to_file as _run_to_file
from .format_support import current_budget, current_options, run_operation, tool_threads


def _native_stream(action: str, source: str, codec: str, candidate: Optional[str] = None):
    return run_operation('stream-native', action, source, candidate,
                         {**current_options(), 'stream_codec': codec})


def _bounded_copy(source: Any, target: Any, *, decoded: bool = False) -> None:
    from .format_support import current_budget
    budget = current_budget()
    for block in iter(lambda: source.read(tx.COPY_BUF), b''):
        if budget:
            budget.consume(decoded=len(block) if decoded else 0, written=len(block))
        target.write(block)
        if budget:
            budget.check_scratch()


class BinaryReader(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class BinaryWriter(Protocol):
    def write(self, data: bytes, /) -> int: ...


def _pack_stream_codec(
    filepath: str,
    suffix: str,
    open_decomp: Callable[[str, Literal['rb']], ContextManager[BinaryReader]],
    open_comp: Callable[[str], ContextManager[BinaryWriter]],
    cli_key: Optional[str],
    cli_args: List[str],
    verify: str,
    debug: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    """Decompress to a temp file, recompress, then atomic-replace."""
    insize = os.path.getsize(filepath)
    dec_temp = tx.make_temp('.bin')
    out_temp = tx.make_temp(suffix)
    try:
        _native_stream('decode', filepath, verify, dec_temp)

        used_cli = False
        tool = resolve_tool(cli_key) if cli_key else None
        if tool:
            level = current_options().get('compression_level', 9)
            flags = [f'-{level}', '-c']
            if cli_key == 'pigz':
                flags += ['-p', str(tool_threads())]
            used_cli = _run_to_file([tool] + flags + [dec_temp], out_temp, debug)

        if not used_cli:
            _native_stream('encode', dec_temp, verify, out_temp)

        return tx.commit_output(
            out_temp, filepath, insize, verify=verify, lossless=True, **tx.commit_kwargs(**commit)
        )
    except Exception as exc:
        from .format_support import FormatLimit, OperationCancelled
        status: Status = ('cancelled' if isinstance(exc, OperationCancelled) else
                          'skipped' if isinstance(exc, FormatLimit) else 'failed')
        record(status, 'resource_limit' if isinstance(exc, FormatLimit) else
               'decode_or_encode_error', str(exc))
        if debug:
            logging.warning('%s repack failed: %s', suffix, exc)
        return None
    finally:
        tx.remove_quietly(dec_temp)
        tx.remove_quietly(out_temp)


def _pack_pipe_codec(
    filepath: str,
    decode_cmd: List[str],
    encode_prefix: List[str],
    suffix: str,
    verify: Optional[str],
    debug: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    """Decode with argv stdout, encode with prefix+[payload], then replace."""
    insize = os.path.getsize(filepath)
    dec_temp = tx.make_temp('.bin')
    out_temp = tx.make_temp(suffix)
    try:
        if not _run_to_file(decode_cmd, dec_temp, debug):
            return None
        budget = current_budget()
        if budget:
            budget.consume(decoded=os.path.getsize(dec_temp), written=os.path.getsize(dec_temp))
        if not _run_to_file(encode_prefix + [dec_temp], out_temp, debug):
            return None
        return tx.commit_output(
            out_temp, filepath, insize, verify=verify, lossless=True, **tx.commit_kwargs(**commit)
        )
    finally:
        tx.remove_quietly(dec_temp)
        tx.remove_quietly(out_temp)


def _compress_file(src: str, dest: str, codec: str, debug: bool = False) -> bool:
    """Compress a single payload file with the named stream codec."""
    if codec == 'gz':
        tool = resolve_tool('pigz')
        if tool:
            return _run_to_file([tool, '-9', '-p', str(tool_threads()), '-c', src], dest, debug)
        _native_stream('encode', src, codec, dest)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    if codec == 'bz2':
        tool = resolve_tool('bzip2')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        _native_stream('encode', src, codec, dest)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    if codec == 'xz':
        tool = resolve_tool('xz')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        _native_stream('encode', src, codec, dest)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    if codec == 'lzma':
        tool = resolve_tool('lzma')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        _native_stream('encode', src, codec, dest)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    tool_map = {
        'zst': ('zstd', ['-19', '-c']),
        'br': ('brotli', ['-q', '11', '-c']),
        'lz4': ('lz4', ['-9', '-c']),
        'lz': ('lzip', ['-9', '-c']),
        'lzo': ('lzop', ['-9', '-c']),
        'z': ('compress', ['-c']),
    }
    spec = tool_map.get(codec)
    if spec is None:
        return False
    key, flags = spec
    tool = resolve_tool(key)
    if tool is None:
        return False
    return _run_to_file([tool] + flags + [src], dest, debug)


@guard_packer
def pack_gzip(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .formats import peek_gzip_is_warc

    if filepath.lower().endswith('.warc.gz') or peek_gzip_is_warc(filepath):
        from .warc import pack_warc

        return pack_warc(filepath, debug=debug, quiet=quiet, **commit)

    def _gz_out(path: str) -> ContextManager[BinaryWriter]:
        return gzip.open(path, 'wb', compresslevel=9)

    return _pack_stream_codec(
        filepath, '.gz', gzip.open, _gz_out, 'pigz', ['-9', '-c'],
        'gz', debug=debug, **commit,
    )


@guard_packer
def pack_xz(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    def _xz_out(path: str) -> ContextManager[BinaryWriter]:
        return lzma.open(path, 'wb', preset=9)

    return _pack_stream_codec(
        filepath, '.xz', lzma.open, _xz_out, 'xz', ['-9', '-c'],
        'xz', debug=debug, **commit,
    )


@guard_packer
def pack_bz2(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    def _bz_out(path: str) -> ContextManager[BinaryWriter]:
        return bz2.open(path, 'wb', compresslevel=9)

    return _pack_stream_codec(
        filepath, '.bz2', bz2.open, _bz_out, 'bzip2', ['-9', '-c'],
        'bz2', debug=debug, **commit,
    )


@guard_packer
def pack_zstd(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    zstd = resolve_tool('zstd')
    if zstd is None:
        if debug:
            logging.warning('zstd not installed')
        return None
    return _pack_pipe_codec(
        filepath, [zstd, '-d', '-c', filepath], [zstd, '-19', '-c'],
        '.zst', 'zst', debug=debug, **commit,
    )


@guard_packer
def pack_brotli(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    brotli = resolve_tool('brotli')
    if brotli is None:
        if debug:
            logging.warning('brotli not installed')
        return None
    return _pack_pipe_codec(
        filepath, [brotli, '-d', '-c', filepath], [brotli, '-q', '11', '-c'],
        '.br', 'br', debug=debug, **commit,
    )


@guard_packer
def pack_lz4(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('lz4')
    if tool is None:
        return None
    return _pack_pipe_codec(
        filepath, [tool, '-d', '-c', filepath], [tool, '-9', '-c'],
        '.lz4', 'lz4', debug=debug, **commit,
    )


@guard_packer
def pack_lzip(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('lzip')
    if tool is None:
        return None
    return _pack_pipe_codec(
        filepath, [tool, '-d', '-c', filepath], [tool, '-9', '-c'],
        '.lz', 'lz', debug=debug, **commit,
    )


@guard_packer
def pack_lzo(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('lzop')
    if tool is None:
        return None
    return _pack_pipe_codec(
        filepath, [tool, '-d', '-c', filepath], [tool, '-9', '-c'],
        '.lzo', 'lzo', debug=debug, **commit,
    )


@guard_packer
def pack_lzma(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    import lzma

    def _lzma_out(path: str) -> ContextManager[BinaryWriter]:
        return lzma.open(path, 'wb', format=lzma.FORMAT_ALONE, preset=9)

    def _lzma_in(path: str, mode: str = 'rb'):
        return lzma.open(path, mode, format=lzma.FORMAT_ALONE)

    return _pack_stream_codec(
        filepath, '.lzma', _lzma_in, _lzma_out, 'lzma', ['-9', '-c'],
        'lzma', debug=debug, **commit,
    )


@guard_packer
def pack_compress(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    compress = resolve_tool('compress')
    gzip_tool = resolve_tool('gzip') or resolve_tool('pigz')
    if compress is None or gzip_tool is None:
        if debug:
            import logging
            logging.warning('compress/gzip not installed for .Z')
        return None
    return _pack_pipe_codec(
        filepath, [gzip_tool, '-d', '-c', filepath], [compress, '-c'],
        '.Z', 'z', debug=debug, **commit,
    )
