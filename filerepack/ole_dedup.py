"""Exact BLIP deduplication with complete qualified consumer and byte accounting."""

import os
import struct
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from .format_support import Budget, FormatLimit, run_operation
from .ole_officeart import BLIPS, PROPERTY_IDS, Parser, Record, require
from .ole_ppt import read_records
from .ole_verify import CompoundFile
from .ole_xls_art import WORKBOOK, XlsArt, biff, inspect_xls

# All scalar BLIP-index families in MS-ODRAW. Complex inlined images and unknown
# property families are deliberately excluded from this shared-store profile.
IMAGE_IDS = {0x104, 0x10F, 0x186, 0x1C5, 0x545, 0x585, 0x5C5, 0x605}
DISPLAY_IDS = (
    PROPERTY_IDS
    | set(range(0x100, 0x110))
    | {
        0x111,
        0x180,
        0x182,
        0x183,
        0x184,
        0x185,
        0x187,
        0x188,
        0x189,
        0x18A,
        0x18B,
        0x18C,
        0x18D,
        0x18E,
        0x190,
        0x191,
        0x1C1,
        0x1C2,
        0x1C3,
        0x1C4,
        0x1C6,
        0x1C7,
        0x1C8,
        0x1CB,
        0x1CC,
        0x1CD,
        0x1CE,
        0x1CF,
        0x1D0,
        0x1D1,
        0x1D2,
        0x1D3,
        0x1D4,
        0x1D5,
        0x1D6,
        0x1D7,
        0x7F,
        0x80,
        0x87,
        0x13F,
        0x193,
        0x194,
        0x1BF,
        0x201,
        0x23F,
        0x301,
        0x304,
        0x305,
        0x306,
        0x33F,
    }
    | IMAGE_IDS
)


def consumers(data: bytes, entries: int, budget: Budget) -> Dict[int, int]:
    result = {}
    for at, record in read_records(data).items():
        budget.consume(nodes=1)
        require(
            record.kind not in (0xF121, 0xF122),
            "secondary/private property consumers are not qualified",
        )
        if record.kind != 0xF00B:
            continue
        require(record.flags & 15 == 3, "FOPT version")
        count, previous = record.flags >> 4, -1
        body = data[at + 8 : at + 8 + record.size]
        tail = count * 6
        require(count > 0 and tail <= len(body), "FOPT table bounds")
        for i in range(count):
            code, value = struct.unpack_from("<HI", body, i * 6)
            ident = code & 0x3FFF
            require(
                ident in DISPLAY_IDS and ident > previous,
                "unknown/duplicate dedup consumer property",
            )
            previous = ident
            if code & 0x8000:
                require(
                    ident == 0x105
                    and value % 2 == 0
                    and value >= 2
                    and tail + value <= len(body)
                    and body[tail + value - 2 : tail + value] == b"\0\0",
                    "complex/inline consumer is not qualified",
                )
                tail += value
            elif ident in IMAGE_IDS:
                require(
                    code & 0x4000 and 0 <= value <= entries, "BLIP reference flags/index bounds"
                )
                if value:
                    result[at + 8 + i * 6 + 2] = value - 1
            else:
                require(not code & 0x4000, "unknown BLIP-reference property")
        require(tail == len(body), "unaccounted FOPT complex bytes")
    return result


def entry_identity(entry: Record, picture: Record) -> bytes:
    prefix = bytearray(entry.body[: 36 + entry.body[33]])
    for at in (20, 24, 28):
        struct.pack_into("<I", prefix, at, 0)
    return struct.pack("<HH", entry.flags, entry.kind) + bytes(prefix) + picture.original()


@dataclass
class DedupLayout:
    compound: CompoundFile
    host: str
    data: bytes
    start: int
    stop: int
    store: Record
    images: Tuple[Record, ...]
    consumers: Dict[int, int]
    identity: List[bytes]
    canonical: List[int]
    adapter: Optional[XlsArt]
    ppt_layout: Any = None

    def fingerprint(self) -> Tuple[object, ...]:
        unique = list(dict.fromkeys(self.identity))
        normalized = {i: unique.index(value) for i, value in enumerate(self.identity)}
        data = bytearray(self.data)
        for field, index in self.consumers.items():
            struct.pack_into("<I", data, field, normalized[index] + 1)
        delta = self.stop - self.start
        root_other: object
        if self.adapter is not None:
            for field, target in self.adapter.pointers.items():
                struct.pack_into(
                    "<I", data, field, target - delta if target >= self.stop else target
                )
            root_other = tuple(
                r.fingerprint() for r in self.adapter.group.children if r.kind != 0xF001
            )
            # Exclude the entire drawing-group envelope, but compare every other
            # group record and the complete normalized BStore separately.
            a, z = self.adapter.start, self.adapter.stop
            prefix = bytes(data[:a] + data[z:])
        else:
            records = read_records(self.data)
            for at, record in records.items():
                if (
                    record.flags & 15 == 15
                    and at < self.start
                    and at + 8 + record.size >= self.stop
                ):
                    struct.pack_into("<I", data, at + 4, record.size - delta)
            layout = self.ppt_layout
            for field in layout.fields.values():
                target = struct.unpack_from("<I", data, field)[0]
                struct.pack_into(
                    "<I", data, field, target - delta if target >= self.stop else target
                )
            struct.pack_into("<I", data, layout.edit + 20, layout.directory - delta)
            current = bytearray(layout.current)
            struct.pack_into("<I", current, 16, layout.edit - delta)
            root_other = bytes(current)
            prefix = bytes(data[: self.start] + data[self.stop :])
        changed = (
            {WORKBOOK}
            if self.host == "xls"
            else {("PowerPoint Document",), ("Pictures",), ("Current User",)}
        )
        metadata = tuple(
            replace(e, size=0, sha256="") if e.path in changed else e
            for e in self.compound.manifest.entries
        )
        counts = Counter(self.identity[i] for i in self.consumers.values())
        return self.host, metadata, prefix, root_other, tuple(unique), tuple(sorted(counts.items()))

    def rebuild(self) -> Tuple[Dict[Tuple[str, ...], bytes], Dict[str, int]]:
        retained = sorted(set(self.canonical))
        mapping = {i: retained.index(self.canonical[i]) for i in range(len(self.canonical))}
        counts = Counter(mapping[i] for i in self.consumers.values())
        data = bytearray(self.data)
        for field, index in self.consumers.items():
            struct.pack_into("<I", data, field, mapping[index] + 1)
        entries, pictures, offset = [], [], 0
        for new, old in enumerate(retained):
            entry = self.store.children[old]
            prefix = bytearray(entry.body[: 36 + entry.body[33]])
            struct.pack_into("<I", prefix, 24, counts[new])
            if self.host == "ppt":
                if not counts[new]:
                    entries.append(entry)
                    continue
                blob = self.images[old].original()
                struct.pack_into("<I", prefix, 20, len(blob))
                struct.pack_into("<I", prefix, 28, offset)
                offset += len(blob)
                pictures.append(blob)
                entries.append(replace(entry, body=bytes(prefix)))
            else:
                body = bytes(prefix) + self.images[old].original()
                entries.append(replace(entry, body=body))
        store = replace(self.store, flags=(len(entries) << 4) | 15, children=tuple(entries))
        if self.adapter is not None:
            group = replace(
                self.adapter.group,
                children=tuple(
                    store if c.kind == 0xF001 else c for c in self.adapter.group.children
                ),
            )
            replacements = replace(self.adapter, data=bytes(data), group=group).rebuild({})
        else:
            payload = store.encode({})
            delta = len(payload) - (self.stop - self.start)
            for at, record in read_records(self.data).items():
                if (
                    record.flags & 15 == 15
                    and at < self.start
                    and at + 8 + record.size >= self.stop
                ):
                    struct.pack_into("<I", data, at + 4, record.size + delta)
            layout = self.ppt_layout
            for field in layout.fields.values():
                target = struct.unpack_from("<I", data, field)[0]
                struct.pack_into(
                    "<I", data, field, target + delta if target >= self.stop else target
                )
            struct.pack_into("<I", data, layout.edit + 20, layout.directory + delta)
            current = bytearray(layout.current)
            struct.pack_into("<I", current, 16, layout.edit + delta)
            replacements = {
                ("PowerPoint Document",): bytes(data[: self.start])
                + payload
                + bytes(data[self.stop :]),
                ("Pictures",): b"".join(pictures),
                ("Current User",): bytes(current),
            }
        return replacements, {
            "removed_entries": len(self.images) - len(retained),
            "rewritten_references": sum(mapping[i] != i for i in self.consumers.values()),
        }


def inspect_dedup(compound: CompoundFile, budget: Budget) -> DedupLayout:
    from .ole import _profile
    from .ole_ppt_records import inspect_records

    host = (
        "xls"
        if WORKBOOK in compound.streams
        else "ppt"
        if ("Pictures",) in compound.streams
        else ""
    )
    require(
        bool(host) and _profile(compound, host) == (host, False),
        "only qualified macro-free XLS/PPT shared stores",
    )
    parser = Parser(budget, raster=False)
    refs, adapter, ppt = {}, None, None
    if host == "xls":
        data = compound.streams[WORKBOOK]
        adapter = inspect_xls(data, parser)
        store = next(r for r in adapter.group.children if r.kind == 0xF001)
        # Physical BIFF fragments are removed by the adapter, not an OfficeArt
        # span in Workbook. Normalization uses the complete fragmented group.
        start, stop = adapter.start, adapter.stop
        images = tuple(r.children[0] for r in store.children)
        fragments: List[bytes] = []
        fields: List[int] = []
        for at, kind, body in biff(data):
            if at <= stop:
                continue
            if kind in (0xEC, 0x3C):
                fields.extend(range(at + 4, at + 4 + len(body)))
                fragments.append(body)
            elif kind == 0xA and fragments:
                drawing = b"".join(fragments)
                for field, index in consumers(drawing, len(images), budget).items():
                    require(
                        field + 4 <= len(fields)
                        and fields[field : field + 4]
                        == list(range(fields[field], fields[field] + 4)),
                        "consumer operand crosses BIFF fragmentation",
                    )
                    refs[fields[field]] = index
                fragments, fields = [], []
    else:
        ppt = inspect_records(compound, budget)
        data = ppt.data
        records = read_records(data)
        stores = [at for at, r in records.items() if r.kind == 0xF001]
        require(len(stores) == 1, "dedup requires one live PPT BStore")
        start = stores[0]
        stop = start + 8 + records[start].size
        store = parser.sequence(data[start:stop])[0]
        raw_images = parser.sequence(compound.streams["Pictures",])
        offsets, at = {}, 0
        for picture in raw_images:
            require(picture.kind in BLIPS, "PPT delay-store record type")
            offsets[at] = picture
            at += 8 + len(picture.body)
        images_list = []
        seen = set()
        for entry in store.children:
            require(
                len(entry.body) == 36 and not entry.children and entry.body[33] == 0,
                "unqualified empty/named/embedded PPT store",
            )
            size, count, target = struct.unpack_from("<III", entry.body, 20)
            if count == 0:
                require(
                    entry.flags == 2 and entry.body == b"\0" * 18 + b"\xff\0" + b"\0" * 16,
                    "unqualified empty PPT BStore entry",
                )
                images_list.append(Record(0, 0, b""))
                continue
            require(
                target in offsets and target not in seen and count > 0,
                "aliased/unreferenced PPT delay store",
            )
            picture = offsets[target]
            uid_size = 16 * (1 + (picture.flags >> 4 == BLIPS[picture.kind][1]))
            require(
                size == 8 + len(picture.body)
                and entry.body[2:18] == picture.body[uid_size - 16 : uid_size],
                "PPT store size/UID",
            )
            seen.add(target)
            images_list.append(picture)
        require(seen == set(offsets), "unreferenced Pictures bytes")
        images = tuple(images_list)
        refs = consumers(data, len(images), budget)
    require(
        len(images) <= 64 and all(len(e.body) >= 36 for e in store.children), "dedup store limits"
    )
    counts = Counter(refs.values())
    require(
        all(
            struct.unpack_from("<I", e.body, 24)[0] == counts[i]
            and (counts[i] > 0 or host == "ppt" and images[i].kind == 0)
            for i, e in enumerate(store.children)
        ),
        "incomplete FBSE/consumer reference counts",
    )
    require(sum(p.kind == 0 for p in images) <= 1, "multiple empty entries are not qualified")
    identity = [entry_identity(e, p) for e, p in zip(store.children, images)]
    canonical = [identity.index(value) for value in identity]
    return DedupLayout(
        compound, host, data, start, stop, store, images, refs, identity, canonical, adapter, ppt
    )


def run_dedup_operation(
    action: str,
    source: str,
    candidate: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from .ole_recompress import _DEADLINE

    return run_operation(
        "ole-dedup",
        action,
        source,
        candidate,
        options,
        deadline=_DEADLINE.get() or time.monotonic() + 120,
    )


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    from .ole_recompress import _read

    layout = inspect_dedup(_read(source, budget), budget)
    if action == "inspect":
        return {"images": len(layout.images)}
    if action == "compare" and candidate is not None:
        after = inspect_dedup(_read(candidate, budget), budget)
        return {
            "equal": layout.fingerprint() == after.fingerprint()
            and len(after.images) <= len(layout.images)
        }
    raise ValueError("Unknown dedup operation")


def try_candidate(
    source: str,
    original: CompoundFile,
    candidate: str,
    selected: Dict[str, Any],
    writer: str,
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    from .ole_recompress import planned_native, _command

    try:
        require(options.get("pack_images", True), "parent policy disables image deduplication")
        layout = inspect_dedup(original, budget)
        replacements, counts = layout.rebuild()
        report: Dict[str, Any] = dict(counts)
        selected["details"]["deduplication"] = report
        if not report["removed_entries"]:
            report["skip"] = "no compatible byte-identical images"
            return selected
        require(
            b"qualified-stream-replacement-v1"
            in _command([writer, "--capabilities"], budget).stdout.split(),
            "deduplication requires native helper 0.4.0+",
        )
        with tempfile.TemporaryDirectory(
            prefix="dedup-", dir=os.path.dirname(candidate)
        ) as scratch:
            output = os.path.join(scratch, "candidate." + layout.host)
            with open(output, "xb"):
                pass
            rebuilt = planned_native(writer, source, output, layout.host, replacements, budget)
            after = inspect_dedup(rebuilt, budget)
            require(
                layout.fingerprint() == after.fingerprint(),
                "dedup candidate changed images/graph/display bytes",
            )
            if len(rebuilt.data) < os.path.getsize(candidate):
                os.replace(output, candidate)
                selected["verify"] = "ole-dedup"
                selected["details"].update(
                    strategy="ole-image-deduplication",
                    additional_savings_bytes=selected["details"]["compaction_bytes"]
                    - len(rebuilt.data),
                )
            else:
                report["skip"] = "removed images do not improve selected physical file size"
    except FormatLimit:
        raise
    except ValueError as exc:
        selected["details"]["deduplication_skip"] = str(exc)
    return selected
