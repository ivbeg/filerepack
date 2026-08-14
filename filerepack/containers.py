# -*- coding: utf-8 -*-

"""Extract nested assets, run existing packers, reinsert mappings."""

import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from .formats import identify_filename


@dataclass
class MemberResult:
    """Result of packing one extracted member file."""

    key: str
    path: str
    insize: int
    outsize: int
    packed: bool

    @property
    def shrank(self) -> bool:
        return self.outsize < self.insize


@contextmanager
def staging_dir(prefix: str = 'filerepack-') -> Iterator[str]:
    """Temporary directory that is always removed."""
    path = tempfile.mkdtemp(prefix=prefix)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def pack_members(
    members: Dict[str, str],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, MemberResult]:
    """Dispatch packers on extracted files. Pack in place; dryrun is ignored.

    *members* maps a caller key to a filesystem path. The host rebuild is
    left to the caller; use paths of members whose ``shrank`` is true.
    """
    from .repack import _dispatch_packer

    opts: Dict[str, Any] = dict(options or {})
    opts['dryrun'] = False
    results: Dict[str, MemberResult] = {}
    for key, path in members.items():
        try:
            insize = os.path.getsize(path)
        except OSError:
            continue
        kind = identify_filename(os.path.basename(path), peek_path=path)
        packed = False
        if kind is not None and not kind.is_archive:
            packer = kind.packer or kind.key
            result = _dispatch_packer(packer, path, opts)
            packed = result is not None
        try:
            outsize = os.path.getsize(path)
        except OSError:
            outsize = insize
        results[key] = MemberResult(
            key=key, path=path, insize=insize, outsize=outsize, packed=packed,
        )
    return results


def shrunken_paths(results: Dict[str, MemberResult]) -> Dict[str, str]:
    """Map original keys to packed paths for members that got smaller."""
    return {key: item.path for key, item in results.items() if item.shrank}
