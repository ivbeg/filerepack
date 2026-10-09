"""Path planning, cooperative reservations and collision-safe publication."""

import hashlib
import os
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .transactions import FileMetadata, FileSnapshot, check_inplace_source, publish_candidate
from .transactions import digest as digest


def normalize_path(path: str) -> str:
    """Resolve directory aliases while retaining the named final directory entry."""
    path = os.path.abspath(path)
    return os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))


def same_file(left: str, right: str) -> bool:
    if os.path.normcase(normalize_path(left)) == os.path.normcase(normalize_path(right)):
        return True
    try:
        left_state, right_state = os.stat(left), os.stat(right)
        return bool(left_state.st_ino and right_state.st_ino) and os.path.samestat(
            left_state, right_state,
        )
    except OSError:
        return False


def backup_destination(source: str, directory: Optional[str] = None) -> str:
    if not directory:
        return normalize_path(source + '.bak')
    base = os.path.basename(source)
    target = normalize_path(os.path.join(directory, base))
    if not os.path.lexists(target):
        return target
    parent = os.path.basename(os.path.dirname(os.path.abspath(source)))
    stem, ext = os.path.splitext(base)
    target = normalize_path(os.path.join(directory, f'{parent}_{stem}{ext}'))
    number = 1
    while os.path.lexists(target):
        target = normalize_path(os.path.join(directory, f'{parent}_{stem}_{number}{ext}'))
        number += 1
    return target


def copy_verified(source: str, destination: str) -> str:
    shutil.copy2(source, destination)
    checksum = digest(source)
    if digest(destination) != checksum:
        raise OSError('Source changed while copying; publication refused')
    return checksum


@dataclass
class DestinationPlan:
    source: str
    output: str
    converted: Optional[str] = None
    backup: Optional[str] = None
    overwrite: bool = False

    @property
    def paths(self) -> List[str]:
        return list(dict.fromkeys(p for p in (
            self.source, self.output, self.converted, self.backup,
        ) if p is not None))

    def validate(self) -> None:
        if not os.path.isfile(self.source):
            raise FileNotFoundError(f'Source is not a regular file: {self.source}')
        if self.output == self.source:
            check_inplace_source(self.source)
        for path in (self.output, self.converted):
            if path is None or path == self.source:
                continue
            if os.path.isdir(path):
                raise IsADirectoryError(f'Destination is a directory: {path}')
            if os.path.lexists(path) and not self.overwrite:
                raise FileExistsError(
                    f'Destination already exists: {path}; use overwrite explicitly',
                )
        if self.backup:
            if any(same_file(self.backup, path) for path in (
                self.source, self.output, self.converted,
            ) if path is not None):
                raise FileExistsError(f'Backup conflicts with source/output: {self.backup}')
            if os.path.lexists(self.backup):
                raise FileExistsError(f'Required backup already exists: {self.backup}')
        for path in self.paths:
            parent = os.path.dirname(path)
            while not os.path.lexists(parent):
                parent = os.path.dirname(parent)
            if not os.path.isdir(parent):
                raise NotADirectoryError(f'Destination parent is not a directory: {parent}')


class PathReservation:
    """Fail-fast, cross-process ownership of paths and existing file identities."""

    def __init__(
        self, paths: List[str], *, dryrun: bool = False,
        source_snapshot: Optional[FileSnapshot] = None,
    ) -> None:
        self.paths = [normalize_path(path) for path in paths]
        self.dryrun = dryrun
        self.locks: List[str] = []
        self.identities: Dict[str, Tuple[int, int]] = {}
        self.snapshots: Dict[str, FileSnapshot] = {}
        self.source_snapshot = source_snapshot

    def __enter__(self) -> 'PathReservation':
        for path in self.paths:
            if self.source_snapshot is not None and path == self.source_snapshot.path:
                self.source_snapshot.require_unchanged()
                self.snapshots[path] = self.source_snapshot
            elif os.path.isfile(path):
                self.snapshots[path] = FileSnapshot.capture(path)
        if self.dryrun:
            return self
        tokens = set()
        for path in self.paths:
            # Conservative case/NFC folding also protects aliases on insensitive volumes.
            tokens.add('path:' + unicodedata.normalize('NFC', path).casefold())
            try:
                state = os.stat(path)
                identity = (state.st_dev, state.st_ino)
                self.identities[path] = identity
                if state.st_ino:
                    tokens.add(f'inode:{identity}')
            except FileNotFoundError:
                pass
        uid = str(os.getuid()) if hasattr(os, 'getuid') else 'user'
        root = os.path.join(tempfile.gettempdir(), 'filerepack-reservations-' + uid)
        os.makedirs(root, mode=0o700, exist_ok=True)
        try:
            for token in sorted(tokens):
                name = hashlib.sha256(token.encode('utf-8', errors='surrogatepass')).hexdigest()
                lock = os.path.join(root, name + '.lock')
                try:
                    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    raise FileExistsError(
                        f'Source or destination is reserved by another operation: {lock}',
                    )
                self.locks.append(lock)
                os.close(descriptor)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args) -> None:
        for lock in reversed(self.locks):
            try:
                os.unlink(lock)
            except FileNotFoundError:
                pass
        self.locks.clear()

    def require_source_unchanged(self) -> None:
        snapshot = self.snapshots.get(self.paths[0]) if self.paths else None
        if snapshot is not None:
            snapshot.require_unchanged()

    def publish_copy(
        self, source: str, destination: str, *, overwrite: bool = False,
        metadata: Optional[FileMetadata] = None,
        candidate_snapshot: Optional[FileSnapshot] = None,
    ) -> None:
        destination = normalize_path(destination)
        if self.dryrun or destination not in self.paths:
            raise ValueError('Publication requires an owned destination reservation')
        original = self.snapshots.get(destination)
        source_snapshot = self.snapshots.get(self.paths[0]) if self.paths else None
        guards = [snapshot for snapshot in (source_snapshot, original) if snapshot is not None]
        if original is not None:
            check_inplace_source(destination)
        if metadata is None:
            metadata = (source_snapshot or FileSnapshot.capture(source)).metadata
        publish_candidate(source, destination, metadata=metadata, guards=guards,
                          overwrite=overwrite and original is not None,
                          candidate_snapshot=candidate_snapshot)
