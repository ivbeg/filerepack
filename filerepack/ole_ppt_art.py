"""Pictures delay-store references in the audited single-edit PPT profile."""

import hashlib
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Tuple

from .ole_officeart import BLIPS, Parser, Record, require
from .ole_ppt_host import PptHost, inspect_host
from .ole_verify import CompoundFile

PICTURES, DOCUMENT = ("Pictures",), ("PowerPoint Document",)


@dataclass
class PptArt:
    data: bytes
    pictures: Tuple[Record, ...]
    refs: Dict[int, int]  # FBSE record position -> Pictures record index.

    def fingerprint(self) -> Tuple[object, ...]:
        data = bytearray(self.data)
        for position, index in self.refs.items():
            struct.pack_into("<I", data, position + 28, 0)
            struct.pack_into("<I", data, position + 36, index)
        # Exact-byte identities for immutable carriers keep the verifier from
        # retaining another Document and every unselected encoded picture.
        pictures = tuple(
            record.fingerprint()
            if record.raster is not None or record.metafile is not None
            else (record.flags, record.kind, hashlib.sha256(record.body).digest())
            for record in self.pictures
        )
        return hashlib.sha256(data).digest(), pictures

    def rebuild(self, payloads: Dict[int, bytes]) -> Dict[Tuple[str, ...], bytes]:
        data, encoded, positions = bytearray(self.data), [], []
        offset = 0
        for record in self.pictures:
            positions.append(offset)
            blob = record.encode(payloads)
            encoded.append(blob)
            offset += len(blob)
        for position, index in self.refs.items():
            struct.pack_into("<I", data, position + 28, len(encoded[index]))
            struct.pack_into("<I", data, position + 36, positions[index])
        return {DOCUMENT: bytes(data), PICTURES: b"".join(encoded)}


def inspect_ppt(compound: CompoundFile, parser: Parser) -> PptArt:
    host = inspect_host(compound, parser.budget, pictures=True)
    require(PICTURES in compound.streams, "no Pictures delay store")
    data = compound.streams[DOCUMENT]
    # Compact identities allow sequential PNG decoding. Reserve complete source,
    # encoder/verification passes by declared sample size in Pictures order.
    parser.bounded_png = True
    # The new notes-bearing corpus qualifies PNG rewriting only; retain the
    # existing JPEG codec for legacy presentations without NotesContainer.
    parser.retain_jpeg = any(record.kind == 1008 for record in host.records.values())
    pictures = parser.sequence(compound.streams[PICTURES])
    require(
        0 < len(pictures) <= 64 and all(record.kind in BLIPS for record in pictures),
        "unqualified Pictures sequence",
    )
    mapping, offset = {}, 0
    for index, record in enumerate(pictures):
        mapping[offset] = index
        offset += 8 + len(record.body)
    records = host.records
    stores = [position for position, r in records.items() if r.kind == 0xF001]
    require(len(stores) == 1, "multiple/missing PPT BStores")
    store = stores[0]
    parent = records[store].parent
    require(parent is not None, "BStore parent missing")
    assert parent is not None
    group_parent = records[parent].parent
    require(group_parent is not None, "drawing group parent missing")
    assert group_parent is not None
    require(
        records[parent].kind == 0xF000
        and records[group_parent].kind == 1035
        and records[group_parent].parent == 0,
        "BStore outside live drawing group",
    )
    refs: Dict[int, int] = {}
    entries = [position for position, r in records.items() if r.kind == 0xF007]
    entries.sort()
    require(len(entries) == records[store].flags >> 4, "PPT BStore entry count differs")
    counts = _consumers(host, len(entries))
    for entry_index, position in enumerate(entries):
        entry = records[position]
        require(entry.parent == store and entry.size == 36, "unqualified PPT FBSE placement/name")
        body = data[position + 8 : position + 44]
        size, count, target = struct.unpack_from("<III", body, 20)
        if count == 0:
            require(
                counts[entry_index] == 0
                and entry.flags == 2
                and body == b"\0" * 18 + b"\xff\0" + b"\0" * 16,
                "unqualified empty PPT BStore entry",
            )
            continue
        require(
            count > 0
            and count == counts[entry_index]
            and target in mapping
            and body[33] == 0
            and entry.flags & 15 == 2
            and entry.flags >> 4 in body[:2],
            "shared/missing/named picture reference",
        )
        index = mapping[target]
        picture = pictures[index]
        uid_count = 16 * (1 + (picture.flags >> 4 == BLIPS[picture.kind][1]))
        require(
            size == 8 + len(picture.body)
            and body[2:18] == picture.body[uid_count - 16 : uid_count],
            "PPT FBSE size/UID differs",
        )
        require(
            entry.flags >> 4 == {0xF01A: 2, 0xF01B: 3, 0xF01D: 5, 0xF01E: 6}[picture.kind],
            "PPT FBSE type differs",
        )
        refs[position] = index
    require(
        len(refs) == len(pictures) and set(refs.values()) == set(range(len(pictures))),
        "aliased/unreferenced Pictures records",
    )
    return PptArt(data, pictures, refs)


def _consumers(host: PptHost, entries: int) -> Counter:
    """MS-ODRAW pib/fillBlip/lineFillBlip use stable, one-based BStore IDs.

    fComplex values are lengths, including when fBid is set; they are never indexes.
    Tertiary XML package properties remain immutable and carry no delay-store offsets.
    """
    counts: Counter = Counter()
    for position, record in host.records.items():
        if record.kind not in (0xF00B, 0xF122):
            continue
        number, tail, previous = record.flags >> 4, (record.flags >> 4) * 6, -1
        require(
            record.flags & 15 == 3 and number > 0 and tail <= record.size,
            "PPT property table bounds/version",
        )
        for index in range(number):
            code, value = struct.unpack_from("<HI", host.data, position + 8 + index * 6)
            ident = code & 0x3FFF
            require(ident > previous, "duplicate/unsorted PPT property")
            previous = ident
            if code & 0x8000:
                require(tail + value <= record.size, "PPT complex property bounds")
                require(
                    ident not in (0x104, 0x186, 0x1C5) or value == 0,
                    "inline picture property is not qualified",
                )
                tail += value
            elif code & 0x4000:
                require(
                    ident in (0x104, 0x186, 0x1C5) and value <= entries,
                    "unknown/out-of-range PPT BLIP consumer",
                )
                if value:
                    owner = position
                    while host.records[owner].parent is not None:
                        parent = host.records[owner].parent
                        assert parent is not None
                        owner = parent
                    require(
                        owner in host.live and host.records[owner].kind in (1006, 1016, 1008),
                        "picture consumer outside live slide/master/notes page",
                    )
                    counts[value - 1] += 1
            elif ident in (0x104, 0x186, 0x1C5):
                require(False, "PPT BLIP index lacks fBid")
        require(tail == record.size, "unaccounted PPT complex property bytes")
    return counts
