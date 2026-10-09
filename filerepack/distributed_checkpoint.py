"""Safe inventory of local PyTorch Distributed Checkpoint directories.

PyTorch's filesystem DCP metadata is pickle-based in supported implementations.
This module inventories it as opaque bytes and never invokes DCP readers or
unpickles metadata. It cannot prove that a checkpoint is complete.
"""

import os
import re
import stat
from typing import Any, Dict, List, Optional, Tuple

from .format_support import UnsupportedFormat, format_scope
from .validation import validate_options

_SHARD_NAME = re.compile(r"^__([0-9]+)_([0-9]+)\.distcp$")


def _generation(item: os.stat_result) -> Tuple[int, ...]:
    return item.st_dev, item.st_ino, item.st_mode, item.st_size, item.st_mtime_ns, item.st_ctime_ns


def inspect_distributed_checkpoint(
    source: str, options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Inventory a flat local DCP directory without reading its pickle metadata."""
    options = validate_options(options or {})
    root = os.path.abspath(os.fspath(source))
    with format_scope(options) as budget:
        root_state = os.lstat(root)
        if stat.S_ISLNK(root_state.st_mode) or not stat.S_ISDIR(root_state.st_mode):
            raise UnsupportedFormat("DCP inspection requires a real local directory")
        files: List[Dict[str, Any]] = []
        metadata = None
        shards = []
        with os.scandir(root) as entries:
            for entry in entries:
                budget.consume(nodes=1)
                budget.memory((len(files) + 1) * 1024)
                item = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(item.st_mode):
                    raise UnsupportedFormat("DCP directory contains a symlink")
                if stat.S_ISDIR(item.st_mode):
                    raise UnsupportedFormat("nested DCP filesystem layouts are unsupported")
                if not stat.S_ISREG(item.st_mode):
                    raise UnsupportedFormat("DCP directory contains a special file")
                row = {"name": entry.name, "bytes": item.st_size}
                files.append(row)
                if entry.name == ".metadata":
                    metadata = row
                if _SHARD_NAME.fullmatch(entry.name):
                    shards.append(row)
        if not metadata or not shards:
            raise UnsupportedFormat("directory is not a recognized flat DCP metadata/shard set")
        if _generation(os.lstat(root)) != _generation(root_state):
            raise ValueError("DCP directory changed during inspection")
        total = sum(item["bytes"] for item in files)
        files.sort(key=lambda item: item['name'])
        return {
            "format": "pytorch-distributed-checkpoint",
            "profile": "flat-filesystem-inventory-v1",
            "source": root,
            "file_count": len(files),
            "shard_count": len(shards),
            "input_bytes": total,
            "files": files,
            "metadata_loaded": False,
            "complete_checkpoint_verified": False,
            "writer_registered": False,
            "reason": "metadata is opaque pickle; full-set reader and savings gates are open",
        }
