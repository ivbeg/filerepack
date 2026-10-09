"""Data packers using the shared candidate lifecycle."""

import logging
import importlib.util
import os
from os.path import abspath
from typing import Any, Optional
from pathlib import Path

from . import candidates as tx
from .commands import run_command as _run_command
from .models import PackResult
from .tools import resolve_tool
from .transactions import guard_packer
from .parquet import rewrite_parquet


def sqlite_eligibility(source: str, destination: str, options: dict) -> str:
    from .destinations import same_file
    live = any(os.path.lexists(source + suffix) for suffix in ('-wal', '-shm', '-journal'))
    if not same_file(source, destination):
        if live and options.get('backup'):
            return 'Live SQLite snapshots do not support a single-file source backup'
        return ''
    if live:
        return 'SQLite sidecars indicate a live database; request a distinct snapshot output'
    if not options.get('sqlite_offline'):
        return 'In-place SQLite requires sqlite_offline=True / --sqlite-offline and closed users'
    return ''


def copy_sqlite_snapshot(source: str, destination: str) -> None:
    """Read a consistent SQLite transaction including committed WAL pages."""
    import sqlite3
    from .format_support import format_scope
    tx.remove_quietly(destination)
    with format_scope({}) as budget:
        reader = sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True,
                                 timeout=1.0)
        writer = sqlite3.connect(destination)
        try:
            reader.execute('BEGIN')
            reader.execute('SELECT count(*) FROM sqlite_master').fetchone()
            reader.backup(writer, pages=128, progress=lambda *_args: budget.check())
            if writer.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('SQLite snapshot failed integrity validation')
            budget.consume(written=os.path.getsize(destination))
        finally:
            writer.close()
            reader.close()


@guard_packer
def pack_parquet(
    filepath: str, debug: bool = False, quiet: bool = False,
    ultra: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Recompress Parquet only after schema, metadata and value verification."""
    insize = os.path.getsize(filepath)
    tempfpath = tx.make_temp('.parquet')
    c_level = 22 if ultra else 19
    try:
        if not rewrite_parquet(filepath, tempfpath, c_level):
            return None
        return tx.commit_output(
            tempfpath, filepath, insize, verify='parquet',
            **tx.commit_kwargs(**commit),
        )
    except Exception as exc:
        if debug:
            logging.warning('parquet compression failed: %s', exc)
        return None
    finally:
        tx.remove_quietly(tempfpath)


@guard_packer
def pack_sqlite(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    if filepath.lower().endswith(('.vscdb', '.sqlitedb')):
        from .qgis import pack_qgd
        if any(os.path.lexists(filepath + suffix) for suffix in ('-wal', '-shm', '-journal')):
            return None
        return pack_qgd(filepath, debug=debug, quiet=quiet, **commit)
    import sqlite3
    from .outcomes import record
    if any(os.path.lexists(filepath + suffix) for suffix in ('-wal', '-shm', '-journal')):
        record('skipped', 'sqlite_live', 'Live SQLite inputs require a snapshot output')
        return None
    if not commit.get('sqlite_offline'):
        record('skipped', 'sqlite_offline_required', 'SQLite requires explicit offline policy')
        return None
    try:
        with open(filepath, 'rb') as fh:
            if not fh.read(16).startswith(b'SQLite format 3'):
                return None
    except OSError:
        return None
    insize = os.path.getsize(filepath)
    out_temp = tx.make_temp('.sqlite')
    tx.remove_quietly(out_temp)
    for suffix in ('-journal', '-wal', '-shm'):
        tx.own_sidecar(out_temp + suffix)
    try:
        src = sqlite3.connect(Path(filepath).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            escaped = abspath(out_temp).replace("'", "''")
            src.execute(f"VACUUM INTO '{escaped}'")
        except sqlite3.Error:
            tx.remove_quietly(out_temp)
            dst = sqlite3.connect(out_temp)
            try:
                src.backup(dst)
                dst.execute('VACUUM')
            finally:
                dst.close()
        finally:
            src.close()
        return tx.commit_output(
            out_temp, filepath, insize, verify='sqlite', lossless=True,
            **tx.commit_kwargs(**commit)
        )
    except sqlite3.Error:
        tx.remove_quietly(out_temp)
        return None


@guard_packer
def pack_orc(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('orc-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_avro(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('avro-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_feather(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('feather-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_arrow(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('arrow-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_hdf5(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('hdf5-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_netcdf(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('netcdf-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_woff(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    if importlib.util.find_spec('fontTools') is None:
        from .outcomes import record
        record('unsupported', 'missing_dependency', 'WOFF preservation requires filerepack[fonts]')
        return None
    return pack_format('font-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


@guard_packer
def pack_woff2(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    result = pack_woff(filepath, debug=debug, quiet=quiet, **commit)
    if result is not None:
        return result
    compress, decompress = resolve_tool('woff2_compress'), resolve_tool('woff2_decompress')
    if compress is None or decompress is None:
        return None
    from shutil import copy2
    insize = os.path.getsize(filepath)
    tmpdir = tx.make_temp_dir(prefix='filerepack-woff2-')
    try:
        copied = os.path.join(tmpdir, 'font.woff2')
        copy2(filepath, copied)
        if _run_command([decompress, copied], quiet=quiet, debug=debug) is None:
            return None
        decoded = os.path.join(tmpdir, 'font.ttf')
        if not os.path.isfile(decoded):
            return None
        if _run_command([compress, decoded], quiet=quiet, debug=debug) is None:
            return None
        staged = tx.make_temp('.woff2')
        copy2(copied, staged)
        return tx.commit_output(staged, filepath, insize, verify='woff2', lossless=True,
                                **tx.commit_kwargs(**commit))
    finally:
        tx.remove_quietly(tmpdir)
