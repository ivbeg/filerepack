"""Bounded legacy Office signature locations; VBA payloads remain opaque.

MS-OSHARED 1.3.4 and 2.3.3.2.2.1, MS-OLEPS 2.19-2.21,
MS-DOC 2.5.6 / 2.9.298. No macro code is decoded, loaded or executed.
"""

import struct
import uuid
from typing import Set

from .ole_verify import CompoundFile

MAX_PROTECTION_BYTES = 4 * 1024 * 1024
MAX_PROPERTIES = 4096
DOCSUMMARY = uuid.UUID("d5cdd502-2e9c-101b-9397-08002b2cf9ae").bytes_le
USERDEFINED = uuid.UUID("d5cdd505-2e9c-101b-9397-08002b2cf9ae").bytes_le
MACRO_NAMES = {"macros", "vba", "_vba_project_cur", "_vba_project"}


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _property_ids(data: bytes, start: int, end: int) -> Set[int]:
    """Validate the complete property index, including duplicate/overlapping offsets."""
    count = struct.unpack_from("<I", data, start + 4)[0]
    first = 8 + count * 8
    _require(
        count <= MAX_PROPERTIES and first <= end - start, "OLE property count limit/truncation"
    )
    identifiers: Set[int] = set()
    offsets: Set[int] = set()
    for index in range(count):
        identifier, offset = struct.unpack_from("<II", data, start + 8 + index * 8)
        # Office's unaligned string/vector types can put later properties off a
        # four-byte boundary. Keep the exact offsets; the index must still be complete.
        _require(
            identifier not in identifiers
            and offset not in offsets
            and offset >= first
            and start + offset + 4 <= end,
            "Invalid/duplicate OLE property identifier or offset",
        )
        identifiers.add(identifier)
        offsets.add(offset)
    ordered = sorted(offsets)
    _require(
        all(a + 4 <= b for a, b in zip(ordered, ordered[1:])), "Overlapping OLE property offsets"
    )
    return identifiers


def check_document_summary(data: bytes) -> None:
    """Reject GKPIDDSI_DIGSIG (0x18), including malformed/unknown property sections."""
    _require(
        48 <= len(data) <= MAX_PROTECTION_BYTES,
        "DocumentSummaryInformation protection size limit/truncation",
    )
    order, version = struct.unpack_from("<HH", data)
    count = struct.unpack_from("<I", data, 24)[0]
    _require(
        order == 0xFFFE and version in (0, 1) and count in (1, 2),
        "Unknown DocumentSummaryInformation protection format",
    )
    previous = 28 + 20 * count
    _require(previous <= len(data), "Truncated OLE property section directory")
    for index in range(count):
        entry = 28 + 20 * index
        fmtid = data[entry : entry + 16]
        _require(
            fmtid == (DOCSUMMARY if index == 0 else USERDEFINED),
            "Unknown DocumentSummaryInformation property section",
        )
        start = struct.unpack_from("<I", data, entry + 16)[0]
        _require(
            start >= previous and start % 4 == 0 and start + 8 <= len(data),
            "Invalid/overlapping OLE property section offset",
        )
        _require(not any(data[previous:start]), "Nonzero OLE property section padding")
        size = struct.unpack_from("<I", data, start)[0]
        end = start + size
        _require(size >= 8 and size % 4 == 0 and end <= len(data), "Truncated OLE property section")
        identifiers = _property_ids(data, start, end)
        if index == 0:
            _require(
                0 not in identifiers and 1 in identifiers,
                "Invalid DocumentSummaryInformation property index",
            )
            _require(0x18 not in identifiers, "Signed VBA project (GKPIDDSI_DIGSIG)")
        previous = end
    _require(not any(data[previous:]), "Nonzero OLE property stream padding")


def check_word_variables(table: bytes, start: int, size: int) -> None:
    """Check the FIB-addressed StwUser names and parallel Xst values exactly."""
    if size == 0:
        return  # fcStwUser is undefined when lcbStwUser is zero.
    _require(
        6 <= size <= MAX_PROTECTION_BYTES and 0 <= start and start + size <= len(table),
        "Word StwUser protection size limit/truncation",
    )
    data = table[start : start + size]
    extended, count, extra = struct.unpack_from("<HHH", data)
    _require(
        extended == 0xFFFF and extra == 4 and count <= MAX_PROPERTIES,
        "Unknown Word StwUser protection structure",
    )
    offset = 6
    seen: Set[str] = set()
    for _ in range(count):
        _require(offset + 2 <= size, "Truncated Word StwUser name length")
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        end = offset + length * 2
        _require(0 < length < 0xFFFF and end + extra <= size, "Truncated Word StwUser name")
        name = data[offset:end].decode("utf-16le", errors="strict").casefold()
        _require("\0" not in name, "Invalid Word StwUser name")
        _require(name not in seen, "Duplicate Word StwUser name")
        _require(name not in ("sign", "sigagile", "sigv3"), "Signed Word VBA project (StwUser)")
        seen.add(name)
        offset = end + extra
    for _ in range(count):
        _require(offset + 2 <= size, "Truncated Word StwUser value length")
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2 + length * 2
        _require(offset <= size, "Truncated Word StwUser value")
    _require(offset == size, "Unexplained Word StwUser bytes")


def check_macro_projects(compound: CompoundFile, profile: str) -> bool:
    """Qualify one canonical project after its host signature/reference checks.

    The internal ppt-project profile is for an already resolved nested PPT storage.
    Project password/editor-lock metadata stays opaque along with all project bytes.
    """
    entries = {tuple(part.lower() for part in entry.path): entry for entry in compound.entries}
    markers = {path for path, entry in entries.items() if entry.name.lower() in MACRO_NAMES}
    if profile == "pub" and markers == {("vba",)}:
        _require(
            entries[("vba",)].kind == 1 and not any(len(p) > 1 and p[0] == "vba" for p in entries),
            "Publisher macro project is not qualified",
        )
        return False
    if not markers:
        return False
    _require(
        profile in ("doc", "xls", "ppt-project"),
        "VBA project layout is not qualified for this profile",
    )
    project = (
        ()
        if profile == "ppt-project"
        else (("macros",) if profile == "doc" else ("_vba_project_cur",))
    )
    vba = project + ("vba",)
    cache = vba + ("_vba_project",)
    expected = {vba, cache} | ({project} if project else set())
    _require(
        markers == expected
        and entries[project].kind == (1 if project else 5)
        and entries[vba].kind == 1
        and entries[cache].kind == 2,
        "Unknown/embedded VBA project layout; signature status is not qualified",
    )
    required = (project + ("project",), vba + ("dir",), cache)
    _require(
        all(path in entries and entries[path].kind == 2 for path in required),
        "Incomplete VBA project layout; signature status is not qualified",
    )
    streams = {
        tuple(part.lower() for part in path): payload for path, payload in compound.streams.items()
    }
    _require(
        bool(streams[required[0]])
        and len(streams[cache]) >= 7
        and streams[cache][:2] == b"\xcc\x61"
        and streams[cache][4] == 0
        and streams[required[1]][:1] == b"\x01",
        "Unknown VBA project headers; signature status is not qualified",
    )
    return True


def check_container_protection(compound: CompoundFile) -> None:
    """Check outer Office and nested project protection with the same fail-closed rules."""
    for entry in compound.entries:
        name = entry.name.lower()
        _require(
            not (
                "signature" in name
                or name in ("encryptioninfo", "encryptedpackage")
                or name == "\x06dataspaces"
            ),
            "Signed/encrypted/rights-managed OLE document",
        )
        if name == "\x05documentsummaryinformation":
            _require(entry.kind == 2, "Non-simple DocumentSummaryInformation is not qualified")
            check_document_summary(compound.streams[entry.path])
