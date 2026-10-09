"""Bounded operation evidence; command arguments and user paths are never collected."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from importlib import metadata
import os
import sys
from typing import Any, Dict, Iterator, List, Optional

_ACTIVE: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar('evidence', default=None)
_PACKAGES = {'PIL': 'Pillow', 'pikepdf': 'pikepdf', 'fontTools': 'fonttools',
             'brotli': 'Brotli', 'pyarrow': 'pyarrow', 'fastavro': 'fastavro',
             'h5py': 'h5py', 'netCDF4': 'netCDF4', 'tifffile': 'tifffile',
             'imagecodecs': 'imagecodecs', 'numpy': 'numpy', 'torch': 'torch',
             'pyreadstat': 'pyreadstat', 'zarr': 'zarr', 'numcodecs': 'numcodecs',
             'zopfli': 'zopfli', 'lz4': 'lz4', 'olefile': 'olefile'}


@contextmanager
def evidence_scope() -> Iterator[List[Dict[str, Any]]]:
    rows = _ACTIVE.get()
    if rows is None:
        rows = []
    token = _ACTIVE.set(rows)
    try:
        yield rows
    finally:
        _ACTIVE.reset(token)


def add(value: Dict[str, Any]) -> None:
    rows = _ACTIVE.get()
    if rows is None:
        return
    value = dict(value)
    count = value.pop('count', 1)
    for row in rows:
        if {key: item for key, item in row.items() if key != 'count'} == value:
            row['count'] += count
            return
    if len(rows) < 128:
        rows.append({**value, 'count': count})
    elif not any(row.get('type') == 'truncated' for row in rows):
        rows.append({'type': 'truncated', 'reason': 'Evidence exceeds 128 distinct events',
                     'count': 1})


def command(executable: str) -> None:
    if _ACTIVE.get() is None:
        return
    from .tools import TOOL_SPECS
    name = os.path.basename(executable).removesuffix('.exe')
    key = next((spec.key for spec in TOOL_SPECS if name in spec.binaries), None)
    add({'type': 'tool', 'executable': executable, 'key': key, 'version': None})


def validation(kind: str, stage: str, valid: bool, reason: str = '') -> None:
    add({'type': 'validation', 'kind': kind, 'stage': stage, 'valid': valid,
         'reason': reason[:500]})


def loaded_packages() -> None:
    """Identify libraries loaded by an isolated worker, without importing new readers."""
    for module, package in _PACKAGES.items():
        if module in sys.modules:
            try:
                version = metadata.version(package)
            except metadata.PackageNotFoundError:
                version = None
            add({'type': 'library', 'name': package, 'version': version})


@lru_cache(maxsize=128)
def _version(path: str, key: str, signature: tuple) -> Optional[str]:
    from .tools import probe_version
    from .format_support import _BUDGET
    token, budget_token = _ACTIVE.set(None), _BUDGET.set(None)
    try:
        return probe_version(path, key)
    except (OSError, ValueError):
        return None
    finally:
        _BUDGET.reset(budget_token)
        _ACTIVE.reset(token)


def report_evidence(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Read tool versions after processing, with bounded probes and a generation cache."""
    result = []
    for row in rows:
        row = dict(row)
        if row.get('type') == 'tool' and row.get('key'):
            try:
                stat = os.stat(row['executable'])
                signature = (stat.st_dev, stat.st_ino, stat.st_size,
                             stat.st_mtime_ns, stat.st_ctime_ns)
                row['version'] = _version(row['executable'], row['key'], signature)
            except OSError:
                pass
        result.append(row)
    return result
