#!/usr/bin/env python3
"""Read-only CFB directory diagnostics for .ppt files (Python 3.9+, stdlib only).

This is NOT a complete CFB/PPT validator or a filerepack patch. It inspects the
outer CFB directory, not compressed embedded OLE objects or PPT record offsets.
The presence of unused entries is normal, not proof of a filerepack bug.

Specification: MS-CFB sections 2.6.1 and 2.6.3:
https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/60fe8611-66c3-496b-b70d-a504c94c9ace
https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/b37413bb-f3ef-4adc-b18e-29bddd62c26e

Exit status: 0 = no issues in the limited checks; 1 = issues/errors; 2 = usage.
Files are opened only in 'rb' mode. No streams are executed or modified.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct
import sys
from typing import BinaryIO, Iterator

MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
FREE = 0xFFFFFFFF
END = 0xFFFFFFFE
FAT_SECTOR = 0xFFFFFFFD
DIFAT_SECTOR = 0xFFFFFFFC
ACTIVE_TYPES = {1, 2, 5}
MAX_DIRECTORY_BYTES = 64 * 1024 * 1024
MAX_FAT_BYTES = 64 * 1024 * 1024


class FormatError(ValueError):
    """Invalid or unsupported structure encountered by these limited checks."""


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


class DirectoryReader:
    def __init__(self, file: BinaryIO) -> None:
        self.file = file
        self.size = os.fstat(file.fileno()).st_size
        header = file.read(512)
        if len(header) != 512 or header[:8] != MAGIC:
            raise FormatError("Not a CFB/OLE file (or truncated header)")
        self.version = u16(header, 26)
        shift = u16(header, 30)
        if u16(header, 28) != 0xFFFE:
            raise FormatError("Unsupported byte order")
        if (self.version, shift) not in {(3, 9), (4, 12)}:
            raise FormatError(f"Unsupported version/sector shift: {self.version}/{shift}")
        self.sector_size = 1 << shift
        if self.size < self.sector_size or self.size % self.sector_size:
            raise FormatError("File length is not a whole number of CFB sectors")
        self.sector_count = self.size // self.sector_size - 1
        fat_count = u32(header, 44)
        difat_count = u32(header, 72)
        if not 0 < fat_count <= self.sector_count:
            raise FormatError("Invalid FAT sector count")
        if difat_count > self.sector_count:
            raise FormatError("Invalid DIFAT sector count")
        if fat_count * self.sector_size > MAX_FAT_BYTES:
            raise FormatError("Diagnostic resource limit: FAT exceeds 64 MiB")
        fat_ids = [v for (v,) in struct.iter_unpack("<I", header[76:512]) if v != FREE]
        difat_seen: set[int] = set()
        next_difat = u32(header, 68)
        for _ in range(difat_count):
            if next_difat in difat_seen:
                raise FormatError("Cycle in DIFAT chain")
            difat_seen.add(next_difat)
            sector = self.read_sector(next_difat)
            fat_ids.extend(v for (v,) in struct.iter_unpack("<I", sector[:-4]) if v != FREE)
            next_difat = u32(sector, self.sector_size - 4)
        if difat_count and next_difat != END:
            raise FormatError("DIFAT chain does not end at declared length")
        if len(fat_ids) != fat_count or len(set(fat_ids)) != fat_count:
            raise FormatError("FAT count mismatch or duplicate FAT sectors")
        if set(fat_ids) & difat_seen:
            raise FormatError("Overlapping FAT and DIFAT sectors")
        self.fat = b"".join(self.read_sector(sid) for sid in fat_ids)
        if len(self.fat) // 4 < self.sector_count:
            raise FormatError("FAT is too short for the file")
        for sid in fat_ids:
            if u32(self.fat, sid * 4) != FAT_SECTOR:
                raise FormatError(f"FAT sector {sid} lacks FATSECT marker")
        for sid in difat_seen:
            if u32(self.fat, sid * 4) != DIFAT_SECTOR:
                raise FormatError(f"DIFAT sector {sid} lacks DIFSECT marker")
        self.first_directory = u32(header, 48)
        self.reserved_sectors = set(fat_ids) | difat_seen

    def read_sector(self, sid: int) -> bytes:
        if not 0 <= sid < self.sector_count:
            raise FormatError(f"Sector ID out of bounds: 0x{sid:08x}")
        self.file.seek((sid + 1) * self.sector_size)
        data = self.file.read(self.sector_size)
        if len(data) != self.sector_size:
            raise FormatError(f"Truncated sector {sid}")
        return data

    def entries(self) -> Iterator[tuple[int, int, bytes]]:
        sid = self.first_directory
        seen: set[int] = set()
        entry_id = 0
        while sid != END:
            if sid in seen:
                raise FormatError("Cycle in directory sector chain")
            if sid in self.reserved_sectors:
                raise FormatError("Directory overlaps FAT/DIFAT")
            seen.add(sid)
            if len(seen) * self.sector_size > MAX_DIRECTORY_BYTES:
                raise FormatError("Diagnostic resource limit: directory exceeds 64 MiB")
            sector = self.read_sector(sid)
            for offset in range(0, self.sector_size, 128):
                yield entry_id, (sid + 1) * self.sector_size + offset, sector[offset:offset + 128]
                entry_id += 1
            sid = u32(self.fat, sid * 4)


def inspect(path: Path, example_limit: int = 8) -> dict:
    result: dict = {
        "file": str(path), "slots": 0, "active": 0, "unused": 0,
        "unused_noncanonical": 0, "unused_examples": [],
        "issues": [], "issue_count": 0,
    }

    def issue(text: str) -> None:
        result["issue_count"] += 1
        if len(result["issues"]) < example_limit:
            result["issues"].append(text)

    canonical_free = bytearray(128)
    canonical_free[68:80] = b"\xff" * 12
    types: list[int] = []
    links: list[tuple[int, int, int, int]] = []
    with path.open("rb") as file:
        reader = DirectoryReader(file)
        result["version"] = reader.version
        result["sector_size"] = reader.sector_size
        for entry_id, offset, raw in reader.entries():
            name_len = u16(raw, 64)
            obj_type = raw[66]
            types.append(obj_type)
            result["slots"] += 1
            if obj_type == 0:
                result["unused"] += 1
                canonical = raw == canonical_free
                if not canonical:
                    result["unused_noncanonical"] += 1
                if len(result["unused_examples"]) < example_limit:
                    result["unused_examples"].append({
                        "entry_id": entry_id, "file_offset": offset,
                        "object_type": obj_type, "name_length": name_len,
                        "canonical": canonical,
                    })
                continue
            if obj_type not in ACTIVE_TYPES:
                issue(f"entry={entry_id} offset=0x{offset:x}: unknown type=0x{obj_type:02x}")
                continue
            result["active"] += 1
            if (entry_id == 0) != (obj_type == 5):
                issue(f"entry={entry_id}: root must be entry 0 and only entry 0")
            if name_len < 2 or name_len > 64 or name_len % 2:
                issue(f"entry={entry_id} type={obj_type}: invalid name_length={name_len}")
            elif raw[name_len - 2:name_len] != b"\x00\x00":
                issue(f"entry={entry_id}: missing UTF-16 name terminator")
            else:
                try:
                    name = raw[:name_len - 2].decode("utf-16-le")
                    if not name or "\x00" in name or any(c in name for c in "/\\:!"):
                        issue(f"entry={entry_id}: empty or prohibited name={name!r}")
                except UnicodeDecodeError:
                    issue(f"entry={entry_id}: invalid UTF-16 name")
            if raw[67] not in (0, 1):
                issue(f"entry={entry_id}: invalid color={raw[67]}")
            left, right, child = struct.unpack_from("<III", raw, 68)
            links.append((entry_id, left, right, child))
            if obj_type == 2 and child != FREE:
                issue(f"entry={entry_id}: stream has a child pointer")
    if not types or types[0] != 5:
        issue("Missing root storage at entry 0")
    for entry_id, left, right, child in links:
        for label, target in (("left", left), ("right", right), ("child", child)):
            if target == FREE:
                continue
            if target >= len(types):
                issue(f"entry={entry_id}: {label} points outside directory: {target}")
            elif target == 0 or types[target] not in (1, 2):
                issue(f"entry={entry_id}: {label} points to non-storage/non-stream entry={target}")
    result["has_canonical_unused_entries"] = result["unused"] > result["unused_noncanonical"]
    return result


def walk_ppt(root: Path) -> Iterator[Path]:
    def onerror(error: OSError) -> None:
        raise error
    for directory, _, filenames in os.walk(root, followlinks=False, onerror=onerror):
        for name in sorted(filenames):
            path = Path(directory) / name
            if path.suffix.lower() == ".ppt" and not path.is_symlink():
                yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="One CFB file or a directory to scan recursively for .ppt")
    parser.add_argument("--json", action="store_true", help="Emit one JSON object per file")
    args = parser.parse_args()
    root = args.path.expanduser()
    if not root.exists():
        parser.error(f"Path does not exist: {root}")
    paths = walk_ppt(root) if root.is_dir() else iter([root])
    count = 0
    failed = False
    try:
        for path in paths:
            count += 1
            try:
                result = inspect(path)
                failed |= bool(result["issue_count"] or result["unused_noncanonical"])
            except (OSError, FormatError) as exc:
                result = {"file": str(path), "error": str(exc)}
                failed = True
            if args.json:
                print(json.dumps(result, ensure_ascii=True))
            else:
                print(json.dumps(str(path), ensure_ascii=True))
                if "error" in result:
                    print(f"  ERROR: {result['error']}")
                    continue
                print(f"  CFB v{result['version']}, sector_size={result['sector_size']}, "
                      f"slots={result['slots']}, active={result['active']}, unused={result['unused']}")
                print(f"  active/root/link issues={result['issue_count']}; "
                      f"noncanonical unused slots={result['unused_noncanonical']}")
                for item in result["unused_examples"]:
                    print(f"  unused entry={item['entry_id']} offset=0x{item['file_offset']:x} "
                          f"type=0 name_length={item['name_length']} canonical={item['canonical']}")
                for item in result["issues"]:
                    print(f"  ISSUE: {item}")
        if not count:
            print("No .ppt files found.", file=sys.stderr)
            return 2
    except OSError as exc:
        print(f"Directory scan failed: {exc}", file=sys.stderr)
        return 1
    if not args.json:
        print(f"Scanned {count} file(s). Limited outer-directory checks only; not a losslessness test.")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
