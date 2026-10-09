"""Passive modern torch.save ZIP recompression; never unpickle user input.

Reader gates: Python Torch 2.2.2 and 2.14.1. Storage DEFLATE needs explicit load-only;
its mmap reader rejects compressed storage. ZIP storage payloads stay 64-byte
aligned in the default profile. Unknown layouts are protected from generic ZIP.
"""

import copy
import hashlib
import os
import re
import struct
import zipfile
import zlib
from typing import Any, Dict, Optional

from .format_support import Budget, UnsupportedFormat, inflate, read_small
from .transactions import guard_packer

METADATA = {
    "data.pkl",
    "version",
    "byteorder",
    ".data/serialization_id",
    ".format_version",
    ".storage_alignment",
}


def looks_like_checkpoint(path: str) -> bool:
    """Bounded conservative routing, including unsupported TorchScript containers."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as file:
            if file.read(4) != b"PK\x03\x04":
                return False
            file.seek(max(0, size - 65558))
            tail = file.read(65558)
            end = tail.rfind(b"PK\x05\x06")
            if end < 0 or end + 22 > len(tail):
                return False
            count = int.from_bytes(tail[end + 10 : end + 12], "little")
            central_size = int.from_bytes(tail[end + 12 : end + 16], "little")
            offset = int.from_bytes(tail[end + 16 : end + 20], "little")
            if count > 100000 or central_size > 8 * 1024**2:
                # Do not expose oversized checkpoint-like ZIPs to generic recursion.
                file.seek(0)
                return b"data.pkl" in file.read(4096)
            file.seek(offset)
            directory = file.read(central_size)
            return b"/data.pkl" in directory or b"/constants.pkl" in directory
    except (OSError, ValueError):
        return False


def _extras(raw: bytes) -> Dict[int, bytes]:
    position = 0
    fields: Dict[int, bytes] = {}
    while position < len(raw):
        if position + 4 > len(raw):
            raise ValueError("truncated checkpoint ZIP extra field")
        identity, length = struct.unpack_from("<HH", raw, position)
        position += 4
        if position + length > len(raw) or identity not in (1, 0x4246) or identity in fields:
            raise UnsupportedFormat("unknown checkpoint ZIP extra field")
        fields[identity] = raw[position : position + length]
        position += length
    return fields


def _record(data: bytes, info: Any, position: int, central: int, budget: Budget) -> Any:
    start = info.header_offset
    if start != position or data[start : start + 4] != b"PK\x03\x04":
        raise ValueError("checkpoint local records are not contiguous")
    fields = struct.unpack_from("<HHHHHIIIHH", data, start + 4)
    version, flags, method, _, _, crc, compressed, length, nlen, elen = fields
    if version != info.extract_version or version not in (0, 20, 45):
        raise UnsupportedFormat("unsupported or inconsistent checkpoint ZIP reader version")
    body = start + 30 + nlen + elen
    rawname = data[start + 30 : start + 30 + nlen]
    if (
        rawname != info.filename.encode("utf-8")
        or flags != info.flag_bits
        or (method != info.compress_type)
    ):
        raise ValueError("checkpoint local/central header disagreement")
    extra = _extras(data[start + 30 + nlen : body])
    end = body + info.compress_size
    if end > central:
        raise ValueError("checkpoint member bounds overlap central directory")
    if flags & 8:
        if (
            crc not in (0, info.CRC)
            or compressed not in (0, info.compress_size, 0xFFFFFFFF)
            or (length not in (0, info.file_size, 0xFFFFFFFF))
        ):
            raise ValueError("checkpoint deferred local CRC/size mismatch")
        if compressed == 0xFFFFFFFF or length == 0xFFFFFFFF:
            values = extra.get(1, b"")
            if len(values) != 16:
                raise ValueError("missing/incomplete checkpoint local ZIP64 sizes")
            usize, csize = struct.unpack("<QQ", values)
            if usize not in (0, info.file_size) or csize not in (0, info.compress_size):
                raise ValueError("checkpoint local ZIP64/deferred sizes mismatch")
        if data[end : end + 4] != b"PK\x07\x08":
            raise ValueError("missing checkpoint ZIP data descriptor")
        width = 8 if compressed == 0xFFFFFFFF or length == 0xFFFFFFFF else 4
        descriptor = data[end + 4 : end + 8 + width * 2]
        if (
            len(descriptor) != 4 + width * 2
            or int.from_bytes(descriptor[:4], "little") != (info.CRC)
            or int.from_bytes(descriptor[4 : 4 + width], "little") != (info.compress_size)
            or int.from_bytes(descriptor[4 + width :], "little") != (info.file_size)
        ):
            raise ValueError("checkpoint ZIP descriptor mismatch")
        end += 8 + width * 2
    elif (crc, compressed, length) != (info.CRC, info.compress_size, info.file_size):
        raise ValueError("checkpoint ZIP local size/CRC mismatch")
    raw = data[body : body + info.compress_size]
    if method == 8:
        raw = inflate(raw, budget, "raw-deflate")
    else:
        budget.consume(decoded=len(raw))
    if len(raw) != info.file_size or zlib.crc32(raw) != info.CRC:
        raise ValueError("checkpoint decoded record length/CRC mismatch")
    return end, body, method, raw


def _directory(data: bytes, archive: Any, count: int) -> None:
    end = data.rfind(b"PK\x05\x06")
    if end < 0 or end + 22 != len(data):
        raise ValueError("checkpoint ZIP EOCD missing or trailing payload")
    disk, directory_disk, entries, total, size, offset, comment = struct.unpack_from(
        "<HHHHIIH", data, end + 4
    )
    if disk or directory_disk or comment or entries != total:
        raise UnsupportedFormat("split/commented checkpoint ZIP is outside the profile")
    if total == 65535 or size == 0xFFFFFFFF or offset == 0xFFFFFFFF:
        locator = end - 20
        if data[locator : locator + 4] != b"PK\x06\x07":
            raise ValueError("missing checkpoint ZIP64 locator")
        volume, start, volumes = struct.unpack_from("<IQI", data, locator + 4)
        if volume or volumes != 1 or data[start : start + 4] != b"PK\x06\x06":
            raise ValueError("invalid checkpoint ZIP64 framing")
        fields = struct.unpack_from("<QHHIIQQQQ", data, start + 4)
        length, _, _, disk, directory_disk, entries, total, size, offset = fields
        if length != 44 or start + 56 != locator or disk or directory_disk or entries != total:
            raise ValueError("invalid checkpoint ZIP64 directory header")
        directory_end = start
    else:
        directory_end = end
        if data[end - 20 : end - 16] == b"PK\x06\x07":
            # Torch emits ZIP64 EOCD even for small files. Validate its trailer too.
            volume, start, volumes = struct.unpack_from("<IQI", data, end - 16)
            if volume or volumes != 1 or data[start : start + 4] != b"PK\x06\x06":
                raise ValueError("invalid optional checkpoint ZIP64 locator")
            fields = struct.unpack_from("<QHHIIQQQQ", data, start + 4)
            if (
                fields[0] != 44
                or start + 56 != end - 20
                or fields[3:5] != (0, 0)
                or (fields[5:] != (count, count, size, offset))
            ):
                raise ValueError("checkpoint ZIP/ZIP64 directory disagreement")
            directory_end = start
    if total != count or offset != archive.start_dir or offset + size != directory_end:
        raise ValueError("checkpoint central directory count/offset/size mismatch")


def manifest(path: str, budget: Budget, policy: str) -> Any:
    data = read_small(path, budget)
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos or archive.comment:
            raise UnsupportedFormat("empty/commented checkpoint container")
        _directory(data, archive, len(infos))
        roots = {info.filename.split("/")[0] for info in infos}
        if len(roots) != 1 or any("/" not in info.filename for info in infos):
            raise UnsupportedFormat("checkpoint must have one record root")
        root = next(iter(roots))
        if root in ("", ".", "..") or "\\" in root:
            raise ValueError("unsafe checkpoint root")
        records, names = [], set()
        position = 0
        alignment = 64
        for info in infos:
            budget.consume(nodes=1)
            name = info.filename[len(root) + 1 :]
            if name in names or not (name in METADATA or re.fullmatch(r"data/[0-9]+", name)):
                raise UnsupportedFormat("duplicate or unknown checkpoint record: " + name)
            names.add(name)
            if info.is_dir() or info.flag_bits & ~0x808 or info.compress_type not in (0, 8):
                raise UnsupportedFormat("unsupported checkpoint ZIP flags/method")
            if (
                info.comment
                or info.create_system != 0
                or info.external_attr not in (0, 0o600 << 16)
            ):
                raise UnsupportedFormat("unsupported checkpoint ZIP attributes")
            _extras(info.extra)
            end, body, method, raw = _record(data, info, position, archive.start_dir, budget)
            position = end
            if name == ".storage_alignment":
                if raw.strip() != b"64":
                    raise UnsupportedFormat("unsupported checkpoint storage alignment")
                alignment = 64
            if (
                name.startswith("data/")
                and policy == "preserve-mmap"
                and (method != 0 or body % alignment)
            ):
                raise UnsupportedFormat("source storage is not mmap-compatible/aligned")
            if name == "version" and raw.strip() != b"3":
                raise UnsupportedFormat("unsupported checkpoint serialization version")
            if name == ".format_version" and raw.strip() != b"1":
                raise UnsupportedFormat("unsupported checkpoint layout version")
            if name == "byteorder" and raw not in (b"little", b"big"):
                raise ValueError("invalid checkpoint byteorder")
            records.append((info, raw, hashlib.sha256(raw).hexdigest()))
        if position != archive.start_dir or not {"data.pkl", "version"} <= names:
            raise ValueError("incomplete checkpoint layout")
        return records


def _rewrite(records: Any, candidate: str, policy: str, budget: Budget) -> None:
    with zipfile.ZipFile(candidate, "w", allowZip64=True) as output:
        assert output.fp is not None
        for original, raw, _ in records:
            budget.check()
            info = copy.copy(original)
            storage = "/data/" in info.filename
            info.compress_type = 0 if storage and policy == "preserve-mmap" else 8
            info.extra = b""
            # PyTorch record starts remain aligned. FB is its documented padding field.
            padding = -(output.fp.tell() + 30 + len(info.filename.encode()) + 4) % 64
            info.extra = struct.pack("<HH", 0x4246, padding) + b"Z" * padding
            output.writestr(info, raw, compresslevel=9)
    # zipfile supplies POSIX permissions for zero-valued DOS attributes. Restore
    # original central attributes after framing is finalized (local headers omit them).
    with zipfile.ZipFile(candidate) as archive:
        position = archive.start_dir
    with open(candidate, "r+b") as output:
        for original, _, _ in records:
            output.seek(position + 28)
            nlen, elen, clen = struct.unpack("<HHH", output.read(6))
            output.seek(position + 38)
            output.write(struct.pack("<I", original.external_attr))
            position += 46 + nlen + elen + clen
    budget.consume(written=os.path.getsize(candidate))


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    policy = options.get("checkpoint_compatibility", "preserve-mmap")
    records = manifest(source, budget, policy)
    details = {
        "profile": "torch-save-ZIP-v3",
        "compatibility": policy,
        "mmap": policy == "preserve-mmap",
        "tested_readers": ["Python Torch 2.2.2", "Python Torch 2.14.1"],
        "records": len(records),
        "user_objects_loaded": False,
    }
    if action == "inspect":
        return {"details": details}
    assert candidate is not None
    if action == "rewrite":
        _rewrite(records, candidate, policy, budget)
    # Compare byte identity/order/attributes independently of chosen compression methods.
    other = manifest(candidate, budget, policy)

    def signature(items: Any) -> Any:
        return [
            (i.filename, i.date_time, i.create_system, i.external_attr, digest)
            for i, _, digest in items
        ]

    if signature(records) != signature(other):
        raise ValueError("checkpoint member bytes/order/attributes changed")
    return {"equal": True, "changed": action == "rewrite", "details": details}


@guard_packer
def pack_checkpoint(filepath: str, debug: bool = False, quiet: bool = False, **commit: Any) -> Any:
    from .format_support import pack_format

    return pack_format("checkpoint", filepath, {"debug": debug, "quiet": quiet, **commit})
