"""Qualified inline DOC pictures, resolved through FIB, CLX, FKPs and styles.

Audited piece PRMs and style inheritance retain operand provenance. Mixed Data
accepts framed PICFs, binary fields, chained PrcData and zero padding; every
affected reference is relocated and overlapping/unknown blocks are rejected.
"""

import struct
import re
from dataclasses import dataclass, field as dataclass_field
from typing import Dict, List, Optional, Tuple, Union

from .format_support import Budget
from .ole_officeart import Parser, Record, require
from .ole_verify import CompoundFile
from .ole_word_data import DataReferences

DATA, WORD = ("Data",), ("WordDocument",)
_NONZERO = re.compile(rb"[^\0]")
# Audited font/language/revision identifiers, boolean character flags and simple
# paragraph/table formatting. None of the non-reference properties point to Data.
CHAR = {
    0x4A43,
    0x485F,
    0x4A61,
    0x486D,
    0x486E,
    0x4873,
    0x4874,
    0x6816,
    0x6A03,
    0x0855,
    0x0856,
    0x080A,
    0x0806,
    0x4A30,
    0x0835,
    0x0836,
    0x0837,
    0x0838,
    0x0839,
    0x083A,
    0x083B,
    0x083C,
    0x2A3E,
    0x2A42,
    0x2A48,
    0x4845,
    0x4A4F,
    0x2A53,
    0x0854,
    0x0858,
    # MS-DOC 2.6.1: fonts, bidi emphasis, colors/borders and direct flags/rsids.
    0x4A50, 0x4A51, 0x4A5E, 0x085C, 0x085D, 0x6870, 0x8840,
    0xCA71, 0xCA72, 0x6815, 0x0875, 0x0802, 0x0811,
    # Revision authors/timestamps, border, underline color and highlighting.
    0x0800, 0x0801, 0x4804, 0x6805, 0x6817, 0x4863, 0x6864,
    0x6865, 0x6877, 0xCA89, 0x2A83, 0x2A0C,
    0xCA85,  # CCnf: validated conditional table-style formatting below.
}
PARA = {
    0x6412, 0xA413, 0xA414, 0x2640, 0x246D, 0x6426, 0xC650,
    0x840F, 0x845E, 0x245B, 0x245C, 0x840E, 0x845D, 0x2403,
    0x2461, 0xC60D, 0x8411, 0x8460, 0x260A, 0x460B, 0x6467,
    0x2406, 0x2416, 0x6649, 0x2417, 0xC66C,
    # Pagination, East Asian spacing/alignment and legacy/current borders.
    0x2431, 0x2437, 0x2438, 0x2448, 0x2405, 0x2407, 0x4439,
    0x6424, 0x6425, 0x6427, 0x6428, 0x6629,
    0xC64E, 0xC64F, 0xC651, 0xC652, 0xC653,
    0xC615, 0xC666,  # Exceptional tab-stop framing and conditional style.
}
# MS-DOC 2.6.3: cell widths, borders/shading, padding, merges and table styles.
# Ordinary operands carry no stream offsets; TCnf's nested array is validated.
TABLE = {
    0x563A, 0xF617, 0xD634, 0xF661, 0x9601, 0x9602, 0x9407,
    0xD608, 0x740A, 0xF614, 0x3615, 0xD61A, 0xD61B, 0xD61C,
    0xD61D, 0x7479, 0xF618, 0xD642, 0xD670, 0x7621, 0xD635,
    0x7623, 0xD62C, 0xD639, 0xD62F, 0xD609, 0xD612,
    0xD613, 0xD605, 0x3404, 0x3488, 0x3489,
    0xD66A, 0xD687,  # Conditional table-style formatting and shading.
}
PARA_REFS = {0x6646, 0x646B}  # HugePapx and TableProps -> Data.PrcData.
SPECIAL = {0x6A03, 0x0855, 0x0856, 0x080A, 0x0806}
# MS-DOC 2.9.336 excludes properties preserved by sprmCIstd (2.6.1).
# Pictures/OLE identity, special-character flags and revision IDs cannot be
# supplied by a style; their provenance must remain in direct/piece formatting.
STYLE_CHAR = CHAR - SPECIAL - {
    0x4A30, 0x6816, 0x6815, 0x0875, 0x0802, 0x0811,
    0x0800, 0x0801, 0x4804, 0x6805, 0x6817, 0x4863, 0x6864,
    0xCA89, 0x2A83, 0x2A0C,
}
CONDITIONAL = {0xCA85, 0xC666, 0xD66A}
# UpxTapx-permitted offset-free properties and the six TCnf border exceptions.
CONDITIONAL_TABLE = {
    0xD634, 0xF661, 0xD605, 0xD613, 0xD687, 0x3488, 0x3489,
    0xD47F, 0xD680, 0xD681, 0xD682, 0xD683, 0xD684,
}


def u16(data: Union[bytes, bytearray], offset: int) -> int:
    require(0 <= offset <= len(data) - 2, "truncated Word ushort")
    return int(struct.unpack_from("<H", data, offset)[0])


def u32(data: Union[bytes, bytearray], offset: int) -> int:
    require(0 <= offset <= len(data) - 4, "truncated Word uint")
    return int(struct.unpack_from("<I", data, offset)[0])


def properties(
    data: bytes, base: int, allowed: set, *, table_style: bool = False
) -> Dict[int, Tuple[int, bytes]]:
    result = {}
    offset = 0
    sizes = (1, 1, 2, 4, 2, 2, 0, 3)
    while offset < len(data):
        code = u16(data, offset)
        require(code in allowed, "unsupported Word property: " + hex(code))
        require(
            code not in SPECIAL | PARA_REFS or code not in result,
            "duplicate Word reference property: " + hex(code),
        )
        start = offset + 2
        size = sizes[code >> 13]
        if not size:
            require(start < len(data), "truncated variable Word property")
            # TDefTable has a two-byte cb counting the remainder plus one.
            size = 1 + (u16(data, start) if code == 0xD608 else data[start])
            require(code != 0xD608 or size >= 3, "invalid TDefTable length")
        if code == 0xC615:
            size = tab_operand_size(data, start)
        require(start + size <= len(data), "truncated Word property operand")
        if code in CONDITIONAL:
            require(table_style, "conditional formatting outside a Word table style")
            operand = data[start : start + size]
            require(
                size >= 3 and u16(operand, 1) in {1 << n for n in range(12)},
                "invalid Word conditional formatting condition",
            )
            nested = {
                0xCA85: STYLE_CHAR - CONDITIONAL,
                0xC666: PARA - CONDITIONAL - {0xC615, 0x2416, 0x2417, 0x6649, 0x6467, 0xC66C},
                0xD66A: CONDITIONAL_TABLE,
            }[code]
            # Nested formatting cannot own relocated Data references. Do not
            # inherit its values into the unconditional picture properties.
            properties(operand[3:], base + start + 3, nested)
        result[code] = (base + start, data[start : start + size])
        offset = start + size
    return result


def tab_operand_size(data: bytes, start: int) -> int:
    require(start + 2 <= len(data), "truncated Word tab-stop operand")
    cb, deleted = data[start], data[start + 1]
    added_at = start + 2 + 4 * deleted
    require(deleted <= 64 and added_at < len(data), "Word deleted tab-stop bounds")
    added = data[added_at]
    size = 3 + 4 * deleted + 3 * added
    require(
        added <= 64 and start + size <= len(data) and cb in (size - 1, 255),
        "Word tab-stop length/count bounds",
    )
    return size


def style_properties(
    data: bytes, budget: Budget, *, base: int = 0, resolved: Optional[Dict] = None
) -> Dict[int, int]:
    cb = u16(data, 0)
    require(cb >= 18 and 2 + cb <= len(data), "Word stylesheet header bounds")
    count, base_size = u16(data, 2), u16(data, 4)
    require(15 <= count < 4094 and base_size in (10, 18), "Word stylesheet version/count")
    position = 2 + cb
    bases, kinds, chars_by_style = {}, {}, {}
    for index in range(count):
        budget.consume(nodes=1)
        size = u16(data, position)
        position += 2
        require(size <= len(data) - position, "truncated Word style")
        body_start = position
        body = data[position : position + size]
        position += size + size % 2
        if not size:
            continue
        require(size >= base_size + 4 and u16(body, 6) == size, "Word style base/length")
        kind, parent = u16(body, 2) & 15, u16(body, 2) >> 4
        cupx = u16(body, 4) & 15
        require(
            kind in (1, 2, 3, 4) and cupx == {1: 2, 2: 1, 3: 3, 4: 1}[kind],
            "revision-marked/unknown Word style",
        )
        bases[index] = parent
        kinds[index] = kind
        chars = u16(body, base_size)
        offset = base_size + 2 + 2 * chars
        require(
            offset + 2 <= size and body[offset : offset + 2] == b"\0\0", "Word style name bounds"
        )
        offset += 2
        for part in range(cupx):
            length = u16(body, offset)
            offset += 2
            require(length <= size - offset, "truncated style formatting")
            grp = body[offset : offset + length]
            offset += length + length % 2
            char_part = kind == 2 or kind == 1 and part == 1 or kind == 3 and part == 2
            if char_part:
                parsed = properties(
                    grp, base + body_start + offset - length - length % 2, CHAR,
                    table_style=kind == 3,
                )
                for code in parsed:
                    require(code in STYLE_CHAR, "forbidden Word style property: " + hex(code))
                chars_by_style[index] = {k: (-at - 1, value) for k, (at, value) in parsed.items()}
            elif kind == 3 and part == 0:
                properties(grp, 0, TABLE, table_style=True)
            else:
                require(len(grp) >= 2, "truncated style paragraph index")
                properties(grp[2:], 0, PARA | TABLE, table_style=kind == 3)
        require(offset == size, "unaccounted style formatting bytes")
    require(position == len(data), "unaccounted stylesheet bytes")
    for index in bases:
        seen = set()
        parent = index
        while parent != 4095:
            budget.consume(nodes=1)
            require(parent in bases and parent not in seen, "invalid/cyclic style inheritance")
            seen.add(parent)
            parent = bases[parent]
    if resolved is not None:
        for index in bases:
            chain, parent, parsed = [], index, {}
            while parent != 4095:
                chain.append(parent)
                parent = bases[parent]
            for parent in reversed(chain):
                parsed.update(chars_by_style.get(parent, {}))
            resolved[index] = parsed
    return kinds


def fib_slice(word: bytes, table: bytes, index: int) -> bytes:
    start, size = u32(word, 154 + 8 * index), u32(word, 158 + 8 * index)
    require(
        size > 0 and start <= len(table) and size <= len(table) - start, "Word FIB table bounds"
    )
    return table[start : start + size]


SMALL_PRMS = {
    0x41: 0x0800,
    0x42: 0x0801,
    0x43: 0x0802,
    0x4B: 0x080A,
    0x55: 0x0835,
    0x56: 0x0836,
    0x57: 0x0837,
    0x58: 0x0838,
    0x59: 0x0839,
    0x5A: 0x083A,
    0x5B: 0x083B,
    0x5C: 0x083C,
    0x5E: 0x2A3E,
    0x62: 0x2A42,
    0x68: 0x2A48,
    0x75: 0x0855,
    0x76: 0x0856,
}


def pieces(
    word: bytes, table: bytes, modifiers: Optional[Dict] = None
) -> List[Tuple[int, int, int]]:
    base = u32(word, 154 + 8 * 33)
    clx = fib_slice(word, table, 33)
    pos, prcs = 0, []
    while pos < len(clx) and clx[pos] == 1:
        size = u16(clx, pos + 1)
        pos += 3
        require(pos + size <= len(clx), "piece PRC bounds")
        parsed = properties(clx[pos : pos + size], base + pos, CHAR | PARA | TABLE)
        require(0x0806 not in parsed, "piece Data property is not qualified")
        prcs.append({k: (-at - 1, value) for k, (at, value) in parsed.items() if k in CHAR})
        pos += size
    require(
        pos + 5 <= len(clx) and clx[pos] == 2 and u32(clx, pos + 1) == len(clx) - pos - 5,
        "piece table CLX envelope",
    )
    table_base = base + pos + 5
    data = clx[pos + 5 :]
    require(len(data) >= 16 and (len(data) - 4) % 12 == 0, "piece table bounds")
    count = (len(data) - 4) // 12
    require(0 < count <= 8192, "Word piece count limit")
    cps = [u32(data, i * 4) for i in range(count + 1)]
    require(cps[0] == 0 and all(a < b for a, b in zip(cps, cps[1:])), "piece CP order")
    result: List[Tuple[int, int, int]] = []
    for i in range(count):
        pcd = 4 * (count + 1) + i * 8
        fc, prm = u32(data, pcd + 2), u16(data, pcd + 6)
        require(not fc & 0x80000000, "unknown text encoding")
        parsed = {}
        if prm & 1:
            require(prm >> 1 < len(prcs), "piece PRC index")
            parsed = prcs[prm >> 1]
        elif prm:
            code = SMALL_PRMS.get((prm >> 1) & 127)
            require(code in CHAR, "unqualified small piece PRM")
            assert code is not None
            parsed = {code: (-table_base - pcd - 8, bytes([prm >> 8]))}
        unit = 1 if fc & 0x40000000 else 2
        offset = (fc & 0x3FFFFFFF) // (2 if unit == 1 else 1)
        end = offset + unit * (cps[i + 1] - cps[i])
        require(end <= len(word), "text piece outside WordDocument")
        require(
            all(end <= start or offset >= stop for start, stop, _ in result),
            "aliased/overlapping text pieces",
        )
        result.append((offset, end, unit))
        if modifiers is not None:
            modifiers[offset] = parsed
    return result


def fkps(
    word: bytes, table: bytes, index: int, budget: Budget
) -> List[Tuple[int, int, int, bytes]]:
    plc = fib_slice(word, table, index)
    require(len(plc) >= 12 and (len(plc) - 4) % 8 == 0, "FKP index bounds")
    count = (len(plc) - 4) // 8
    bounds = [u32(plc, i * 4) for i in range(count + 1)]
    require(all(a < b for a, b in zip(bounds, bounds[1:])), "FKP index FC order")
    result, pages = [], set()
    for i in range(count):
        page = u32(plc, 4 * (count + 1) + 4 * i)
        require(page not in pages and page * 512 + 512 <= len(word), "FKP page alias/bounds")
        pages.add(page)
        data = word[page * 512 : (page + 1) * 512]
        runs = data[511]
        require(0 < runs <= (101 if index == 12 else 29), "FKP run count")
        fc = [u32(data, j * 4) for j in range(runs + 1)]
        require(
            fc[0] == bounds[i]
            and fc[-1] == bounds[i + 1]
            and all(a < b for a, b in zip(fc, fc[1:])),
            "FKP run FC order/coverage",
        )
        prefix = 4 * (runs + 1) + runs * (1 if index == 12 else 13)
        intervals: List[Tuple[int, int]] = []
        for j in range(runs):
            budget.consume(nodes=1)
            start = data[4 * (runs + 1) + j * (1 if index == 12 else 13)] * 2
            if not start:
                require(index == 12, "missing paragraph FKP properties")
                result.append((fc[j], fc[j + 1], 0, b""))
                continue
            require(prefix <= start < 511, "FKP property location overlaps index")
            original_start = start
            if index == 12:
                length, start = data[start], start + 1
            elif data[start]:
                length, start = 2 * data[start] - 1, start + 1
            else:
                require(start + 1 < 511 and data[start + 1] > 0, "Papx length")
                length, start = 2 * data[start + 1], start + 2
            require(start + length <= 511, "FKP property bounds")
            interval = (original_start, start + length)
            require(
                all(
                    interval == other or interval[1] <= other[0] or interval[0] >= other[1]
                    for other in intervals
                ),
                "partially aliased FKP properties",
            )
            intervals.append(interval)
            result.append((fc[j], fc[j + 1], page * 512 + start, data[start : start + length]))
    return result


def _direct_character_properties(
    grp: bytes, base: int, styles: Dict[int, int]
) -> Dict[int, Tuple[int, bytes]]:
    parsed = properties(grp, base, CHAR)
    if 0x4A30 in parsed:
        require(styles.get(u16(parsed[0x4A30][1], 0)) == 2, "character style index")
    for code in (0x0855, 0x0856, 0x080A, 0x0806):
        require(code not in parsed or parsed[code][1] in (b"\0", b"\1"),
                "inherited/toggled picture boolean is not qualified")
    return parsed


def picture_references(
    compound: CompoundFile, budget: Budget, data_refs: Optional[DataReferences] = None
) -> Dict[int, int]:
    if data_refs is None:
        data_refs = DataReferences(compound.streams.get(DATA, b""), budget)
    word = compound.streams[WORD]
    require(
        u16(word, 0) == 0xA5EC
        and u16(word, 2) == 0xC1
        and u16(word, 8) == 0
        and not u16(word, 10) & 1
        and u16(word, 32) == 14
        and u16(word, 62) == 22
        and u16(word, 152) in (93, 108, 136, 164, 183),
        "unqualified Word FIB/version",
    )
    table = compound.streams[("1Table" if u16(word, 10) & 0x200 else "0Table",)]
    resolved: Dict[int, Dict[int, Tuple[int, bytes]]] = {}
    modifiers: Dict[int, Dict[int, Tuple[int, bytes]]] = {}
    styles = style_properties(
        fib_slice(word, table, 1), budget, base=u32(word, 162), resolved=resolved
    )
    ranges = pieces(word, table, modifiers)
    fib_end = 154 + 8 * u16(word, 152)
    extended_count = u16(word, fib_end)
    version = u16(word, fib_end + 2) if extended_count else u16(word, 2)
    require(
        (u16(word, 152), extended_count, version)
        in {(93, 0, 0xC1), (108, 2, 0xD9), (136, 2, 0x101), (164, 2, 0x10C), (183, 5, 0x112)},
        "unqualified extended Word FIB/version",
    )
    fib_end += 2 + 2 * extended_count
    require(
        fib_end <= len(word) and all(start >= fib_end for start, _, _ in ranges),
        "text piece overlaps FIB",
    )
    pages = set()
    for index in (12, 13):
        plc = fib_slice(word, table, index)
        require(len(plc) >= 12 and (len(plc) - 4) % 8 == 0, "FKP index bounds")
        count = (len(plc) - 4) // 8
        for i in range(count):
            page = u32(plc, 4 * (count + 1) + i * 4)
            start, stop = page * 512, (page + 1) * 512
            require(
                page not in pages
                and start >= fib_end
                and all(stop <= low or start >= high for low, high, _ in ranges),
                "formatting page overlaps FIB/text/another FKP",
            )
            pages.add(page)
    paragraphs = fkps(word, table, 13, budget)
    for _, _, base, grp in paragraphs:
        require(len(grp) >= 2, "paragraph style index bounds")
        require(styles.get(u16(grp, 0)) == 1, "unqualified paragraph style index")
        require(grp[2:4] != b"\x46\x66" or (len(grp) == 8 and u16(grp, 0) == 0),
                "HugePapx requires a sole operand and zero paragraph style")
        data_refs.paragraph(grp[2:], base + 2)
    refs: Dict[int, int] = {}
    roles: Dict[int, set] = {}
    covered = []
    for first, last, base, grp in fkps(word, table, 12, budget):
        direct = _direct_character_properties(grp, base, styles)
        for start, stop, unit in ranges:
            low, high = max(first, start), min(last, stop)
            if low >= high:
                continue
            require((low - start) % unit == 0 and (high - low) % unit == 0, "text/FKP alignment")
            covered.append((low, high))
            require(
                sum(max(0, min(high, plast) - max(low, pfirst))
                    for pfirst, plast, _, _ in paragraphs) == high - low,
                "paragraph-formatting coverage",
            )
            # Styles cannot supply picture/binary identity. Text runs without
            # either direct or piece-owned identity need no per-character walk.
            if 0x6A03 not in direct and 0x6A03 not in modifiers[start]:
                require(0x0806 not in direct, "binary Data lacks a direct location")
                continue
            for offset in range(low, high, unit):
                budget.consume(nodes=1)
                paragraph = [
                    u16(pgrp, 0)
                    for pfirst, plast, _, pgrp in paragraphs
                    if pfirst <= offset < plast
                ]
                require(len(paragraph) == 1, "paragraph-formatting coverage")
                parsed = dict(resolved[paragraph[0]])
                if 0x4A30 in direct:
                    style = u16(direct[0x4A30][1], 0)
                    require(styles.get(style) == 2, "character style index")
                    parsed.update(resolved[style])
                parsed.update(direct)
                parsed.update(modifiers[start])
                for code in (0x0855, 0x0856, 0x080A, 0x0806):
                    require(
                        code not in parsed or parsed[code][1] in (b"\0", b"\1"),
                        "unqualified toggled picture property",
                    )
                char = word[offset] if unit == 1 else u16(word, offset)
                if 0x6A03 in parsed:
                    role = ("binary" if parsed.get(0x0806, (0, b"\0"))[1] == b"\1"
                            else "picture") if char == 1 else "other"
                    roles.setdefault(parsed[0x6A03][0], set()).add(role)
                if char != 1:
                    continue  # U+0014's OLE IDs and ignored operands stay opaque/exact.
                require(
                    0x6A03 in parsed
                    and parsed.get(0x0855, (0, b""))[1] == b"\x01"
                    and parsed.get(0x0856, (0, b"\0"))[1] == b"\0"
                    and parsed.get(0x080A, (0, b"\0"))[1] == b"\0",
                    "picture lacks direct unambiguous character properties",
                )
                field, value = parsed[0x6A03]
                target = struct.unpack("<I", value)[0]
                require(
                    target <= 0x7FFFFFFF and (field not in refs or refs[field] == target),
                    "ambiguous picture target",
                )
                if parsed.get(0x0806, (0, b"\0"))[1] == b"\1":
                    require(high - low == unit and last - first == unit,
                            "binary Data character range is not singular")
                    data_refs.binary(target)
                    data_refs.refs[field] = target
                else:
                    refs[field] = target
    require(
        sum(b - a for a, b in covered) == sum(b - a for a, b, _ in ranges),
        "incomplete character-formatting coverage",
    )
    require(bool(refs), "no qualified inline pictures")
    require(
        all(target == 0 or roles[field] == {"picture"} for field, target in refs.items()),
        "picture operand also applies to non-picture text",
    )
    require(all(roles[field] == {"binary"} for field in data_refs.refs if field in roles),
            "binary operand also applies to other text")
    return refs


@dataclass
class WordArt:
    word: bytes
    data: bytes
    refs: Dict[int, int]
    blocks: Tuple[Tuple[int, bytes, Tuple[Record, ...]], ...]
    padding: bytes
    table: bytes = b""
    table_path: Tuple[str, ...] = ("1Table",)
    gaps: Tuple[bytes, ...] = ()
    data_refs: Dict[int, int] = dataclass_field(default_factory=dict)

    @property
    def changed(self) -> set:
        return {WORD, DATA} | ({self.table_path} if any(at < 0 for at in self.refs) else set())

    def fingerprint(self) -> Tuple[object, ...]:
        indices = {start: i for i, (start, _, _) in enumerate(self.blocks)}
        word, table = bytearray(self.word), bytearray(self.table)
        for field, target in self.refs.items():
            struct.pack_into(
                "<I",
                word if field >= 0 else table,
                field if field >= 0 else -field - 1,
                indices[target],
            )
        blocks = []
        for start, prefix, records in self.blocks:
            normalized = bytearray(prefix)
            if records:
                struct.pack_into("<I", normalized, 0, 0)
            for at, target in self.data_refs.items():
                if start <= at < start + len(prefix):
                    struct.pack_into("<I", normalized, at - start, indices[target])
            blocks.append((bytes(normalized), tuple(r.fingerprint() for r in records)))
        return (
            bytes(word),
            bytes(table) if any(at < 0 for at in self.refs) else None,
            tuple(blocks),
            self.padding,
            self.gaps,
        )

    def rebuild(self, payloads: Dict[int, bytes]) -> Dict[Tuple[str, ...], bytes]:
        word, table, data, mapping = bytearray(self.word), bytearray(self.table), bytearray(), {}
        for i, (start, prefix, records) in enumerate(self.blocks):
            if self.gaps:
                data.extend(self.gaps[i])
            mapping[start] = len(data)
            body = b"".join(record.encode(payloads) for record in records)
            framed = bytearray(prefix)
            if records:
                struct.pack_into("<I", framed, 0, len(framed) + len(body))
            data.extend(framed + body)
        data.extend(self.padding)
        for at, target in self.data_refs.items():
            owner = next(start for start, prefix, _ in self.blocks
                         if start <= at <= start + len(prefix) - 4)
            struct.pack_into("<I", data, mapping[owner] + at - owner, mapping[target])
        for field, target in self.refs.items():
            struct.pack_into(
                "<I",
                word if field >= 0 else table,
                field if field >= 0 else -field - 1,
                mapping[target],
            )
        replacements: Dict[Tuple[str, ...], bytes] = {WORD: bytes(word), DATA: bytes(data)}
        if any(at < 0 for at in self.refs):
            replacements[self.table_path] = bytes(table)
        return replacements


def inspect_word(compound: CompoundFile, parser: Parser) -> WordArt:
    require(DATA in compound.streams, "no inline picture Data stream")
    data_refs = DataReferences(compound.streams[DATA], parser.budget)
    refs = picture_references(compound, parser.budget, data_refs)
    data, end, gaps, gap = compound.streams[DATA], 0, [], bytearray()
    blocks: List[Tuple[int, bytes, Tuple[Record, ...]]] = []
    targets = set(refs.values())
    refs.update(data_refs.refs)
    for start in targets:
        data_refs.region(start, u32(data, start), "picture")
    while end < len(data):
        parser.budget.consume(nodes=1)
        nonzero = _NONZERO.search(data, end)
        if nonzero is None:
            break
        start = end
        if start in data_refs.regions and data_refs.regions[start][1] != "picture":
            size, _ = data_refs.regions[start]
            end = start + size
            require(not any(start < target < end for target in data_refs.regions),
                    "overlapping Data regions")
            gaps.append(bytes(gap))
            gap.clear()
            blocks.append((start, data[start:end], ()))
            continue
        if u32(data, start) == 0:
            amount = ((nonzero.start() - end) // 4) * 4
            require(amount >= 4, "mixed Data padding bounds")
            gap.extend(data[start : start + amount])
            end += amount
            continue
        require(start + 68 <= len(data), "mixed Data block header bounds")
        size = u32(data, start)
        require(
            68 < size <= len(data) - start
            and u16(data, start + 4) == 68
            and u16(data, start + 6) == 100,
            "unqualified PICF size/format",
        )
        end = start + size
        require(not any(start < target < end for target in data_refs.regions),
                "partially aliased PICF target")
        gaps.append(bytes(gap))
        gap.clear()
        if start in targets:
            records = parser.sequence(data[start + 68 : end])
            require(
                len(records) == 2
                and records[0].kind == 0xF004
                and records[1].kind == 0xF007
                and len(records[1].children) == 1,
                "unqualified inline shape/BLIP layout",
            )
            blocks.append((start, data[start : start + 68], records))
        else:
            # Unreferenced PICFs are fully framed and kept byte-identical. Never
            # recompress history/orphans or guess a consumer for their bytes.
            from .ole_ppt import read_records

            opaque = read_records(data[start + 68 : end])
            parser.budget.consume(nodes=len(opaque))
            roots = [r.kind for r in opaque.values() if r.parent is None]
            require(roots == [0xF004, 0xF007], "unqualified unreferenced Data block")
            blocks.append((start, data[start:end], ()))
    require(set(data_refs.regions) <= {start for start, _, _ in blocks},
            "missing/stale Data region target")
    table_path = ("1Table" if u16(compound.streams[WORD], 10) & 512 else "0Table",)
    return WordArt(
        compound.streams[WORD],
        data,
        refs,
        tuple(blocks),
        bytes(gap) + data[end:],
        compound.streams[table_path],
        table_path,
        tuple(gaps),
        data_refs.internal,
    )
