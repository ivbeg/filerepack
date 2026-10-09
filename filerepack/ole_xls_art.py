"""Qualified BIFF8 drawing-group relocation; other record bytes remain exact."""

import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .ole_officeart import Parser, Record, require
from .ole_ppt import read_records

WORKBOOK = ("Workbook",)
# Audited simple globals, worksheet settings and embedded-picture object records.
# Pivot caches, macros and FRT families not represented here are rejected.
# Audited cell/formula/SST data stays exact; only explicit absolute pointers move.
SIZES = {
    0xA: {0},
    0xC: {2},
    0xD: {2},
    0xE: {2},
    0xF: {2},
    0x10: {8},
    0x11: {2},
    0x12: {2},
    0x13: {2},
    0x14: {0},
    0x15: {0},
    0x19: {2},
    0x1D: {15},
    0x22: {2},
    0x2A: {2},
    0x2B: {2},
    0x3D: {18},
    0x40: {2},
    0x42: {2},
    0x55: {2},
    0x5C: {112},
    0x5F: {2},
    0x80: {8},
    0x81: {2},
    0x82: {2},
    0x83: {2},
    0x84: {2},
    0x8C: {4},
    0x8D: {2},
    0x9C: {2},
    0xA1: {34},
    0xC1: {2},
    0xDA: {2},
    0xE0: {20},
    0xE1: {2},
    0xE2: {0},
    0xED: {24},
    0xEF: {6},
    0x13D: {6},
    0x160: {2},
    0x161: {2},
    0x1AF: {2},
    0x1B7: {2},
    0x1BC: {2},
    0x1C0: {0},
    0x1C1: {8},
    0x200: {14},
    0x225: {4},
    0x23E: {18},
    0x293: {4},
    0x809: {16},
}
VARIABLE = {0x31, 0x3C, 0x5D, 0x85, 0xEB, 0xEC, 0xFC, 0xFF, 0x13D, 0x20B, 0x41E, 0x863}
SIZES.update(
    {0x201: {6}, 0x203: {14}, 0x205: {8}, 0x208: {16}, 0xFD: {10}, 0x27E: {10}, 0x236: {16}}
)
VARIABLE.update({0x6, 0x207, 0xD7, 0xBD, 0xBE, 0x4BC, 0x221})
CELLS = {0x201, 0x203, 0x205, 0xFD, 0x27E, 0xBD, 0xBE, 0x6}
DRAW_VERSIONS = {
    0xF002: 15,
    0xF003: 15,
    0xF004: 15,
    0xF008: 0,
    0xF009: 1,
    0xF00A: 2,
    0xF00B: 3,
    0xF010: 0,
    0xF011: 0,
    0xF122: 3,
}


def biff(data: bytes) -> List[Tuple[int, int, bytes]]:
    records: List[Tuple[int, int, bytes]] = []
    offset = 0
    while offset < len(data):
        if data[offset : offset + 4] == b"\0" * 4:
            require(not any(data[offset:]), "nonzero BIFF tail padding")
            break
        require(offset + 4 <= len(data) and len(records) < 200000, "BIFF header/count limit")
        kind, size = struct.unpack_from("<HH", data, offset)
        end = offset + 4 + size
        require(size <= 8224 and end <= len(data), "BIFF record bounds")
        require(
            kind in VARIABLE or size in SIZES.get(kind, set()),
            "unqualified BIFF type/version/length: " + hex(kind),
        )
        records.append((offset, kind, data[offset + 4 : end]))
        offset = end
    return records


class StringCursor:
    """Retain physical record identity, including character encoding transitions."""

    def __init__(self, parts: List[Tuple[int, int, bytes]]):
        self.parts, self.index, self.offset = parts, 0, 8

    def advance(self) -> None:
        while self.offset == len(self.parts[self.index][2]) and self.index + 1 < len(self.parts):
            self.index += 1
            self.offset = 0

    def read(self, size: int) -> bytes:
        result = bytearray()
        while size:
            self.advance()
            payload = self.parts[self.index][2]
            count = min(size, len(payload) - self.offset)
            require(count > 0, "truncated SST string metadata")
            result.extend(payload[self.offset : self.offset + count])
            self.offset += count
            size -= count
        return bytes(result)


def shared_strings(
    parts: List[Tuple[int, int, bytes]], parser: Parser
) -> List[Tuple[int, int, int]]:
    require(len(parts[0][2]) >= 8, "truncated SST counts")
    total, unique = struct.unpack_from("<II", parts[0][2])
    require(
        unique <= total and unique <= 100000 and (unique > 0 or total == 0),
        "SST string count bounds",
    )
    cursor, starts = StringCursor(parts), []
    for _ in range(unique):
        parser.budget.consume(nodes=1)
        cursor.advance()
        record, _, payload = parts[cursor.index]
        start = cursor.offset
        require(start + 3 <= len(payload), "SST fixed string header crosses record boundary")
        count, flags = struct.unpack_from("<HB", payload, start)
        require(count <= 32767 and not flags & ~13, "SST string count/flags")
        header_size = 3 + (2 if flags & 8 else 0) + (4 if flags & 4 else 0)
        require(start + header_size <= len(payload), "SST optional header crosses record boundary")
        starts.append((record + 4 + start, record, 4 + start))
        cursor.offset += 3
        runs = struct.unpack("<H", cursor.read(2))[0] if flags & 8 else 0
        extended = struct.unpack("<I", cursor.read(4))[0] if flags & 4 else 0
        width = 1 + (flags & 1)
        while count:
            payload = parts[cursor.index][2]
            available = len(payload) - cursor.offset
            if not available:
                require(cursor.index + 1 < len(parts), "truncated continued SST characters")
                cursor.index += 1
                cursor.offset = 0
                flag = cursor.read(1)[0]
                require(flag in (0, 1), "SST continuation encoding flag")
                width = 1 + flag
                continue
            take = min(count, available // width)
            require(
                take > 0 and (take == count or available % width == 0),
                "split double-byte SST character",
            )
            cursor.offset += take * width
            count -= take
        cursor.read(runs * 4 + extended)
    require(
        cursor.index == len(parts) - 1 and cursor.offset == len(parts[-1][2]),
        "unaccounted SST bytes/continuations",
    )
    return starts


def picture_object(data: bytes) -> None:
    position, types = 0, []
    while position < len(data):
        require(position + 4 <= len(data), "truncated Obj subrecord")
        kind, size = struct.unpack_from("<HH", data, position)
        position += 4
        require(
            position + size <= len(data) and kind in (0x15, 7, 8, 0),
            "unqualified linked/control/macro Obj subrecord",
        )
        if kind == 0x15:
            require(
                size == 18 and struct.unpack_from("<H", data, position)[0] == 8,
                "only embedded picture Obj is qualified",
            )
        else:
            require(size == (0 if kind == 0 else 2), "Obj subrecord length")
        types.append(kind)
        position += size
    require(types == [0x15, 7, 8, 0], "unqualified picture Obj sequence")


def worksheet_drawing(parts: List[bytes], parser: Parser) -> None:
    if not parts:
        return
    data = b"".join(parts)
    records = read_records(data)
    parser.budget.consume(nodes=len(records))
    require(
        all(DRAW_VERSIONS.get(r.kind) == r.flags & 15 for r in records.values()),
        "unqualified worksheet drawing type/version",
    )
    require(
        len([r for r in records.values() if r.parent is None]) == 1 and records[0].kind == 0xF002,
        "worksheet drawing root",
    )
    for at, record in records.items():
        if record.kind == 0xF122:
            # MS-ODRAW 2.2.11 / 2.3.7.43: only one scalar Fill Style
            # Boolean property, with neither fBid nor fComplex. Its exact
            # display bits stay in the unchanged worksheet byte manifest.
            require(
                record.flags == 0x13 and record.size == 6 and data[at + 8 : at + 10] == b"\xbf\x01",
                "unqualified tertiary worksheet property",
            )


@dataclass
class XlsArt:
    data: bytes
    start: int
    stop: int
    group: Record
    pointers: Dict[int, int]

    def fingerprint(self) -> Tuple[object, ...]:
        data = bytearray(self.data)
        for field, target in self.pointers.items():
            normalized = target - (self.stop - self.start) if target >= self.stop else target
            struct.pack_into("<I", data, field, normalized)
        return bytes(data[: self.start] + data[self.stop :]), self.group.fingerprint()

    def rebuild(self, payloads: Dict[int, bytes]) -> Dict[Tuple[str, ...], bytes]:
        group = self.group.encode(payloads)
        fragments = [group[i : i + 8224] for i in range(0, len(group), 8224)]
        wrapped = b"".join(
            struct.pack("<HH", 0xEB if i == 0 else 0x3C, len(part)) + part
            for i, part in enumerate(fragments)
        )
        delta = len(wrapped) - (self.stop - self.start)
        data = bytearray(self.data)
        for field, target in self.pointers.items():
            mapped = target + delta if target >= self.stop else target
            require(0 <= mapped <= 0xFFFFFFFF, "BIFF pointer overflow")
            struct.pack_into("<I", data, field, mapped)
        return {WORKBOOK: bytes(data[: self.start]) + wrapped + bytes(data[self.stop :])}


def inspect_xls(data: bytes, parser: Parser) -> XlsArt:  # noqa: C901
    # A linear record dispatch keeps substream state and pointer ownership visible.
    records = biff(data)
    parser.budget.consume(nodes=len(records))
    by_offset = {offset: (kind, payload) for offset, kind, payload in records}
    tabs = [p for _, k, p in records if k == 0x13D]
    require(len(tabs) <= 1, "duplicate RRTabId")
    if tabs:
        require(
            len(tabs[0]) == 2 * sum(k == 0x85 for _, k, _ in records),
            "RRTabId/BoundSheet inventory differs",
        )
        identifiers = struct.unpack("<" + "H" * (len(tabs[0]) // 2), tabs[0])
        require(len(set(identifiers)) == len(identifiers), "duplicate sheet identity")
    indices = [i for i, (_, kind, _) in enumerate(records) if kind == 0xEB]
    # MS-XLS product behavior note 6 permits a second MsoDrawingGroup
    # instead of the first Continue. It is a fragment of the same root,
    # not another drawing group; subsequent fragments must be Continue.
    require(
        bool(indices) and indices in ([indices[0]], [indices[0], indices[0] + 1]),
        "expected one global drawing group",
    )
    first, last = indices[0], indices[0] + 1
    if len(indices) == 2:
        last += 1
    while last < len(records) and records[last][1] == 0x3C:
        last += 1
    require(last < len(records), "drawing group outside globals")
    start, stop = records[first][0], records[last][0]
    drawing = b"".join(payload for _, _, payload in records[first:last])
    parsed = parser.sequence(drawing)
    require(len(parsed) == 1 and parsed[0].kind == 0xF000, "drawing group root")
    stores = [r for r in parsed[0].children if r.kind == 0xF001]
    require(
        len(stores) == 1 and all(len(r.children) == 1 for r in stores[0].children),
        "delayed/empty XLS BLIP stores are not qualified",
    )
    pointers: Dict[int, int] = {}
    pointer_kinds: Dict[int, int] = {}
    strings: List[Tuple[int, int, int]] = []
    string_continues = set()
    sst_indices = [i for i, (_, kind, _) in enumerate(records) if kind == 0xFC]
    require(len(sst_indices) <= 1, "duplicate SST")
    if sst_indices:
        sst_first, sst_last = sst_indices[0], sst_indices[0] + 1
        while sst_last < len(records) and records[sst_last][1] == 0x3C:
            string_continues.add(sst_last)
            sst_last += 1
        strings = shared_strings(records[sst_first:sst_last], parser)
    nesting, substream = 0, 0
    sheet_parts: List[bytes] = []
    sheet_db: List[int] = []
    sheet_indices: List[int] = []
    sheet_start = 0
    for index, (offset, kind, payload) in enumerate(records):
        if first <= index < last:
            require(nesting == 1 and substream == 5, "drawing group not in globals")
            continue
        if kind == 0x809:
            require(
                not nesting
                and struct.unpack_from("<HH", payload) == (0x600, 5 if offset == 0 else 0x10),
                "unknown/nested BIFF substream",
            )
            nesting = 1
            substream = struct.unpack_from("<H", payload, 2)[0]
            sheet_start, sheet_db, sheet_indices = offset, [], []
        else:
            require(nesting == 1, "BIFF record outside substream")
        if kind == 0xA:
            worksheet_drawing(sheet_parts, parser)
            require(
                sheet_db == sheet_indices or not sheet_db and not sheet_indices,
                "Index/DBCell inventory differs",
            )
            sheet_parts = []
            nesting = 0
        elif kind == 0xEC:
            require(substream == 0x10 and offset > stop, "worksheet drawing inside globals")
            sheet_parts.append(payload)
        elif kind == 0x3C:
            if index not in string_continues:
                require(
                    substream == 0x10
                    and records[index - 1][1] in (0xEC, 0x3C)
                    and bool(sheet_parts),
                    "CONTINUE outside qualified drawing/string records",
                )
                sheet_parts.append(payload)
        elif kind == 0x5D:
            require(substream == 0x10, "picture Obj inside globals")
            picture_object(payload)
        elif kind == 0x85:
            require(
                substream == 5 and offset < start and len(payload) >= 8 and payload[5] == 0,
                "only worksheet BoundSheet is qualified",
            )
            pointers[offset + 4] = struct.unpack_from("<I", payload)[0]
            pointer_kinds[offset + 4] = 0x809
        elif kind == 0x20B:
            require(
                substream == 0x10
                and len(payload) >= 16
                and (len(payload) - 16) % 4 == 0
                and not any(payload[:4]),
                "Index length/reserved fields",
            )
            low, high = struct.unpack_from("<II", payload, 4)
            require(low <= high <= 65536 and (low < high or low == high == 0), "Index row range")
            pointers[offset + 16] = struct.unpack_from("<I", payload, 12)[0]
            pointer_kinds[offset + 16] = 0x55
            for local in range(16, len(payload), 4):
                field = offset + 4 + local
                target = struct.unpack_from("<I", payload, local)[0]
                require(target >= sheet_start, "Index DBCell outside sheet")
                pointers[field], pointer_kinds[field] = target, 0xD7
                sheet_indices.append(target)
        elif kind == 0xFC:
            require(substream == 5, "SST outside globals")
        elif kind == 0xFF:
            require(
                substream == 5 and len(payload) >= 2 and (len(payload) - 2) % 8 == 0,
                "ExtSST bounds",
            )
            step = struct.unpack_from("<H", payload)[0]
            require(
                step > 0 and (len(payload) - 2) // 8 == (len(strings) + step - 1) // step,
                "ExtSST string bucket count",
            )
            for bucket, local in enumerate(range(2, len(payload), 8)):
                absolute, relative, reserved = struct.unpack_from("<IHH", payload, local)
                expected, _, cb = strings[bucket * step]
                require(
                    absolute == expected and relative == cb and reserved == 0,
                    "ExtSST bucket targets a different string",
                )
                pointers[offset + 4 + local] = absolute
        elif kind == 0xD7:
            require(
                substream == 0x10
                and len(payload) >= 4
                and (len(payload) - 4) % 2 == 0
                and len(payload) <= 68,
                "DBCell bounds",
            )
            back = struct.unpack_from("<I", payload)[0]
            if back:
                row = offset - back
                require(
                    row >= sheet_start and by_offset.get(row, (0,))[0] == 0x208,
                    "DBCell first Row target",
                )
                target = row + 4 + len(by_offset[row][1])
                for local in range(4, len(payload), 2):
                    target += struct.unpack_from("<H", payload, local)[0]
                    require(
                        target < offset and by_offset.get(target, (0,))[0] in CELLS,
                        "DBCell cell target",
                    )
            else:
                require(len(payload) == 4, "empty DBCell has cell offsets")
            sheet_db.append(offset)
        elif kind in CELLS:
            require(substream == 0x10 and len(payload) >= 6, "cell record outside worksheet")
            row, col = struct.unpack_from("<HH", payload)
            require(row < 65536 and col < 256, "cell coordinates")
            if kind == 0xFD:
                require(struct.unpack_from("<I", payload, 6)[0] < len(strings), "LabelSst index")
            elif kind == 0x6:
                require(
                    len(payload) >= 22
                    and 22 + struct.unpack_from("<H", payload, 20)[0] <= len(payload),
                    "Formula token bounds",
                )
            elif kind in (0xBD, 0xBE):
                stride = 6 if kind == 0xBD else 2
                require(
                    len(payload) >= 6 + stride
                    and (len(payload) - 6) % stride == 0
                    and struct.unpack_from("<H", payload, len(payload) - 2)[0]
                    == col + (len(payload) - 6) // stride - 1,
                    "multiple-cell record bounds",
                )
        elif kind == 0x863:
            require(
                len(payload) == 21
                and payload[:12] == bytes.fromhex("630800000000000000000000")
                and payload[12:20] == bytes.fromhex("1500000000000000"),
                "unqualified BookExt version",
            )
    require(nesting == 0 and bool(pointers), "missing/incomplete worksheet references")
    for field, target in pointers.items():
        require(not start <= target < stop, "BIFF pointer into replaced drawing bytes")
        if field in pointer_kinds:
            require(
                target in by_offset and by_offset[target][0] == pointer_kinds[field],
                "missing/stale BIFF file pointer",
            )
    return XlsArt(data, start, stop, parsed[0], pointers)
