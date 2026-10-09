"""Bounded CFB allocation validation and independent logical preservation checks.

Physical sector/directory IDs and the root mini-stream carrier are deliberately
excluded from the manifest. No live application stream is excluded.
"""

import hashlib
import os
import struct
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from typing import BinaryIO, Dict, Iterator, List, Optional, Set, Tuple, Union

from .cfb_name_compare import NameKey, cfb_name_key
from .ole_root import normalize_root_name, root_name_view

MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
FREE = 0xFFFFFFFF
END = 0xFFFFFFFE
FAT = 0xFFFFFFFD
DIFAT = 0xFFFFFFFC
MAX_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 8192
MAX_DEPTH = 32

Path = Tuple[str, ...]


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("OLE: " + reason)


def _u32(data: bytes, offset: int) -> int:
    return int(struct.unpack_from("<I", data, offset)[0])


def _words(data: bytes) -> Tuple[int, ...]:
    return struct.unpack("<" + "I" * (len(data) // 4), data)


@dataclass(frozen=True)
class OleEntry:
    path: Path
    name: str
    kind: int
    clsid: bytes
    state: int
    created: int
    modified: int
    size: int
    sha256: str


@dataclass(frozen=True)
class OleManifest:
    version: int
    entries: Tuple[OleEntry, ...]


@dataclass(frozen=True)
class _DirectoryEntry:
    name: str
    kind: int
    color: int
    left: int
    right: int
    child: int
    clsid: bytes
    state: int
    created: int
    modified: int
    start: int
    size: int


class CompoundFile:
    """Strict allocation graph independent of the Rust writer and olefile reader."""

    def __init__(self, data: bytes):
        self.data = data
        self.owners: Dict[int, str] = {}
        self.mini_owners: Set[int] = set()
        self.streams: Dict[Path, bytes] = {}
        self.entries: List[OleEntry] = []
        self._header()
        self.data = normalize_root_name(data)
        self.root_name_normalized = self.data is not data
        # A legacy carrier has been replaced by its private canonical copy.
        # Release the input before materializing its logical streams.
        del data
        self._allocation_tables()
        directory = self._chain(self.first_dir, "directory")
        raw = b"".join(self._sector(sid) for sid in directory)
        _require(len(raw) // 128 <= MAX_ENTRIES, "directory entry limit exceeded")
        self.directory = [self._directory_entry(raw[i : i + 128]) for i in range(0, len(raw), 128)]
        _require(bool(self.directory) and self.directory[0].kind == 5, "missing root storage")
        root = self.directory[0]
        _require(
            root.name == "Root Entry" and root.left == root.right == FREE,
            "unsupported root storage",
        )
        # Real Office files can record a nonzero root creation FILETIME despite
        # MS-CFB 2.6.2. Retain it in the manifest and require exact preservation,
        # just as for root modification time; never normalize either timestamp.
        self.mini_data = self._payload(root.start, root.size, "root mini stream")
        _require(root.size % 64 == 0, "unaligned root mini stream")
        self.seen: Set[int] = {0}
        self._add_entry((), root)
        self._tree(root.child, (), 0)
        self._complete_graph()
        self.manifest = OleManifest(3, tuple(sorted(self.entries, key=lambda e: e.path)))

    def _header(self) -> None:
        _require(
            512 <= len(self.data) <= MAX_BYTES and len(self.data) % 512 == 0,
            "invalid file size or 128 MiB limit exceeded",
        )
        header = self.data[:512]
        _require(header[:8] == MAGIC, "not a CFB container")
        minor, major, order, shift, mini_shift = struct.unpack_from("<5H", header, 24)
        _require(major == 3, "only CFB version 3 is qualified")
        _require(
            minor in (0x3B, 0x3E) and order == 0xFFFE and shift == 9 and mini_shift == 6,
            "unsupported CFB header",
        )
        _require(
            header[8:24] == b"\0" * 16
            and header[34:40] == b"\0" * 6
            and _u32(header, 40) == 0
            and _u32(header, 56) == 4096,
            "invalid reserved header or mini-stream cutoff",
        )
        self.sectors = len(self.data) // 512 - 1
        self.fat_count, self.first_dir = struct.unpack_from("<II", header, 44)
        self.first_mini, self.mini_count = struct.unpack_from("<II", header, 60)
        self.first_difat, self.difat_count = struct.unpack_from("<II", header, 68)
        _require(
            0 < self.fat_count <= self.sectors
            and self.mini_count <= self.sectors
            and self.difat_count <= self.sectors,
            "invalid allocation counts",
        )

    def _sector(self, sid: int) -> bytes:
        _require(0 <= sid < self.sectors, "sector reference outside file")
        return self.data[(sid + 1) * 512 : (sid + 2) * 512]

    def _claim(self, sid: int, owner: str) -> None:
        _require(sid not in self.owners, "overlapping or cyclic sector chains")
        self._sector(sid)
        self.owners[sid] = owner

    def _allocation_tables(self) -> None:
        ids = list(_words(self.data[76:512]))
        sid = self.first_difat
        difat_ids = []
        for _ in range(self.difat_count):
            self._claim(sid, "DIFAT")
            difat_ids.append(sid)
            words = _words(self._sector(sid))
            ids.extend(words[:-1])
            sid = words[-1]
        _require(sid == END or (self.difat_count == 0 and sid == FREE), "bad DIFAT terminator")
        _require(all(sid == FREE for sid in ids[self.fat_count :]), "unexplained DIFAT entries")
        ids = ids[: self.fat_count]
        _require(len(ids) == self.fat_count, "incomplete FAT sector list")
        for sid in ids:
            self._claim(sid, "FAT")
        self.fat = _words(b"".join(self._sector(sid) for sid in ids))
        _require(len(self.fat) >= self.sectors, "FAT does not cover the file")
        _require(all(self.fat[sid] == FAT for sid in ids), "FAT sector marker mismatch")
        _require(all(self.fat[sid] == DIFAT for sid in difat_ids), "DIFAT marker mismatch")
        mini = self._chain(self.first_mini, "MiniFAT", self.mini_count)
        self.minifat = _words(b"".join(self._sector(sid) for sid in mini))

    def _chain(self, start: int, owner: str, count: Optional[int] = None) -> List[int]:
        if count == 0:
            _require(start in (END, FREE), "nonempty zero-length chain")
            return []
        result: List[int] = []
        while start != END:
            _require(len(result) < self.sectors, "allocation chain limit exceeded")
            self._claim(start, owner)
            result.append(start)
            start = self.fat[start]
        _require(count is None or len(result) == count, "stream/chain length mismatch")
        return result

    def _payload(self, start: int, size: int, owner: str) -> bytes:
        _require(size <= MAX_BYTES, "stream byte limit exceeded")
        chain = self._chain(start, owner, (size + 511) // 512)
        # Coalesce physical runs after complete chain validation. Copy exactly
        # the logical bytes once; avoid one temporary bytes object per sector
        # and a second full copy merely to strip the final sector's padding.
        view = memoryview(self.data)
        spans = []
        first, previous, remaining = -1, -2, size
        for sid in chain:
            if sid != previous + 1:
                if first >= 0:
                    length = min(remaining, (previous - first + 1) * 512)
                    spans.append(view[(first + 1) * 512 : (first + 1) * 512 + length])
                    remaining -= length
                first = sid
            previous = sid
        if first >= 0:
            spans.append(view[(first + 1) * 512 : (first + 1) * 512 + remaining])
        return b"".join(spans)

    def _directory_entry(self, raw: bytes) -> _DirectoryEntry:
        kind, color = raw[66:68]
        if kind == 0:
            return _DirectoryEntry("", 0, 0, FREE, FREE, FREE, b"", 0, 0, 0, 0, 0)
        length = struct.unpack_from("<H", raw, 64)[0]
        _require(
            kind in (1, 2, 5)
            and color in (0, 1)
            and 2 <= length <= 64
            and length % 2 == 0
            and raw[length - 2 : length] == b"\0\0",
            "invalid directory type/name",
        )
        name = raw[: length - 2].decode("utf-16le", errors="strict")
        _require(bool(name) and not any(c in name for c in "\0/\\:!"), "invalid object name")
        # The pinned native writer compares scalar characters, so supplementary
        # names remain outside its qualified profile even though CFB defines keys.
        _require(
            not any(
                0xD800 <= unit <= 0xDFFF for (unit,) in struct.iter_unpack("<H", raw[: length - 2])
            ),
            "supplementary Unicode names are not qualified",
        )
        left, right, child = struct.unpack_from("<III", raw, 68)
        state, created, modified, start, size = struct.unpack_from("<IQQIQ", raw, 96)
        if kind == 1:
            _require(start == size == 0, "storage contains stream allocation fields")
        if kind == 2:
            _require(
                child == FREE and raw[80:96] == b"\0" * 16 and created == modified == 0,
                "invalid stream directory metadata",
            )
        _require(size <= MAX_BYTES, "stream size limit exceeded")
        return _DirectoryEntry(
            name, kind, color, left, right, child, raw[80:96], state, created, modified, start, size
        )

    def _add_entry(self, path: Path, entry: _DirectoryEntry) -> None:
        payload = b""
        if entry.kind == 2:
            if entry.size < 4096:
                payload = self._mini_payload(entry.start, entry.size)
            else:
                payload = self._payload(entry.start, entry.size, repr(path))
            self.streams[path] = payload
        checksum = hashlib.sha256(payload).hexdigest() if entry.kind == 2 else ""
        self.entries.append(
            OleEntry(
                path,
                entry.name,
                entry.kind,
                entry.clsid,
                entry.state,
                entry.created,
                entry.modified,
                entry.size if entry.kind == 2 else 0,
                checksum,
            )
        )

    def _mini_payload(self, start: int, size: int) -> bytes:
        count = (size + 63) // 64
        chunks = []
        for _ in range(count):
            _require(
                0 <= start < len(self.minifat) and (start + 1) * 64 <= len(self.mini_data),
                "mini-sector reference outside carrier",
            )
            _require(start not in self.mini_owners, "overlapping or cyclic mini-sector chains")
            self.mini_owners.add(start)
            chunks.append(self.mini_data[start * 64 : (start + 1) * 64])
            start = self.minifat[start]
        _require(start in ((END, FREE) if count == 0 else (END,)), "mini chain length mismatch")
        return b"".join(chunks)[:size]

    def _tree(self, sid: int, parent: Path, depth: int) -> None:
        if sid == FREE:
            return
        _require(len(parent) < MAX_DEPTH and depth < 128, "directory nesting limit exceeded")
        _require(0 < sid < len(self.directory), "invalid directory tree root")
        pending: List[Tuple[int, Optional[NameKey], Optional[NameKey], bool, int]] = [
            (sid, None, None, False, depth),
        ]
        while pending:
            index, lower, upper, red_parent, level = pending.pop()
            if index == FREE:
                continue
            _require(level < 128, "directory traversal depth limit exceeded")
            _require(
                0 < index < len(self.directory) and index not in self.seen,
                "invalid, shared or cyclic directory reference",
            )
            self.seen.add(index)
            entry = self.directory[index]
            _require(entry.kind in (1, 2), "non-object in live directory tree")
            key = cfb_name_key(entry.name)
            _require(
                (lower is None or lower < key) and (upper is None or key < upper),
                "duplicate name or directory ordering violation",
            )
            _require(not red_parent or entry.color == 1, "consecutive red directory nodes")
            path = parent + (entry.name,)
            self._add_entry(path, entry)
            pending.append((entry.right, key, upper, entry.color == 0, level + 1))
            pending.append((entry.left, lower, key, entry.color == 0, level + 1))
            if entry.kind == 1:
                self._tree(entry.child, path, level + 1)

    def _complete_graph(self) -> None:
        _require(
            all(e.kind == 0 or i in self.seen for i, e in enumerate(self.directory)),
            "unreachable allocated directory object",
        )
        _require(
            all(value == FREE or i in self.owners for i, value in enumerate(self.fat)),
            "unexplained sector allocation",
        )
        _require(
            all(value == FREE or i in self.mini_owners for i, value in enumerate(self.minifat)),
            "unexplained mini-sector allocation",
        )
        _require(sum(e.size for e in self.entries) <= MAX_BYTES, "aggregate stream limit exceeded")


def read_compound(path: str) -> CompoundFile:
    """Read within a fixed memory/sector budget, without extraction or side effects."""
    _require(os.path.getsize(path) <= MAX_BYTES, "128 MiB input limit exceeded")
    with open(path, "rb") as source:
        data = source.read(MAX_BYTES + 1)
    return CompoundFile(data)


def _independent_blocks(reader: object, parts: Path, size: int) -> Iterator[bytes]:
    """Hash large streams through olefile's independently parsed FAT and sectors.

    olefile 0.47 openstream materializes every sector and then the entire stream.
    Keep its normal reader for small/mini streams; use its own directory/FAT/
    getsect reader incrementally for large regular streams, with exact chain
    length, cycle and termination checks. No CompoundFile allocations are used.
    """
    from typing import Any, cast

    ole = cast(Any, reader)
    if size < 1024 * 1024:
        with ole.openstream(list(parts)) as stream:
            yield from iter(lambda: stream.read(65536), b"")
        return
    entry = ole.direntries[ole._find(list(parts))]
    sector, remaining, seen = entry.isectStart, size, set()
    _require(
        ole.sectorsize == 512 and size >= ole.minisectorcutoff,
        "independent regular stream geometry differs",
    )
    for _ in range((size + 511) // 512):
        _require(
            0 <= sector < len(ole.fat) and sector not in seen,
            "independent FAT stream cycle/bounds disagreement",
        )
        seen.add(sector)
        block = ole.getsect(sector)
        _require(len(block) == 512, "independent stream sector truncated")
        take = min(remaining, 512)
        yield block[:take]
        remaining -= take
        sector = int(ole.fat[sector]) & 0xFFFFFFFF
    _require(remaining == 0 and sector == END, "independent stream chain length differs")


def independent_manifest(path: Union[str, BinaryIO], compound: CompoundFile) -> OleManifest:
    """Compare olefile's complete storage/stream view, lengths and raw metadata."""
    try:
        import olefile
    except ImportError as exc:
        raise ValueError("Install filerepack[ole] for independent OLE verification") from exc
    # Independently read the caller's source. The exact legacy root correction
    # is a seekable field view, avoiding a second full-file normalization copy.
    view = root_name_view(path) if compound.root_name_normalized else nullcontext(path)
    with (
        view as source,
        olefile.OleFileIO(source, raise_defects=olefile.DEFECT_INCORRECT) as reader,
    ):
        expected = {entry.path: entry for entry in compound.manifest.entries}
        paths = {tuple(parts) for parts in reader.listdir(streams=True, storages=True)} | {()}
        _require(paths == set(expected), "independent directory reader disagreement")
        for parts, entry in expected.items():
            sid = reader._find(list(parts)) if parts else 0
            raw = reader.direntries[sid]
            # olefile exposes GUIDs as strings; compare raw bytes without timestamp conversions.
            actual_clsid = uuid.UUID(raw.clsid).bytes_le if raw.clsid else b"\0" * 16
            _require(
                (
                    raw.name,
                    raw.entry_type,
                    actual_clsid,
                    raw.dwUserFlags,
                    raw.createTime,
                    raw.modifyTime,
                )
                == (
                    entry.name,
                    entry.kind,
                    entry.clsid,
                    entry.state,
                    entry.created,
                    entry.modified,
                ),
                "independent directory metadata disagreement",
            )
            if entry.kind == 2:
                _require(
                    reader.get_size(list(parts)) == entry.size, "independent stream size differs"
                )
                checksum, total = hashlib.sha256(), 0
                for block in _independent_blocks(reader, parts, entry.size):
                    total += len(block)
                    _require(total <= entry.size, "independent stream read exceeded length")
                    checksum.update(block)
                _require(
                    total == entry.size and checksum.hexdigest() == entry.sha256,
                    "independent stream bytes differ",
                )
        _require(not reader.parsing_issues, "independent reader reported structural defects")
    return compound.manifest


def ole_fingerprint(path: str) -> OleManifest:
    compound = read_compound(path)
    return independent_manifest(path, compound)
