"""Word floating pictures in a completely covered final WordDocument delay store.

The prefix (text, FKPs, object IDs) is never relocated. Other placements are
explicitly rejected. Table references are resolved from the complete FIB index.
"""

import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .ole_officeart import BLIPS, Parser, Record, require
from .ole_ppt import read_records
from .ole_verify import CompoundFile
from .ole_word_art import WORD, fib_slice, fkps, pieces, u16, u32


@dataclass
class FloatingWordArt:
    word: bytes
    table: bytes
    table_path: Tuple[str, ...]
    group_start: int
    group_end: int
    group: Record
    drawings: bytes
    pictures_start: int
    pictures: Tuple[Record, ...]
    refs: Dict[int, int]
    table_pointers: Dict[int, int]

    @property
    def changed(self) -> set:
        return {WORD, self.table_path}

    def fingerprint(self) -> Tuple[object, ...]:
        word, table = bytearray(self.word[: self.pictures_start]), bytearray(self.table)
        struct.pack_into("<I", word, 64, 0)  # cbMac
        for field, index in self.refs.items():
            struct.pack_into("<II", table, field, 0, u32(table, field + 4))
            struct.pack_into("<I", table, field + 8, index)
        # Embedded store spans are represented structurally. Delayed entries
        # include normalized references in the table, preserving counts/UIDs.
        for field, target in self.table_pointers.items():
            if target >= self.group_end:
                struct.pack_into("<I", word, field, target - (self.group_end - self.group_start))
        struct.pack_into("<I", word, 558, 0)
        return (
            bytes(word),
            bytes(table[: self.group_start] + table[self.group_end :]),
            self.normalized_group(),
            self.drawings,
            tuple(r.fingerprint() for r in self.pictures),
        )

    def normalized_group(self) -> Tuple[object, ...]:
        # Delayed FBSE sizes/positions are the only non-codec fields patched.
        def fp(record: Record) -> Tuple[object, ...]:
            if record.kind == 0xF007 and not record.children:
                body = bytearray(record.body)
                absolute = self.group_start + next(
                    pos
                    for pos, r in read_records(
                        self.table[self.group_start : self.group_end - len(self.drawings)]
                    ).items()
                    if r.kind == 0xF007
                    and self.table[self.group_start + pos + 8 : self.group_start + pos + 8 + r.size]
                    == record.body
                )
                index = self.refs[absolute + 28]
                struct.pack_into("<I", body, 20, 0)
                struct.pack_into("<I", body, 28, index)
                return record.flags, record.kind, bytes(body)
            if record.children:
                return record.flags, record.kind, tuple(fp(c) for c in record.children)
            return record.fingerprint()

        return fp(self.group)

    def rebuild(self, payloads: Dict[int, bytes]) -> Dict[Tuple[str, ...], bytes]:
        word = bytearray(self.word[: self.pictures_start])
        locations, blobs = [], []
        for picture in self.pictures:
            locations.append(len(word))
            blob = picture.encode(payloads)
            word.extend(blob)
            blobs.append(blob)
        table = bytearray(self.table)
        for field, index in self.refs.items():
            struct.pack_into("<I", table, field, len(blobs[index]))
            struct.pack_into("<I", table, field + 8, locations[index])
        # Reparse the modified delayed group so encode preserves patched fields.
        group_size = 8 + len(self.group.body)
        group = self.group.encode(payloads)
        if self.refs:
            # This profile admits exclusively delayed entries, so group encoding
            # has no content changes and the patched original bytes are retained.
            group = bytes(table[self.group_start : self.group_start + group_size])
        wrapped = group + self.drawings
        delta = len(wrapped) - (self.group_end - self.group_start)
        for field, target in self.table_pointers.items():
            struct.pack_into(
                "<I", word, field, target + delta if target >= self.group_end else target
            )
        struct.pack_into("<I", word, 558, len(wrapped))
        struct.pack_into("<I", word, 64, len(word))
        return {
            WORD: bytes(word),
            self.table_path: bytes(table[: self.group_start])
            + wrapped
            + bytes(table[self.group_end :]),
        }


def inspect_floating(compound: CompoundFile, parser: Parser) -> FloatingWordArt:
    word = compound.streams[WORD]
    require(
        u16(word, 32) == 14 and u16(word, 62) == 22 and u16(word, 152) in (93, 108, 136, 164, 183),
        "floating Word FIB structure",
    )
    table_path = ("1Table" if u16(word, 10) & 512 else "0Table",)
    table = compound.streams[table_path]
    start, size = u32(word, 554), u32(word, 558)
    require(size > 8 and start + size <= len(table), "missing/invalid floating OfficeArtContent")
    group_size = 8 + u32(table, start + 4)
    require(group_size <= size, "drawing group bounds")
    group = parser.sequence(table[start : start + group_size])
    require(len(group) == 1 and group[0].kind == 0xF000, "floating drawing group root")
    drawings = table[start + group_size : start + size]
    pos, scopes = 0, []
    while pos < len(drawings):
        require(drawings[pos] in (0, 1) and drawings[pos] not in scopes, "floating drawing scope")
        scopes.append(drawings[pos])
        pos += 1
        require(pos + 8 <= len(drawings), "drawing header bounds")
        count = 8 + u32(drawings, pos + 4)
        require(pos + count <= len(drawings), "drawing container bounds")
        children = read_records(drawings[pos : pos + count])
        require(children[0].kind == 0xF002, "floating drawing container root")
        # No consumer indices change in recompression. Preserve all drawing bytes.
        pos += count
    require(bool(scopes), "missing floating drawing consumers")
    stores = [r for r in group[0].children if r.kind == 0xF001]
    require(
        len(stores) == 1 and all(not r.children for r in stores[0].children),
        "this floating profile requires a delayed BStore",
    )
    positions = read_records(table[start : start + group_size])
    entries = [(start + at, r) for at, r in positions.items() if r.kind == 0xF007]
    targets = {}
    for at, record in entries:
        body = table[at + 8 : at + 8 + record.size]
        require(record.size == 36 and u32(body, 24) > 0, "floating FBSE name/count")
        target = u32(body, 28)
        require(
            target not in targets and target + u32(body, 20) <= len(word),
            "aliased/out-of-bounds floating delay target",
        )
        targets[target] = (at + 28, body)
    picture_start = min(targets) if targets else len(word)
    require(
        bool(targets) and picture_start >= u32(word, 28) and u32(word, 64) == len(word),
        "floating delay store overlaps text or cbMac differs",
    )
    require(
        all(stop <= picture_start for _, stop, _ in pieces(word, table)),
        "floating delay store overlaps a text piece",
    )
    for index in (12, 13):
        fkps(word, table, index, parser.budget)
        plc = fib_slice(word, table, index)
        count = (len(plc) - 4) // 8
        require(
            all(
                (u32(plc, 4 * (count + 1) + 4 * i) + 1) * 512 <= picture_start for i in range(count)
            ),
            "floating delay store overlaps formatting pages",
        )
    pictures: List[Record] = []
    refs: Dict[int, int] = {}
    end = picture_start
    for target, (field, body) in sorted(targets.items()):
        require(target == end, "mixed/unreferenced floating delay spans")
        end = target + u32(body, 20)
        parsed = parser.sequence(word[target:end])
        require(len(parsed) == 1 and parsed[0].kind in BLIPS, "floating delay target type")
        picture = parsed[0]
        uid_size = 16 * (1 + (picture.flags >> 4 == BLIPS[picture.kind][1]))
        require(body[2:18] == picture.body[uid_size - 16 : uid_size], "floating FBSE UID differs")
        refs[field] = len(pictures)
        pictures.append(picture)
    require(end == len(word), "floating delay store does not completely cover final suffix")
    pointers = {}
    for i in range(u16(word, 152)):
        if i == 87:  # dwLowDateTime/dwHighDateTime, not an fc/lcb pair.
            continue
        field = 154 + i * 8
        fc, lcb = u32(word, field), u32(word, field + 4)
        if not lcb or i == 50:
            continue
        require(
            fc + lcb <= len(table) and (fc + lcb <= start or fc >= start + size),
            "FIB table interval overlaps drawings or is unqualified",
        )
        pointers[field] = fc
    return FloatingWordArt(
        word,
        table,
        table_path,
        start,
        start + size,
        group[0],
        drawings,
        picture_start,
        tuple(pictures),
        refs,
        pointers,
    )
