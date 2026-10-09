"""Audited immutable PPT extension forms for Pictures-only rewriting.

MS-PPT 2.5.2/7/24, 2.9 and 2.11; payload references are logical IDs, not
Pictures byte positions. Unknown forms remain outside this profile.
"""

import struct
from typing import Dict, List, Optional, Set, Tuple

from .format_support import Budget
from .ole_ppt import PptRecord, read_records
from .ole_ppt_records import _VERSIONS, _require

# kind: (version, admitted instances, owners, exact size or variable).
_EXTRA: Dict[int, Tuple[int, Tuple[int, ...], Tuple[Optional[int], ...], Optional[int]]] = {
    1008: (15, (0,), (None,), None),
    1009: (1, (0,), (1008,), 8),
    1017: (0, (0,), (1006,), 16),
    1025: (1, (0,), (1000,), 80),
    1031: (15, (1,), (2000,), None),
    1038: (0, (0,), (1008, 1016), None),
    1039: (0, (0,), (1008, 1016), None),
    1052: (0, (0,), (1016,), 4),
    1053: (0, (0,), (1006, 1016), 4),
    1054: (0, tuple(range(1, 12)), (1016,), None),
    1055: (0, (0,), (61457,), 4),
    1056: (0, (0,), (61457,), 1),
    1058: (0, (0,), (1006,), 8),
    1059: (0, (0,), (1016,), None),
    1063: (0, (0,), (1008,), None),
    1064: (0, (0,), (1000,), None),
    4006: (0, (0,), (61453,), None),
    4018: (0, (4,), (1000,), None),
    4051: (0, (0,), (4055,), 4),
    4055: (15, (0,), (1033,), None),
    4057: (15, (3, 4), (1000,), None),
    4058: (0, (0,), (4057,), 4),
    4063: (0, (0,), (61453,), 8),
    4081: (1, (0,), (4116,), 28),
    4082: (15, (0,), (61453,), None),
    4083: (0, (0,), (4082,), 16),
    4116: (15, (0,), (61457,), 36),
    11019: (0, (0,), (1016,), None),
    11021: (0, (0,), (1016,), 4),
    61722: (0, (2,), (61440,), 8),
    61730: (3, (1, 2, 3), (61444,), None),
}

# PPT10 timing/build/font records: (flags, owners, exact length or variable).
_TAG10 = {
    1037: ((0,), (None,), 8),
    12011: ((0,), (None,), 8),
    2006: ((15,), (None,), None),
    4018: ((64,), (None,), 42),
    4020: ((0,), (None,), 8),
    4023: ((0,), (2006,), 68),
    4125: ((0,), (None,), 4),
    11008: ((0,), (None,), 4),
    11009: ((0,), (61756,), 4),
    11003: ((0,), (61756,), 20),
    11010: ((15,), (None,), 0),
    61733: ((31, 63, 79), (61764,), None),
    61735: ((0,), (61764,), 32),
    61736: ((0,), (61733,), 16),
    61738: ((15,), (61739, 61741, 61745), None),
    61739: ((15,), (61764,), None),
    61741: ((15,), (61764,), None),
    61745: ((15,), (61764,), None),
    61747: ((0,), (61738,), 16),
    61748: ((0,), (61739,), 12),
    61750: ((0,), (61741,), 8),
    61754: ((0,), (61745,), 8),
    61756: ((15,), (61733, 61738), None),
    61757: ((15,), (61764,), None),
    61758: ((31,), (61738,), None),
    61759: ((15,), (61739,), None),
    61761: ((0,), (61764,), 20),
    61762: ((0, 16, 144, 160, 176, 320), (61757, 61741, 61745, 61758, 61759), None),
    61763: ((0,), (61759,), 4),
    61764: ((31,), (None, 61764), None),
}


def _shape_text_props(data: bytes, budget: Budget) -> None:
    """MS-PPT 2.9.26/67/68: bounded runs with no picture-bullet target.

    PF9 masks admit only the observed null BlipRef and numbering forms; CF9/SI
    masks remain zero. Numbering and text bytes are immutable, never rewritten.
    """
    pos = 0
    while pos < len(data):
        budget.consume(nodes=1)
        _require(len(data) - pos >= 12, "truncated PPT9 shape text run")
        mask = struct.unpack_from("<I", data, pos)[0]
        _require(mask in (0, 0x02800000, 0x03800000), "unqualified PPT9 shape PF9 mask")
        pos += 4
        if mask:
            # Picture bullet reference MUST be null; number fields have no
            # Pictures offset or other external reference (MS-PPT 2.2.1).
            expected = (struct.pack("<HHHH", 0xFFFF, 1, 3, 1)
                        if mask == 0x03800000 else struct.pack("<HH", 0xFFFF, 0))
            _require(data[pos:pos + len(expected)] == expected,
                     "unqualified PPT9 shape bullet reference/numbering")
            pos += len(expected)
        _require(data[pos:pos + 8] == b"\0" * 8, "unqualified PPT9 shape CF9/SI mask")
        pos += 8
    _require(pos > 0 and pos == len(data), "invalid PPT9 shape text run boundary")


def _blob(
    data: bytes, name: str, owner: int, budget: Budget,
    shape_ids: Optional[Set[int]] = None,
) -> None:
    records = read_records(data)
    budget.consume(nodes=len(records))
    _require(bool(records), "empty programmable tag")
    if owner == 61457:
        # MS-PPT 2.7.18/2.9.67-68: exactly one atom containing bounded text
        # runs; no run can introduce a picture-bullet reference.
        _require(
            name == "___PPT9"
            and len(records) == 1
            and (records[0].kind, records[0].flags) == (4012, 0),
            "unqualified PPT9 shape extension",
        )
        _shape_text_props(data[8:], budget)
        return
    font_zero_count = sum(r.kind == 4023 and r.flags == 0 for r in records.values())
    for pos, record in records.items():
        parent = records[record.parent].kind if record.parent is not None else None
        if name == "___PPT10":
            rule = _TAG10.get(record.kind)
            _require(rule is not None, "unqualified PPT10 extension record")
            assert rule is not None
            flags, owners, size = rule
            _require(
                record.flags in flags
                and parent in owners
                and (size is None or record.size == size),
                "PPT10 extension header/owner",
            )
            if record.parent is None:
                roots = {
                    2000: (1037, 2006, 4018, 4020),
                    1008: (12011,),
                    1006: (12011, 4125, 11008, 11010, 61764),
                    1016: (12011, 4125, 11008, 11010, 61764),
                }
                _require(record.kind in roots[owner], "PPT10 extension outside admitted owner")
            if record.kind in (4018, 4020):
                # MS-PPT 2.9.18/39/40/75: font-only defaults/levels with
                # newEAFontRef=0 and csFontRef=null; neither addresses Pictures.
                level = struct.pack("<IHH", 0x03000000, 0, 0xFFFF)
                expected = struct.pack("<H", 5) + level * 5 if record.kind == 4018 else level
                _require(data[pos + 8:pos + 8 + record.size] == expected,
                         "unqualified PPT10 text master/default font fields")
                _require(font_zero_count == 1,
                         "missing/ambiguous PPT10 text font reference")
        elif name == "___PPT9":
            _require(
                owner == 2000
                and (
                    (record.kind, record.flags, parent, record.size) == (4040, 47, None, 12)
                    or (record.kind, record.flags, parent, record.size) == (4050, 48, 4040, 4)
                ),
                "unqualified PPT9 document extension",
            )
        else:
            _require(
                name == "___PPT12"
                and record.parent is None
                and record.flags == 0
                and record.size == 1
                and record.kind == {2000: 1061, 1016: 1060}.get(owner),
                "unqualified PPT12 extension",
            )
    if name == "___PPT10":
        from .ole_ppt_timing import check_timing

        check_timing(data, records, shape_ids or set())


def _tags(
    data: bytes,
    records: Dict[int, PptRecord],
    children: Dict[Optional[int], List[int]],
    budget: Budget,
) -> None:
    for pos, record in records.items():
        if record.kind != 5000:
            continue
        owner = record.parent
        _require(
            record.flags == 15
            and owner is not None
            and records[owner].kind in (2000, 1006, 1016, 1008, 61457)
            and bool(children[pos])
            and all(records[p].kind == 5002 for p in children[pos]),
            "unqualified programmable tag list/owner",
        )
        assert owner is not None
        if records[owner].kind == 61457:
            shape = records[owner].parent
            _require(
                records[owner].flags == 15
                and shape is not None
                and records[shape].kind == 61444
                and records[shape].flags == 15,
                "programmable shape tag outside client data/shape",
            )
        names = set()
        for tag in children[pos]:
            positions = children[tag]
            _require(records[tag].flags == 15 and len(positions) == 2, "binary tag structure")
            name_pos, blob_pos = positions
            name_atom, blob = records[name_pos], records[blob_pos]
            _require(
                name_atom.kind == 4026
                and name_atom.flags == 0
                and name_atom.size in (14, 16)
                and blob.kind == 5003
                and blob.flags == 0,
                "binary tag header/name",
            )
            name = data[name_pos + 8 : name_pos + 8 + name_atom.size].decode("utf-16le")
            _require(
                name in ("___PPT9", "___PPT10", "___PPT12") and name not in names,
                "unknown/duplicate programmable extension",
            )
            names.add(name)
            shape_ids = set()
            if name == "___PPT10":
                identities: Dict[int, int] = {}
                for shape_pos, shape_record in records.items():
                    if shape_record.kind != 61450:
                        continue
                    ancestor = shape_record.parent
                    while ancestor is not None and ancestor != owner:
                        ancestor = records[ancestor].parent
                    if ancestor == owner and shape_record.size == 8:
                        parent = shape_record.parent
                        identifier = struct.unpack_from("<I", data, shape_pos + 8)[0]
                        valid = (
                            parent is not None and records[parent].kind == 61444
                            and records[parent].flags == 15
                        )
                        identities[identifier] = identities.get(identifier, 0) + (1 if valid else 2)
                # Only referenced visual IDs need the new uniqueness check;
                # older timing forms retain their existing admission rules.
                shape_ids = {i for i, count in identities.items() if i > 0 and count == 1}
            _blob(
                data[blob_pos + 8 : blob_pos + 8 + blob.size], name,
                records[owner].kind, budget, shape_ids,
            )
    for record in records.values():
        if record.kind in (5002, 5003):
            _require(
                record.parent is not None
                and records[record.parent].kind == {5002: 5000, 5003: 5002}[record.kind],
                "programmable extension outside recognized tag",
            )


def check_picture_records(
    data: bytes,
    records: Dict[int, PptRecord],
    children: Dict[Optional[int], List[int]],
    budget: Budget,
) -> None:
    for pos, record in records.items():
        rule = _EXTRA.get(record.kind)
        if rule is None:
            _require(
                _VERSIONS.get(record.kind) == record.flags & 15,
                "unqualified record type/version: " + str(record.kind),
            )
            continue
        version, instances, owners, size = rule
        parent = records[record.parent].kind if record.parent is not None else None
        _require(
            record.flags & 15 == version
            and record.flags >> 4 in instances
            and parent in owners
            and (size is None or record.size == size),
            "unqualified extension header/owner: " + str(record.kind),
        )
        if record.kind in (1038, 1054, 1059, 1063, 1064, 11019):
            _require(data[pos + 8 : pos + 12] == b"PK\x03\x04", "round-trip package signature")
        if record.kind == 1039:
            _require(data[pos + 8 : pos + 13] == b"<?xml", "round-trip XML signature")
    _animations(data, records, children)
    _tags(data, records, children, budget)


def _animations(
    data: bytes,
    records: Dict[int, PptRecord],
    children: Dict[Optional[int], List[int]],
) -> None:
    """MS-PPT 2.8.1/2: immutable, sound-free checker and fly-bottom entrances.

    Every two-bit flag must be a Boolean. Sound IDs would require a separately
    qualified sound collection. Unused bytes remain exact in the host identity.
    """
    owners = set()
    for pos, record in records.items():
        if record.kind != 4116:
            continue
        owner = record.parent
        assert owner is not None  # Checked by the extension header table.
        shape = records[owner].parent
        page = owner
        while records[page].parent is not None:
            parent = records[page].parent
            assert parent is not None
            page = parent
        _require(
            owner not in owners
            and records[page].kind in (1006, 1016, 1008)
            and records[owner].flags == 15
            and shape is not None
            and records[shape].kind == 61444
            and records[shape].flags == 15
            and len(children[pos]) == 1
            and records[children[pos][0]].kind == 4081,
            "animation container children/shape/duplicate",
        )
        owners.add(owner)
        atom = children[pos][0] + 8
        flags, sound, delay, order = struct.unpack_from("<IIih", data, atom + 4)
        _require(
            flags >> 16 == 0
            and all((flags >> bit) & 3 in (0, 1) for bit in range(0, 16, 2))
            and flags & 0x30 == 0
            and sound == 0
            and (flags & 0xC == 0 or delay >= 0)
            and order >= -2,
            "unqualified animation flags/sound/order",
        )
        effect = tuple(data[atom + 20 : atom + 26])
        _require(
            effect in ((1, 3, 0, 0, 0, 0), (1, 12, 3, 0, 0, 0)),
            "unqualified animation build/effect/direction/after-effect: " + str(effect),
        )


def _roundtrip_masters(
    data: bytes, records: Dict[int, PptRecord], children: Dict[Optional[int], List[int]],
    masters: Dict[int, int],
) -> Tuple[Dict[int, int], Dict[int, Set[int]], Dict[int, int]]:
    originals: Dict[int, int] = {}
    layouts: Dict[int, Set[int]] = {}
    composites: Dict[int, int] = {}
    for master in masters.values():
        atoms = [p for p in children[master] if records[p].kind in (1052, 1053)]
        _require(len(atoms) == 1, "missing/duplicate round-trip master identity")
        identifier = struct.unpack_from("<I", data, atoms[0] + 8)[0]
        _require(identifier > 0, "invalid round-trip master identity")
        if records[atoms[0]].kind == 1052:
            _require(identifier not in originals, "ambiguous round-trip master identity")
            originals[identifier] = master
        else:
            composites[master] = identifier
        instances = [records[p].flags >> 4 for p in children[master] if records[p].kind == 1054]
        _require(len(instances) == len(set(instances)), "duplicate round-trip layout instance")
        layouts[master] = set(instances)
    used = {identifier: set(layouts[master]) for identifier, master in originals.items()}
    for master, identifier in composites.items():
        _require(identifier in originals and len(layouts[master]) == 1,
                 "missing/ambiguous composite round-trip master/layout")
        _require(not used[identifier] & layouts[master], "duplicate composite round-trip layout")
        used[identifier].update(layouts[master])
    return originals, layouts, composites


def _check_composite_refs(
    data: bytes, records: Dict[int, PptRecord], children: Dict[Optional[int], List[int]],
    slides: Dict[int, int], masters: Dict[int, int], composites: Dict[int, int],
) -> None:
    """MS-PPT 2.11.10: immutable merged layout/main-master identities."""
    seen: Set[int] = set()
    pages = set(slides.values()) | set(masters.values())
    for pos, record in records.items():
        if record.kind != 1053:
            continue
        page = record.parent
        _require(page in pages and page not in seen, "duplicate/non-live composite master identity")
        assert page is not None
        seen.add(page)
        if records[page].kind == 1016:
            continue  # Already resolved in the complete master inventory.
        _require(not any(records[p].kind == 1058 for p in children[page]),
                 "conflicting composite/layout slide references")
        atom = next(p for p in children[page] if records[p].kind == 1007)
        legacy = struct.unpack_from("<I", data, atom + 20)[0]
        identifier = struct.unpack_from("<I", data, pos + 8)[0]
        _require(composites.get(masters.get(legacy, -1)) == identifier,
                 "missing/inconsistent composite master reference")


def check_picture_layout_refs(
    data: bytes,
    records: Dict[int, PptRecord],
    children: Dict[Optional[int], List[int]],
    slides: Dict[int, int],
    masters: Dict[int, int],
) -> None:
    """Bind immutable round-trip master/layout IDs to the live legacy graph.

    MS-PPT 2.11.11/12/20. These logical IDs never address Pictures bytes;
    matching them must not authorize changes outside the existing FBSE mask.
    """
    refs = [p for p, r in records.items() if r.kind == 1058]
    if not refs and not any(r.kind == 1053 for r in records.values()):
        return
    original_ids, layouts, composites = _roundtrip_masters(data, records, children, masters)
    _check_composite_refs(data, records, children, slides, masters, composites)
    live_slides, seen = set(slides.values()), set()
    for pos in refs:
        slide = records[pos].parent
        _require(
            slide in live_slides and slide not in seen,
            "round-trip layout outside live slide or duplicate reference",
        )
        seen.add(slide)
        atom = next(p for p in children[slide] if records[p].kind == 1007)
        legacy_id = struct.unpack_from("<I", data, atom + 20)[0]
        master_id, instance = struct.unpack_from("<IH", data, pos + 8)
        resolved_master = original_ids.get(master_id)
        _require(
            resolved_master is not None
            and resolved_master == masters.get(legacy_id)
            and instance in layouts[resolved_master],
            "missing/inconsistent round-trip master/layout reference",
        )
