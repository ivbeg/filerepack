"""Typed filesystem boundary: inspect, stage locally, recheck, publish atomically.

This provides atomic visibility on filesystems supporting replace/link. It does
not promise crash durability, ownership, native ACLs or Windows alternate streams.
"""

import hashlib
import logging
import os
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from functools import wraps
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple, TypeVar, cast

from . import xattrs


def validate_durability(value: object = 'atomic') -> None:
    if value != 'atomic':
        raise ValueError('Unsupported durability guarantee; only atomic visibility is supported')


def digest(path: str) -> str:
    checksum = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            from .format_support import current_budget
            budget = current_budget()
            if budget is not None:
                budget.check()
            checksum.update(block)
    return checksum.hexdigest()


def _generation(state: os.stat_result) -> Tuple[int, ...]:
    # Reads can change atime; exclude it from the concurrency generation.
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns,
            state.st_ctime_ns, state.st_mode, state.st_nlink, state.st_uid, state.st_gid)


def check_inplace_source(path: str) -> None:
    state = os.lstat(path)
    if stat.S_ISLNK(state.st_mode):
        raise ValueError('In-place repacking of a file symlink is unsupported')
    if state.st_nlink > 1:
        raise ValueError('In-place repacking of multiple hard links is unsupported')
    if not stat.S_ISREG(state.st_mode):
        raise ValueError('Repacking requires a regular file')


@dataclass(frozen=True)
class FileMetadata:
    mode: int
    atime_ns: int
    mtime_ns: int
    xattrs: Dict[str, bytes]

    def apply(self, path: str) -> None:
        # Apply attributes explicitly: copy2 may silently omit unsupported metadata.
        current = xattrs.read(path)
        for name in current.keys() - self.xattrs.keys():
            xattrs.remove(path, name)
        for name, value in self.xattrs.items():
            xattrs.write(path, name, value)
        os.chmod(path, self.mode)
        os.utime(path, ns=(self.atime_ns, self.mtime_ns))
        state = os.stat(path)
        if (stat.S_IMODE(state.st_mode) != self.mode or state.st_mtime_ns != self.mtime_ns
                or xattrs.read(path) != self.xattrs):
            raise OSError('Filesystem metadata could not be preserved; publication refused')


@dataclass(frozen=True)
class FileSnapshot:
    path: str
    entry_generation: Tuple[int, ...]
    generation: Tuple[int, ...]
    checksum: str
    metadata: FileMetadata

    @classmethod
    def capture(cls, path: str) -> 'FileSnapshot':
        path = os.path.abspath(path)
        entry, state = os.lstat(path), os.stat(path)
        if not stat.S_ISREG(state.st_mode):
            raise ValueError('Repacking requires a regular file')
        metadata = FileMetadata(stat.S_IMODE(state.st_mode), state.st_atime_ns,
                                state.st_mtime_ns, xattrs.read(path))
        snapshot = cls(path, _generation(entry), _generation(state), digest(path), metadata)
        snapshot.require_unchanged(check_contents=False)
        return snapshot

    def require_unchanged(self, *, check_contents: bool = True) -> None:
        try:
            checksum = digest(self.path) if check_contents else self.checksum
            unchanged = (checksum == self.checksum
                         and _generation(os.lstat(self.path)) == self.entry_generation
                         and _generation(os.stat(self.path)) == self.generation)
        except OSError as exc:
            raise FileExistsError('Source or destination changed before publication') from exc
        if not unchanged:
            raise FileExistsError('Source or destination changed before publication')


def publish_candidate(
    candidate: str, destination: str, *, metadata: FileMetadata,
    guards: Sequence[FileSnapshot] = (), overwrite: bool = False,
    copy: Optional[Callable[[str, str], object]] = None,
    candidate_snapshot: Optional[FileSnapshot] = None,
) -> None:
    """Only the local stage is replaced/linked; failures never truncate destination."""
    parent = os.path.dirname(os.path.abspath(destination))
    os.makedirs(parent, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.filerepack-publish-', dir=parent)
    os.close(descriptor)
    try:
        # macOS can label a newly created stage with protected provenance. Retain
        # that creation-time value only when the source has no value to preserve.
        # Every source attribute and every other stage attribute still uses the
        # exact apply/verify contract; additions during copying are not admitted.
        if sys.platform == 'darwin' and 'com.apple.provenance' not in metadata.xattrs:
            provenance = xattrs.read(temporary).get('com.apple.provenance')
            if provenance is not None:
                metadata = replace(metadata, xattrs={
                    **metadata.xattrs, 'com.apple.provenance': provenance,
                })
        candidate_state = candidate_snapshot or FileSnapshot.capture(candidate)
        candidate_state.require_unchanged(check_contents=False)
        (copy or shutil.copyfile)(candidate, temporary)
        if digest(temporary) != candidate_state.checksum:
            raise OSError('Candidate copy verification failed; publication refused')
        candidate_state.require_unchanged(check_contents=False)
        metadata.apply(temporary)
        if digest(temporary) != candidate_state.checksum:
            raise OSError('Metadata application changed candidate bytes; publication refused')
        # Do this after copying and metadata application, adjacent to publication.
        for guard in guards:
            guard.require_unchanged()
        from .format_support import check_cancelled
        check_cancelled()
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    except (OSError, ValueError) as exc:
        logging.warning('Publication refused for %s: %s', destination, exc)
        raise
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


@dataclass
class SourceScope:
    snapshot: FileSnapshot
    published: bool = False
    scratch: List[str] = field(default_factory=list)


_SOURCE_SCOPE: ContextVar[Optional[SourceScope]] = ContextVar('filerepack_source', default=None)


def source_scope() -> Optional[SourceScope]:
    return _SOURCE_SCOPE.get()


def make_temp(suffix: str, *, directory: Optional[str] = None) -> str:
    descriptor, path = tempfile.mkstemp(suffix=suffix, dir=directory)
    os.close(descriptor)
    from .format_support import own_scratch
    own_scratch(path)
    scope = source_scope()
    if scope is not None:
        scope.scratch.append(path)
    return path


def own_sidecar(path: str) -> str:
    """Register a tool's derived output before encoding; never claim existing files."""
    if os.path.lexists(path):
        raise FileExistsError('Tool sidecar already exists: ' + path)
    from .format_support import own_scratch
    own_scratch(path)
    scope = source_scope()
    if scope is not None:
        scope.scratch.append(path)
    return path


def make_temp_dir(prefix: str, *, directory: Optional[str] = None) -> str:
    path = tempfile.mkdtemp(prefix=prefix, dir=directory)
    from .format_support import own_scratch
    own_scratch(path)
    scope = source_scope()
    if scope is not None:
        scope.scratch.append(path)
    return path


def _cleanup_scratch(scope: SourceScope) -> None:
    for path in reversed(scope.scratch):
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            elif os.path.lexists(path):
                os.unlink(path)
        except OSError as exc:
            logging.warning('Scratch cleanup failed for %s: %s', path, exc)


@contextmanager
def candidate_scope(filepath: str) -> Iterator[SourceScope]:
    """Own scratch for one source; same-source helpers join the parent's scope."""
    check_inplace_source(filepath)
    parent = source_scope()
    if parent is not None and parent.snapshot.path == os.path.abspath(filepath):
        yield parent
        return
    scope = SourceScope(FileSnapshot.capture(filepath))
    token = _SOURCE_SCOPE.set(scope)
    try:
        yield scope
        if not scope.published:
            scope.snapshot.require_unchanged()
    finally:
        _cleanup_scratch(scope)
        _SOURCE_SCOPE.reset(token)


Packer = TypeVar('Packer', bound=Callable[..., object])


def guard_packer(function: Packer) -> Packer:
    """Capture before encoding, keeping each nested helper's source scope isolated.

    The kwargs adapter retains existing heterogeneous public helper signatures.
    Filesystem interfaces below that adapter use concrete typed snapshots.
    """
    @wraps(function)
    def guarded(filepath: str, *args: Any, **kwargs: Any) -> object:
        validate_durability(kwargs.get('durability', 'atomic'))
        from .format_support import FormatLimit, OperationCancelled, unchanged, format_scope
        try:
            with format_scope(kwargs), candidate_scope(filepath):
                return function(filepath, *args, **kwargs)
        except FormatLimit as exc:
            result = unchanged(filepath, str(exc))
            result.status = 'cancelled' if isinstance(exc, OperationCancelled) else 'skipped'
            result.reason_code = 'cancelled' if result.status == 'cancelled' else 'resource_limit'
            return result
    return cast(Packer, guarded)
