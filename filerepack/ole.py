"""Qualified legacy Office CFB compaction; application streams stay unchanged."""

import logging
import os
import struct
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from . import candidates as tx
from .commands import check_command
from .models import PackResult
from .ole_ppt import check_ppt_profile
from .ole_protection import check_container_protection, check_macro_projects, check_word_variables
from .ole_verify import CompoundFile, independent_manifest, read_compound
from .tools import resolve_tool
from .transactions import guard_packer

MAX_RECORDS = 200000
OLE_EXTENSIONS = {
    "doc": "doc",
    "dot": "doc",
    "xls": "xls",
    "xlt": "xls",
    "xla": "xls",
    "ppt": "ppt",
    "pot": "ppt",
    "pps": "ppt",
    "msg": "msg",
    "vsd": "vsd",
    "pub": "pub",
    "mpp": "mpp",
    "msi": "msi",
    "hwp": "hwp",
}


@dataclass(frozen=True)
class OleInspection:
    eligible: bool
    profile: str = ""
    reason: str = ""
    stream_bytes: int = 0
    free_sector_bytes: int = 0  # Allocation estimate, never measured savings.
    unsigned_vba: bool = False


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _word_profile(compound: CompoundFile) -> None:
    data = compound.streams.get(("WordDocument",), b"")
    _require(len(data) >= 34, "Missing/truncated WordDocument FIB")
    ident, version = struct.unpack_from("<HH", data)
    _require(
        ident == 0xA5EC and version in (0xC1, 0xD9, 0x101, 0x10C, 0x112),
        "Unsupported Word binary version",
    )
    flags = struct.unpack_from("<H", data, 10)[0]
    _require(not flags & 0x8100, "Encrypted/obfuscated Word document")
    table = "1Table" if flags & 0x200 else "0Table"
    _require((table,) in compound.streams, "Missing selected Word table stream")
    offset = 32
    fields = 0
    for minimum, unit in ((14, 2), (22, 4), (93, 8), (0, 2)):
        _require(offset + 2 <= len(data), "Truncated Word FIB length field")
        count = struct.unpack_from("<H", data, offset)[0]
        _require(count >= minimum, "Unsupported Word FIB structure")
        if unit == 8:
            fields = offset + 2
        offset += 2 + count * unit
        _require(offset <= len(data), "Truncated Word FIB structure")
    # FibRgFcLcb97 pair 60 is fcStwUser/lcbStwUser, also retained by later versions.
    start, size = struct.unpack_from("<II", data, fields + 60 * 8)
    check_word_variables(compound.streams[(table,)], start, size)


def _xls_profile(compound: CompoundFile) -> None:
    data = compound.streams.get(("Workbook",), b"")
    _require(
        len(data) >= 20 and struct.unpack_from("<HHHH", data) == (0x809, 16, 0x600, 5),
        "Missing BIFF8 Workbook globals BOF",
    )
    offset, nesting, records = 0, 0, 0
    sheets: List[int] = []
    while offset < len(data):
        if not nesting and data[offset : offset + 4] == b"\0" * 4:
            _require(not any(data[offset:]), "Invalid Excel tail padding")
            break
        _require(offset + 4 <= len(data) and records < MAX_RECORDS, "BIFF record limit/truncation")
        kind, size = struct.unpack_from("<HH", data, offset)
        start, end = offset + 4, offset + 4 + size
        _require(size <= 8224 and end <= len(data), "Truncated/oversized BIFF record")
        _require(kind != 0x2F, "Encrypted/obfuscated Excel workbook (FilePass)")
        if kind == 0x809:
            _require(
                size == 16 and struct.unpack_from("<H", data, start)[0] == 0x600,
                "Unsupported Excel BOF",
            )
            nesting += 1
        elif kind == 0xA:
            _require(size == 0 and nesting > 0, "Invalid Excel EOF")
            nesting -= 1
        else:
            _require(nesting > 0, "Excel record outside a BOF/EOF substream")
        if kind == 0x85:
            _require(size >= 8, "Truncated BoundSheet record")
            sheets.append(struct.unpack_from("<I", data, start)[0])
        records += 1
        offset = end
    _require(nesting == 0 and bool(sheets), "Incomplete Excel substreams or missing sheets")
    for position in sheets:
        _require(
            position + 8 <= len(data) and struct.unpack_from("<H", data, position)[0] == 0x809,
            "Invalid Excel sheet offset",
        )


def _profile(compound: CompoundFile, extension: str) -> Tuple[str, bool]:
    profile = OLE_EXTENSIONS.get(extension)
    _require(profile is not None, "Unqualified OLE extension/application")
    assert profile is not None
    check_container_protection(compound)
    unsigned_vba = check_macro_projects(compound, profile)
    if profile == "ppt":
        unsigned_vba = check_ppt_profile(compound)
    else:
        from .ole_hosts import PROFILES
        from .ole_hwp import profile as hwp_profile

        validators = {"doc": _word_profile, "xls": _xls_profile, "hwp": hwp_profile, **PROFILES}
        validators[profile](compound)
    return profile, unsigned_vba


def inspect_ole(path: str) -> OleInspection:
    """Read-only eligibility and allocation estimates, without invoking a writer."""
    extension = os.path.splitext(path)[1][1:].lower()
    try:
        compound = read_compound(path)
        profile, unsigned_vba = _profile(compound, extension)
        return OleInspection(
            True,
            profile,
            stream_bytes=sum(e.size for e in compound.entries),
            free_sector_bytes=(compound.sectors - len(compound.owners)) * 512,
            unsigned_vba=unsigned_vba,
        )
    except (OSError, ValueError, struct.error) as exc:
        return OleInspection(False, reason=str(exc))


def _skip(filepath: str, reason: str) -> PackResult:
    logging.warning("OLE compaction skipped: %s", reason)
    size = os.path.getsize(filepath)
    return PackResult(
        filepath, size, size, 0.0, replaced=False, reason=reason, details={"strategy": "unchanged"}
    )


@guard_packer
def pack_ole(
    filepath: str,
    debug: bool = False,
    quiet: bool = False,
    ole_recompress: bool = False,
    ole_embedded_recompress: bool = False,
    ole_deduplicate_images: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    """Compact qualified CFB Office files and verify every stream before publication."""
    del quiet
    for name, flag in (
        ("ole_recompress", ole_recompress),
        ("ole_embedded_recompress", ole_embedded_recompress),
        ("ole_deduplicate_images", ole_deduplicate_images),
    ):
        if type(flag) is not bool:
            raise ValueError(name + " must be a boolean")
        commit[name] = flag
    extension = os.path.splitext(filepath)[1][1:].lower()
    if (
        ole_embedded_recompress
        or ole_deduplicate_images
        or OLE_EXTENSIONS.get(extension) in ("msg", "vsd", "pub", "mpp", "msi", "hwp")
    ):
        tool = resolve_tool("ole_compactor")
        if not tool:
            return _skip(filepath, "filerepack-ole writer is unavailable")
        from .ole_transform import pack_transform_records

        # Newly qualified hosts are inspected inside the isolated operation,
        # including strict compaction, with the same root budget as children.
        return pack_transform_records(filepath, tool, commit)
    if ole_recompress and extension in OLE_EXTENSIONS:
        tool = resolve_tool("ole_compactor")
        if not tool:
            return _skip(
                filepath,
                "filerepack-ole writer is unavailable; build/install "
                "tools/ole-compactor or set FILEREPACK_OLE_COMPACTOR",
            )
        if OLE_EXTENSIONS[extension] in ("doc", "xls", "ppt", "hwp"):
            from .ole_recompress import pack_art_records, pack_ppt_records, pack_hwp_records

            packer = {"ppt": pack_ppt_records, "hwp": pack_hwp_records}.get(
                OLE_EXTENSIONS[extension], pack_art_records
            )
            return packer(filepath, tool, commit)
    try:
        compound = read_compound(filepath)
        _profile(compound, extension)
        independent_manifest(filepath, compound)
    except (OSError, ValueError, struct.error) as exc:
        return _skip(filepath, str(exc))
    tool = resolve_tool("ole_compactor")
    if not tool:
        return _skip(
            filepath,
            "filerepack-ole writer is unavailable; build/install "
            "tools/ole-compactor or set FILEREPACK_OLE_COMPACTOR",
        )
    output = tx.make_temp("." + os.path.splitext(filepath)[1][1:])
    try:
        logging.debug("OLE compaction writer: %s", tool)
        if not check_command([tool, os.path.abspath(filepath), output], timeout=120):
            return _skip(filepath, "OLE compaction writer failed or exceeded its 120-second limit")
        rebuilt = read_compound(output)
        _profile(rebuilt, os.path.splitext(filepath)[1][1:].lower())
        result = tx.commit_output(
            output,
            filepath,
            os.path.getsize(filepath),
            verify="ole",
            lossless=True,
            **tx.commit_kwargs(**commit),
        )
        if result is not None:
            result.details["strategy"] = "ole-compaction"
            if result.reason.startswith("No size reduction:"):
                result.reason += (
                    "; OLE compaction only reclaims unused container space; "
                    "live document streams, text and images are retained"
                )
            return result
        return _skip(filepath, "OLE candidate failed structural or preservation verification")
    except (OSError, ValueError, struct.error) as exc:
        return _skip(filepath, "OLE candidate rejected: " + str(exc))
    finally:
        tx.remove_quietly(output)
