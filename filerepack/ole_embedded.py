"""Qualified Word/XLS child scopes and exact wrapper/child contracts.

Object names are metadata; staging names are generated. No activation, Office
resave, shell interpolation or generic extension-based child execution.
"""

import copy
import hashlib
import io
import os
import re
import struct
import tempfile
import zipfile
import zlib
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Tuple

from .format_support import Budget, FormatLimit
from .ole_verify import CompoundFile, MAGIC, independent_manifest
from .ole_word_art import (
    CHAR,
    SPECIAL,
    WORD,
    fib_slice,
    fkps,
    pieces,
    properties,
    style_properties,
    u16,
    u32,
)

Path = Tuple[str, ...]
LIMIT = 16 * 1024 * 1024


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("OLE embedded: " + reason)


def word_objects(compound: CompoundFile, budget: Budget) -> set:
    word = compound.streams[WORD]
    table = compound.streams[("1Table" if u16(word, 10) & 512 else "0Table",)]
    modifiers: Dict = {}
    spans, targets, covered = pieces(word, table, modifiers), set(), []
    resolved: Dict = {}
    style_properties(fib_slice(word, table, 1), budget, resolved=resolved)
    require(
        not any(SPECIAL & set(p) for p in modifiers.values()),
        "piece-inherited OLE object properties are not qualified",
    )
    require(
        not any(SPECIAL & set(p) for p in resolved.values()),
        "style-inherited OLE object properties are not qualified",
    )
    for first, last, base, grp in fkps(word, table, 12, budget):
        props = properties(grp, base, CHAR)
        require(0x4A30 not in props, "OLE character-style overrides are not qualified")
        for start, stop, unit in spans:
            low, high = max(first, start), min(last, stop)
            if low >= high:
                continue
            require((low - start) % unit == (high - low) % unit == 0, "Word object/FKP alignment")
            covered.append((low, high))
            for at in range(low, high, unit):
                budget.consume(nodes=1)
                char = word[at] if unit == 1 else u16(word, at)
                if char != 20 or props.get(0x080A, (0, b"\0"))[1] != b"\1":
                    continue
                require(
                    0x6A03 in props
                    and props.get(0x0855, (0, b""))[1] == b"\1"
                    and props.get(0x0856, (0, b""))[1] == b"\1",
                    "ambiguous Word OLE character",
                )
                ident = struct.unpack("<I", props[0x6A03][1])[0]
                require(ident > 0, "invalid Word object ID")
                targets.add(("ObjectPool", "_" + str(ident)))
    require(
        sum(z - a for a, z in covered) == sum(z - a for a, z, _ in spans), "Word object coverage"
    )
    return targets


def xls_objects(compound: CompoundFile, budget: Budget) -> set:
    data, at, targets = compound.streams["Workbook",], 0, set()
    while at + 4 <= len(data):
        kind, size = struct.unpack_from("<HH", data, at)
        if kind == size == 0:
            require(not any(data[at:]), "nonzero Workbook tail")
            break
        end = at + 4 + size
        require(size <= 8224 and end <= len(data), "BIFF bounds")
        budget.consume(nodes=1)
        if kind == 0x5D:
            body = data[at + 4 : end]
            pos, parts = 0, {}
            while pos < len(body):
                require(pos + 4 <= len(body), "Obj subrecord header")
                ft, cb = struct.unpack_from("<HH", body, pos)
                pos += 4
                require(ft not in parts and cb <= len(body) - pos, "Obj duplicate/bounds")
                parts[ft] = body[pos : pos + cb]
                pos += cb
            require(0x15 in parts and len(parts[0x15]) == 18, "Obj Cmo bounds")
            ot = struct.unpack_from("<H", parts[0x15])[0]
            if 9 not in parts:
                require(ot in (0, 8, 19), "unqualified Obj consumer type")
                at = end
                continue
            require(
                ot == 8
                and list(parts) == [0x15, 7, 8, 9, 0]
                and len(parts[8]) == 2
                and not parts[0],
                "unqualified embedded Obj sequence",
            )
            flags = struct.unpack("<H", parts[8])[0]
            require(not flags & 0xB2, "DDE/control/control-stream/camera object")
            fmla = parts[9]
            require(len(fmla) >= 18, "FtPictFmla bounds")
            cb = struct.unpack_from("<H", fmla)[0]
            require(
                cb % 2 == 0
                and len(fmla) == cb + 6
                and struct.unpack_from("<H", fmla, 2)[0] == 5
                and fmla[8] == 2,
                "embedded Obj formula/target layout",
            )
            # ObjectParsedFormula: cce2, ignored4, PtgTbl1, ignored4.
            info = fmla[13 : 2 + cb]
            require(
                len(info) >= 4 and info[0] == 3 and info[2] == 0 and len(info) >= 3 + info[1] + 1,
                "embedded class information bounds",
            )
            require(info[3] in (0, 1), "unqualified embedded class string encoding")
            length = 4 + info[1] * (1 + info[3])
            require(
                length <= len(info) <= length + 1 and not any(info[length:]),
                "embedded class string/padding bounds",
            )
            classname = info[4:length].decode("utf-16le" if info[3] else "ascii")
            require(
                classname in ("Word.Document.8", "Excel.Sheet.8", "Package"),
                "unqualified embedding class",
            )
            ident = struct.unpack_from("<I", fmla, 2 + cb)[0]
            target = ("MBD" + format(ident, "08X"),)
            require(target not in targets, "aliased embedding storage")
            targets.add(target)
        at = end
    return targets


@dataclass(frozen=True)
class Wrapper:
    prefix: bytes
    payload: bytes
    suffix: bytes
    size_field: int

    def rebuild(self, payload: bytes) -> bytes:
        prefix = bytearray(self.prefix)
        struct.pack_into("<I", prefix, self.size_field, len(payload))
        struct.pack_into("<I", prefix, 0, len(prefix) + len(payload) + len(self.suffix) - 4)
        return bytes(prefix) + payload + self.suffix

    def identity(self) -> Tuple[bytes, bytes]:
        prefix = bytearray(self.prefix)
        struct.pack_into("<I", prefix, 0, 0)
        struct.pack_into("<I", prefix, self.size_field, 0)
        return bytes(prefix), self.suffix


def native_wrapper(data: bytes) -> Wrapper:
    require(
        8 <= len(data) <= LIMIT and u32(data, 0) == len(data) - 4 and u16(data, 4) == 2,
        "unqualified Ole10Native total size/flags",
    )
    at = 6
    for _ in range(2):
        end = data.find(b"\0", at, min(len(data), at + 1024))
        require(end >= at and end > at, "unterminated native label/name")
        at = end + 1
    require(at + 8 <= len(data) and data[at : at + 4] == b"\0\0\3\0", "native flags/version")
    at += 4
    length = u32(data, at)
    at += 4
    require(
        0 < length <= 1024 and at + length + 4 <= len(data) and data[at + length - 1] == 0,
        "native command bounds/terminator",
    )
    at += length
    size = u32(data, at)
    start, end = at + 4, at + 4 + size
    require(size > 0 and end + 2 <= len(data), "native payload bounds")
    suffix = data[end:]
    if suffix[:2] != b"\0\0":
        pos = 0
        for _ in range(3):
            count = u32(suffix, pos)
            pos += 4
            require(count <= 1024 and pos + 2 * count <= len(suffix), "native UTF16 suffix bounds")
            suffix[pos : pos + 2 * count].decode("utf-16le")
            pos += 2 * count
        require(pos == len(suffix), "unaccounted native suffix")
    else:
        require(suffix == b"\0\0", "unaccounted native suffix")
    return Wrapper(data[:start], data[start:end], suffix, at)


def package_wrapper(compound: CompoundFile, scope: Path) -> Wrapper:
    """Qualify native Packager class and every CompObj field, independently."""
    entry = next(e for e in compound.entries if e.path == scope)
    require(
        entry.clsid == bytes.fromhex("0c00030000000000c000000000000046")
        and compound.streams.get(scope + ("\x01Ole",))
        == bytes.fromhex("0100000200000000000000000000000000000000"),
        "unqualified Package class/link marker",
    )
    data = compound.streams.get(scope + ("\x01CompObj",), b"")
    require(28 <= len(data) <= 4096, "Package CompObj header/bounds")
    at = 28

    def string(wide: bool = False) -> bytes:
        nonlocal at
        size = u32(data, at)
        at += 4
        require(0 < size <= 400, "Package CompObj string length")
        count = size * (2 if wide else 1)
        require(at + count <= len(data), "Package CompObj string bounds")
        value = data[at : at + count]
        at += count
        require(value.endswith(b"\0\0" if wide else b"\0"), "Package CompObj string terminator")
        return value

    user, clipboard = string(), string()
    require(
        user in (b"Package\0", b"Packager Shell Object\0") and clipboard == b"Package\0",
        "unqualified Package display/clipboard class",
    )
    if at < len(data):
        require(string() == b"Package\0", "unqualified Package ProgID")
    if at < len(data):
        require(u32(data, at) == 0x71B239F4, "unknown Package Unicode marker")
        at += 4
        require(
            string(True).decode("utf-16le").rstrip("\0") in ("Package", "Packager Shell Object"),
            "unqualified Package Unicode class",
        )
        require(
            string(True) == "Package\0".encode("utf-16le"), "unqualified Package Unicode clipboard"
        )
        # Reserved2 is retained, including its length. Zero length is permitted.
        size = u32(data, at)
        at += 4
        require(size <= 400 and at + 2 * size <= len(data), "Package reserved string bounds")
        at += 2 * size
    require(at == len(data), "unaccounted Package CompObj bytes")
    return native_wrapper(compound.streams[scope + ("\x01Ole10Native",)])


def scopes(compound: CompoundFile, budget: Budget) -> Tuple[str, List[Path]]:
    from .ole import _profile

    host = "doc" if WORD in compound.streams else "xls" if ("Workbook",) in compound.streams else ""
    require(
        bool(host) and _profile(compound, host) == (host, False), "unqualified parent/macro layout"
    )
    targets = word_objects(compound, budget) if host == "doc" else xls_objects(compound, budget)
    actual = {
        e.path
        for e in compound.entries
        if e.kind == 1
        and (
            len(e.path) == 2 and e.path[0] == "ObjectPool"
            if host == "doc"
            else len(e.path) == 1 and re.fullmatch(r"MBD[0-9A-F]{8}", e.name)
        )
    }
    require(
        actual == targets and len(actual) <= 64, "embedding reference/storage inventory differs"
    )
    return host, sorted(actual)


def extract(
    source: str,
    compound: CompoundFile,
    scope: Path,
    host: str,
    writer: str,
    output: str,
    budget: Budget,
) -> CompoundFile:
    from .ole_recompress import _command, _read

    with open(output, "xb"):
        pass
    if _command(
        [
            writer,
            "--extract-qualified-object-v1",
            host + "-object",
            "/".join(scope),
            source,
            output,
        ],
        budget,
    ).returncode:
        raise ValueError("native object extraction failed")
    budget.consume(written=os.path.getsize(output), decoded=os.path.getsize(output))
    child = _read(output, budget)
    original = {e.path[len(scope) :]: e for e in compound.entries if e.path[: len(scope)] == scope}
    require(set(original) == {e.path for e in child.entries}, "extraction changed child inventory")
    for entry in child.entries:
        expected = original[entry.path]
        if not entry.path:
            require(
                (entry.clsid, entry.state, entry.modified)
                == (expected.clsid, expected.state, expected.modified),
                "child root view metadata",
            )
        else:
            require(
                replace(expected, path=entry.path) == entry,
                "child extraction changed bytes/metadata",
            )
    return child


def zip_identity(data: bytes, budget: Budget) -> Tuple[object, ...]:
    require(len(data) <= LIMIT and data[:4] == b"PK\3\4", "unsupported child ZIP envelope")
    result, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        eocd = len(data) - 22 - len(archive.comment)
        require(eocd >= 0 and data[eocd : eocd + 4] == b"PK\5\6", "child ZIP trailing data")
        disk, start_disk, count, total_count, cd_size, cd_start, comment_size = struct.unpack_from(
            "<HHHHIIH", data, eocd + 4
        )
        require(
            disk == start_disk == 0
            and count == total_count == len(entries)
            and cd_start == archive.start_dir
            and cd_start + cd_size == eocd
            and comment_size == len(archive.comment),
            "unqualified ZIP directory envelope",
        )
        require(
            0 < len(entries) <= 4096 and entries[0].header_offset == 0,
            "child ZIP member/prefix bounds",
        )
        seen = set()
        stop = 0
        for info in entries:
            budget.consume(nodes=1)
            require(
                info.filename not in seen
                and not info.filename.startswith(("/", "\\"))
                and ".." not in info.filename.replace("\\", "/").split("/")
                and not info.flag_bits & ~0x800
                and info.compress_type in (0, 8)
                and info.extract_version <= 20
                and info.file_size <= LIMIT,
                "unqualified child ZIP member/encoding",
            )
            require(
                not info.filename.casefold().startswith(("_xmlsignatures/", "meta-inf/")),
                "authenticated/uncertain ZIP package",
            )
            require(
                not info.filename.casefold().endswith((".p7s", ".sig", ".asc")), "signed ZIP child"
            )
            seen.add(info.filename)
            require(info.header_offset == stop, "unaccounted ZIP local data/gap")
            require(
                data[stop : stop + 4] == b"PK\3\4" and stop + 30 <= cd_start,
                "ZIP local header bounds",
            )
            fields = struct.unpack_from("<HHHHHIIIHH", data, stop + 4)
            version, flags, method, _, _, crc, packed, unpacked, namesize, extrasize = fields
            body = stop + 30 + namesize + extrasize
            require(
                body + packed <= cd_start
                and (version, flags, method, crc, packed, unpacked)
                == (
                    info.extract_version,
                    info.flag_bits,
                    info.compress_type,
                    info.CRC,
                    info.compress_size,
                    info.file_size,
                ),
                "ZIP local/central identity differs",
            )
            name = data[stop + 30 : stop + 30 + namesize]
            require(
                name.decode("utf-8" if flags & 0x800 else "cp437") == info.filename
                and data[stop + 30 + namesize : body] == info.extra,
                "ZIP local/central name or metadata differs",
            )
            pos = 0
            while pos < len(info.extra):
                require(pos + 4 <= len(info.extra), "ZIP extra header bounds")
                tag, size = struct.unpack_from("<HH", info.extra, pos)
                pos += 4
                require(
                    tag in (0x5455, 0x000A, 0x7855, 0x7875) and pos + size <= len(info.extra),
                    "unqualified ZIP extra metadata",
                )
                pos += size
            stop = body + packed
            total += info.file_size
            require(total <= LIMIT, "child ZIP aggregate limit")
            with archive.open(info) as member:
                raw = member.read(info.file_size + 1)
            require(len(raw) == info.file_size, "child ZIP decoded length differs")
            if method == 8:
                decoder = zlib.decompressobj(-15)
                check = decoder.decompress(data[body:stop], info.file_size + 1)
                require(
                    decoder.eof
                    and not decoder.unused_data
                    and not decoder.unconsumed_tail
                    and check == raw,
                    "ZIP compressed member envelope differs",
                )
            budget.consume(decoded=len(raw))
            attrs = (
                info.filename,
                info.date_time,
                info.compress_type,
                info.comment,
                info.extra,
                info.create_system,
                info.create_version,
                info.extract_version,
                info.flag_bits,
                info.volume,
                info.internal_attr,
                info.external_attr,
            )
            result.append((attrs, len(raw), hashlib.sha256(raw).digest()))
        require(stop == cd_start, "unaccounted ZIP data before directory")
        return archive.comment, tuple(result)


def optimize_zip(data: bytes, budget: Budget) -> bytes:
    expected = zip_identity(data, budget)
    target = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(target, "w", compresslevel=9) as output,
    ):
        output.comment = source.comment
        for info in source.infolist():
            budget.check()
            output.writestr(copy.copy(info), source.read(info), compresslevel=9)
    trial = target.getvalue()
    require(zip_identity(trial, budget) == expected, "ZIP encoder changed content/metadata")
    return trial if len(trial) < len(data) else data


def child_identity(child: CompoundFile, budget: Budget, content: bool) -> object:
    from .ole import _profile
    from .ole_art_layout import inspect_art

    hosts = [h for h, p in (("doc", WORD), ("xls", ("Workbook",))) if p in child.streams]
    require(
        len(hosts) == 1 and _profile(child, hosts[0]) == (hosts[0], False),
        "unqualified/signed/encrypted child format",
    )
    if content:
        try:
            return ("officeart", inspect_art(child, budget).fingerprint())
        except FormatLimit:
            raise
        except ValueError:
            pass
    return ("strict", child.manifest)


def child_equal(
    source: str,
    before: CompoundFile,
    target: str,
    after: CompoundFile,
    writer: str,
    options: Dict[str, Any],
    budget: Budget,
    depth: int,
) -> bool:
    content = options.get("ole_recompress", False) and options.get("pack_images", True)
    if child_identity(before, budget, content) == child_identity(after, budget, content):
        return True
    if depth >= 4 or not options.get("deep", True):
        return False
    return compare(source, before, target, after, writer, options, budget, depth=depth + 1)


def optimize_child(
    source: str,
    child: CompoundFile,
    writer: str,
    options: Dict[str, Any],
    budget: Budget,
    scratch: str,
    depth: int,
    ancestors: frozenset,
) -> CompoundFile:
    """Select separate strict, image and recursive-child candidates under one budget."""
    from .ole_art_layout import equal_art, inspect_art
    from .ole_recompress import _art_native, _native, planned_native

    child_identity(child, budget, False)
    host = "doc" if WORD in child.streams else "xls"
    destination = os.path.join(scratch, "strict.cfb")
    with open(destination, "xb"):
        pass
    selected = _native(writer, source, destination, budget)
    require(selected.manifest == child.manifest, "child strict compaction changed content")
    if options.get("ole_recompress", False) and options.get("pack_images", True):
        try:
            art = inspect_art(child, budget)
            replacements, _ = art.reencode(budget, ultra=options.get("ultra", False))
            target = os.path.join(scratch, "image.cfb")
            with open(target, "xb"):
                pass
            after = _art_native(writer, source, target, host, replacements, budget)
            require(equal_art(art, inspect_art(after, budget)), "child image contract differs")
            if len(after.data) < len(selected.data):
                selected = after
        except FormatLimit:
            raise
        except ValueError:
            pass
    if depth < 4 and options.get("deep", True):
        try:
            replacements, _ = optimize(
                source, child, writer, options, budget, depth=depth + 1, ancestors=ancestors
            )
        except FormatLimit:
            raise
        except ValueError:
            replacements = {}
        if replacements:
            target = os.path.join(scratch, "nested.cfb")
            with open(target, "xb"):
                pass
            after = planned_native(writer, source, target, host + "-object", replacements, budget)
            require(
                compare(source, child, target, after, writer, options, budget, depth=depth + 1),
                "recursive child contract differs",
            )
            if len(after.data) < len(selected.data):
                selected = after
    return selected if len(selected.data) < len(child.data) else child


def optimize(
    source: str,
    compound: CompoundFile,
    writer: str,
    options: Dict[str, Any],
    budget: Budget,
    *,
    depth: int = 0,
    ancestors: frozenset = frozenset(),
) -> Tuple[Dict[Path, bytes], Dict[str, object]]:
    require(depth <= 4, "embedded depth limit")
    identity = hashlib.sha256(compound.data).digest()
    require(identity not in ancestors, "cyclic/aliased embedded container")
    ancestors = ancestors | {identity}
    host, objects = scopes(compound, budget)
    replacements, reports = {}, []
    with tempfile.TemporaryDirectory(
        prefix="embedded-", dir=options.get("_scratch_directory")
    ) as scratch:
        for index, scope in enumerate(objects):
            report = {"object": "/".join(scope), "changed_streams": 0}
            reports.append(report)
            native = scope + ("\x01Ole10Native",)
            try:
                if native in compound.streams:
                    wrapped = package_wrapper(compound, scope)
                    if wrapped.payload.startswith(MAGIC):
                        child = CompoundFile(wrapped.payload)
                        budget.consume(decoded=len(wrapped.payload), nodes=len(child.entries))
                        independent_manifest(io.BytesIO(wrapped.payload), child)
                        child_identity(child, budget, False)
                        path = os.path.join(scratch, str(index) + ".doc")
                        from .format_support import write_bytes

                        write_bytes(path, wrapped.payload, budget)
                        output = os.path.join(scratch, str(index) + ".cfb")
                        os.mkdir(output)
                        after = optimize_child(
                            path, child, writer, options, budget, output, depth, ancestors
                        )
                        payload = (
                            after.data
                            if len(after.data) < len(wrapped.payload)
                            else wrapped.payload
                        )
                    elif wrapped.payload.startswith(b"PK\3\4") and options.get(
                        "pack_archives", True
                    ):
                        payload = optimize_zip(wrapped.payload, budget)
                    else:
                        raise ValueError("child packer/category is outside the lossless allowlist")
                    if len(payload) < len(wrapped.payload):
                        replacements[native] = wrapped.rebuild(payload)
                elif options.get("ole_recompress", False) or options.get("deep", True):
                    path = os.path.join(scratch, str(index) + ".cfb")
                    child = extract(source, compound, scope, host, writer, path, budget)
                    output = os.path.join(scratch, str(index) + "-candidates")
                    os.mkdir(output)
                    after = optimize_child(
                        path, child, writer, options, budget, output, depth, ancestors
                    )
                    for relative, payload in after.streams.items():
                        if payload != child.streams[relative]:
                            replacements[scope + relative] = payload
                else:
                    report["skip"] = (
                        "direct substorage has no additional allocation beyond parent compaction"
                    )
                report["changed_streams"] = sum(p[: len(scope)] == scope for p in replacements)
                if not report["changed_streams"] and "skip" not in report:
                    report["skip"] = "no smaller qualified child representation"
            except FormatLimit:
                raise
            except (ValueError, zipfile.BadZipFile, zlib.error) as exc:
                report["skip"] = str(exc)
    return replacements, {
        "embedded_objects": len(objects),
        "objects": reports,
        "changed_streams": len(replacements),
    }


def compare(
    source: str,
    before: CompoundFile,
    candidate: str,
    after: CompoundFile,
    writer: str,
    options: Dict[str, Any],
    budget: Budget,
    *,
    depth: int = 0,
) -> bool:
    content = options.get("ole_recompress", False) and options.get("pack_images", True)
    host, first = scopes(before, budget)
    second_host, second = scopes(after, budget)
    if (host, first) != (second_host, second):
        return False
    allowed = set()
    with tempfile.TemporaryDirectory(
        prefix="embedded-verify-", dir=options.get("_scratch_directory")
    ) as scratch:
        for index, scope in enumerate(first):
            native = scope + ("\x01Ole10Native",)
            old = {p: v for p, v in before.streams.items() if p[: len(scope)] == scope}
            new = {p: v for p, v in after.streams.items() if p[: len(scope)] == scope}
            if old == new:
                continue
            if native in old:
                if set(old) != set(new) or any(old[p] != new[p] for p in old if p != native):
                    return False
                a, b = package_wrapper(before, scope), package_wrapper(after, scope)
                if a.identity() != b.identity() or len(b.payload) > len(a.payload):
                    return False
                if a.payload.startswith(MAGIC) and b.payload.startswith(MAGIC):
                    budget.consume(decoded=len(a.payload) + len(b.payload))
                    left, right = CompoundFile(a.payload), CompoundFile(b.payload)
                    budget.consume(nodes=len(left.entries) + len(right.entries))
                    independent_manifest(io.BytesIO(a.payload), left)
                    independent_manifest(io.BytesIO(b.payload), right)
                    path_a = os.path.join(scratch, str(index) + "-serialized-a.cfb")
                    path_b = os.path.join(scratch, str(index) + "-serialized-b.cfb")
                    from .format_support import write_bytes

                    write_bytes(path_a, a.payload, budget)
                    write_bytes(path_b, b.payload, budget)
                    if not child_equal(path_a, left, path_b, right, writer, options, budget, depth):
                        return False
                elif options.get("pack_archives", True):
                    if zip_identity(a.payload, budget) != zip_identity(b.payload, budget):
                        return False
                else:
                    return False
                allowed.add(native)
            elif content or options.get("deep", True):
                child_a = extract(
                    source,
                    before,
                    scope,
                    host,
                    writer,
                    os.path.join(scratch, str(index) + "-a.cfb"),
                    budget,
                )
                child_b = extract(
                    candidate,
                    after,
                    scope,
                    host,
                    writer,
                    os.path.join(scratch, str(index) + "-b.cfb"),
                    budget,
                )
                if not child_equal(
                    os.path.join(scratch, str(index) + "-a.cfb"),
                    child_a,
                    os.path.join(scratch, str(index) + "-b.cfb"),
                    child_b,
                    writer,
                    options,
                    budget,
                    depth,
                ):
                    return False
                allowed.update(p for p in old if old[p] != new.get(p))
            else:
                return False

    def manifest(compound: CompoundFile) -> object:
        return tuple(
            replace(e, size=0, sha256="") if e.path in allowed else e
            for e in compound.manifest.entries
        )

    return manifest(before) == manifest(after)
