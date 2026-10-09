"""Bounded PowerPoint profile and canonical unsigned VBA storage qualification.

MS-PPT 2.1.2, 2.3.3-4, 2.4.10-11, 2.10.40-42. All encoded records stay unchanged.
"""

import io
import struct
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .ole_protection import check_container_protection, check_macro_projects
from .ole_verify import CompoundFile, independent_manifest

MAX_RECORDS = 200000
MAX_VBA_BYTES = 16 * 1024 * 1024


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


@dataclass(frozen=True)
class PptRecord:
    kind: int
    size: int
    flags: int
    parent: Optional[int]


def read_records(data: bytes) -> Dict[int, PptRecord]:
    records: Dict[int, PptRecord] = {}
    pending: List[Tuple[int, int, Optional[int], int]] = [(0, len(data), None, 0)]
    while pending:
        start, limit, parent, depth = pending.pop()
        _require(depth <= 32, "PowerPoint record nesting limit exceeded")
        while start < limit:
            if parent is None and data[start : start + 8] == b"\0" * 8:
                _require(not any(data[start:limit]), "Invalid PowerPoint tail padding")
                break
            _require(
                start + 8 <= limit and len(records) < MAX_RECORDS,
                "PowerPoint record limit/truncation",
            )
            flags, kind, size = struct.unpack_from("<HHI", data, start)
            end = start + 8 + size
            _require(end <= limit, "Truncated PowerPoint record")
            records[start] = PptRecord(kind, size, flags, parent)
            _require(kind != 12052, "PowerPoint encryption is not qualified")
            if flags & 15 == 15:
                pending.append((start + 8, end, start, depth + 1))
            start = end
    return records


def project_bytes(data: bytes, offset: int, record: PptRecord) -> bytes:
    """Decode only a resolved storage wrapper, with a hard limit and exact termination."""
    _require(
        record.kind == 4113 and record.parent is None and record.flags in (0, 0x10),
        "Unknown PowerPoint VBA storage wrapper",
    )
    _require(0 < record.size <= MAX_VBA_BYTES, "PowerPoint VBA encoded byte limit")
    payload = data[offset + 8 : offset + 8 + record.size]
    _require(len(payload) == record.size, "Truncated PowerPoint VBA storage wrapper")
    if record.flags == 0:
        return payload
    _require(len(payload) >= 4, "Truncated PowerPoint VBA compressed length")
    size = struct.unpack_from("<I", payload)[0]
    _require(512 <= size <= MAX_VBA_BYTES, "PowerPoint VBA decoded byte limit")
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(payload[4:], size + 1)
    except zlib.error as exc:
        raise ValueError("Invalid PowerPoint VBA zlib storage") from exc
    _require(
        len(decoded) == size
        and decoder.eof
        and not decoder.unused_data
        and not decoder.unconsumed_tail,
        "PowerPoint VBA length/termination mismatch",
    )
    return decoded


def _check_vba(
    data: bytes, records: Dict[int, PptRecord], persist: Dict[int, int], document: int, edits: int
) -> bool:
    containers = [pos for pos, record in records.items() if record.kind == 1023]
    atoms = [pos for pos, record in records.items() if record.kind == 1024]
    if not containers and not atoms:
        return False
    _require(
        edits == 1 and len(containers) == len(atoms) == 1,
        "PowerPoint VBA history/multiple-info layout is not qualified",
    )
    container, atom = containers[0], atoms[0]
    info = records[container]
    parent = records.get(info.parent) if info.parent is not None else None
    lists = [
        pos for pos, record in records.items() if record.kind == 2000 and record.parent == document
    ]
    _require(
        info.flags == 0x1F
        and info.size == 20
        and parent is not None
        and parent.kind == 2000
        and parent.flags == 0xF
        and parent.parent == document
        and lists == [info.parent]
        and records[atom] == PptRecord(1024, 12, 2, container)
        and atom == container + 8,
        "Unknown PowerPoint VBAInfoContainer/Atom layout",
    )
    identifier, has_macros, version = struct.unpack_from("<III", data, atom + 8)
    if identifier == 0 and has_macros == 0 and version == 2:
        _require(
            0 not in persist and not any(record.kind == 4113 for record in records.values()),
            "Unexpected PowerPoint VBA storage for empty project flags",
        )
        return False
    _require(
        identifier > 0 and has_macros == 1 and version == 2,
        "Empty/unknown PowerPoint VBA project flags",
    )
    target = persist.get(identifier)
    _require(
        target is not None and sum(pos == target for pos in persist.values()) == 1,
        "Missing/ambiguous PowerPoint VBA persist reference",
    )
    assert target is not None
    raw = project_bytes(data, target, records[target])
    nested = CompoundFile(raw)
    check_container_protection(nested)
    _require(check_macro_projects(nested, "ppt-project"), "Missing PowerPoint VBA project")
    independent_manifest(io.BytesIO(raw), nested)
    return True


def check_ppt_profile(compound: CompoundFile) -> bool:
    """Validate the edit/persist graph; return whether a qualified VBA project exists."""
    current = compound.streams.get(("Current User",), b"")
    data = compound.streams.get(("PowerPoint Document",), b"")
    _require(
        len(current) >= 28 and struct.unpack_from("<H", current, 2)[0] == 0xFF6,
        "Missing/truncated PowerPoint Current User",
    )
    size, token, edit = struct.unpack_from("<III", current, 8)
    _require(token != 0xF3D1C4DF, "Encrypted PowerPoint document")
    _require(size == 20 and token == 0xE391C05F, "Unknown PowerPoint protection/profile")
    _require(
        8 + struct.unpack_from("<I", current, 4)[0] <= len(current),
        "Truncated PowerPoint CurrentUserAtom",
    )
    records = read_records(data)
    seen: Set[int] = set()
    persist: Dict[int, int] = {}
    document_id = 0
    while edit:
        record = records.get(edit)
        _require(
            edit not in seen
            and len(seen) < 4096
            and record is not None
            and record.kind == 0xFF5
            and record.size in (28, 32)
            and record.flags == 0
            and record.parent is None,
            "Invalid PowerPoint edit chain",
        )
        assert record is not None
        seen.add(edit)
        previous, directory, doc_id, seed = struct.unpack_from("<IIII", data, edit + 16)
        if not document_id:
            document_id = doc_id
        if record.size == 32:
            _require(struct.unpack_from("<I", data, edit + 36)[0] == 0, "Encrypted PowerPoint edit")
        index = records.get(directory)
        _require(
            previous < directory < edit
            and index is not None
            and index.kind == 0x1772
            and index.flags == 0
            and index.parent is None,
            "Invalid PowerPoint persist directory offset",
        )
        assert index is not None
        position, end = directory + 8, directory + 8 + index.size
        identifiers: Set[int] = set()
        while position < end:
            _require(position + 4 <= end, "Truncated PowerPoint persist entry")
            descriptor = struct.unpack_from("<I", data, position)[0]
            first, count = descriptor & 0xFFFFF, descriptor >> 20
            position += 4
            _require(
                count > 0
                and first > 0
                and first + count <= seed + 1
                and position + count * 4 <= end,
                "Invalid PowerPoint persist entry",
            )
            for identifier in range(first, first + count):
                target = struct.unpack_from("<I", data, position)[0]
                _require(identifier not in identifiers, "Duplicate PowerPoint persist identifier")
                identifiers.add(identifier)
                _require(
                    target < directory and target in records and records[target].parent is None,
                    "PowerPoint persist reference outside top-level records",
                )
                persist.setdefault(identifier, target)
                position += 4
        edit = previous
    document = persist.get(document_id)
    _require(
        bool(seen)
        and document is not None
        and records[document].kind == 1000
        and records[document].flags == 0xF,
        "Missing PowerPoint document persist object",
    )
    assert document is not None
    return _check_vba(data, records, persist, document, len(seen))
