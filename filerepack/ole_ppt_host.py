"""Single-edit PPT host graph shared by independent payload operations.

Notes and unselected embedded storages remain exact immutable record spans.
MS-PPT 2.4.2/14, 2.5.6/12 and 2.10.12/27/28/34; MS-ODRAW 2.2.7/11.
"""

import io
import struct
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .format_support import Budget
from .ole_ppt import PptRecord, read_records
from .ole_ppt_records import CURRENT, DOCUMENT, _extensions, _persist, _require
from .ole_verify import CompoundFile, independent_manifest


@dataclass
class PptHost:
    data: bytes
    current: bytes
    records: Dict[int, PptRecord]
    children: Dict[Optional[int], List[int]]
    persist: Dict[int, int]
    fields: Dict[int, int]
    directory: int
    edit: int
    live: Set[int]
    storages: List[int]


def _lists(host: PptHost) -> Dict[int, Dict[int, int]]:
    result: Dict[int, Dict[int, int]] = {0: {}, 1: {}, 2: {}}
    targets: Set[int] = set()
    owners: Set[int] = set()
    for pos, record in host.records.items():
        if record.kind != 4080:
            continue
        instance = record.flags >> 4
        _require(
            record.parent == 0 and record.flags & 15 == 15 and instance in result,
            "unqualified slide/master/notes list",
        )
        _require(instance not in owners, "duplicate slide/master/notes list")
        owners.add(instance)
        for child in host.children[pos]:
            atom = host.records[child]
            if atom.kind != 1011:
                _require(instance == 0, "non-persist record in master/notes list")
                continue
            _require(atom.flags == 0 and atom.size == 20, "slide/master/notes persist header")
            identifier, _, _, logical_id, _ = struct.unpack_from("<5I", host.data, child + 8)
            target = host.persist.get(identifier)
            _require(
                target is not None
                and logical_id > 0
                and logical_id not in result[instance]
                and target not in targets,
                "missing/duplicate slide/master/notes target",
            )
            assert target is not None
            _require(
                host.records[target].kind == {0: 1006, 1: 1016, 2: 1008}[instance],
                "wrong slide/master/notes persist target kind",
            )
            result[instance][logical_id] = target
            targets.add(target)
    for pos, record in host.records.items():
        if record.kind == 1011:
            _require(
                record.parent is not None and host.records[record.parent].kind == 4080,
                "persist atom outside a live list",
            )
    host.live.update(targets)
    return result


def _notes(host: PptHost, lists: Dict[int, Dict[int, int]]) -> None:
    data, records = host.data, host.records
    atoms = [p for p in host.children[0] if records[p].kind == 1001]
    _require(
        len(atoms) == 1 and records[atoms[0]].flags == 1 and records[atoms[0]].size == 40,
        "unknown DocumentAtom",
    )
    master_id, handout = struct.unpack_from("<II", data, atoms[0] + 32)
    _require(handout == 0, "handout master is not qualified")
    master = host.persist.get(master_id) if master_id else None
    _require(
        not master_id
        or (master is not None and records[master].kind == 1008 and master not in host.live),
        "missing/ambiguous notes master",
    )
    if master is not None:
        host.live.add(master)
    slides, notes = lists[0], lists[2]
    reverse: Dict[int, int] = {}
    for target in set(notes.values()) | ({master} if master is not None else set()):
        _require(records[target].flags == 15, "NotesContainer version/instance")
        direct = host.children[target]
        kinds = [records[p].kind for p in direct]
        order = {1009: 0, 1036: 1, 2032: 2, 4026: 3, 5000: 4, 1038: 5, 1039: 5, 1063: 5}
        _require(
            kinds[:3] == [1009, 1036, 2032]
            and all(k in (4026, 5000, 1038, 1039, 1063) for k in kinds[3:])
            and len(set(kinds)) == len(kinds),
            "NotesContainer children/order",
        )
        ranks = [order[k] for k in kinds]
        _require(ranks == sorted(ranks), "NotesContainer optional child order")
        drawing, colors = records[direct[1]], records[direct[2]]
        _require(
            drawing.flags == 15 and colors.flags == 16 and colors.size == 32,
            "notes drawing/color header",
        )
        for pos in direct[3:]:
            child = records[pos]
            if child.kind == 4026:
                _require(child.flags == 48 and child.size % 2 == 0, "notes slide-name header")
        atom = records[direct[0]]
        _require(atom.flags == 1 and atom.size == 8, "NotesAtom version/length")
        slide_id, flags = struct.unpack_from("<IH", data, direct[0] + 8)
        if target == master:
            _require(
                (slide_id, flags) in ((0, 0), (0x80000000, 2)), "unqualified notes-master fields"
            )
        else:
            _require(
                slide_id in slides and slide_id not in reverse and flags & ~7 == 0,
                "missing/duplicate notes-to-slide reference",
            )
            _require(master is not None or flags == 0, "notes inherit from missing master")
            reverse[slide_id] = target
    seen: Set[int] = set()
    for slide_id, target in slides.items():
        atoms = [p for p in host.children[target] if records[p].kind == 1007]
        _require(
            len(atoms) == 1 and records[atoms[0]].flags == 2 and records[atoms[0]].size == 24,
            "unknown SlideAtom",
        )
        master_ref, notes_ref = struct.unpack_from("<II", data, atoms[0] + 20)
        _require(master_ref in lists[1], "missing slide master ID")
        if notes_ref:
            note = notes.get(notes_ref)
            _require(
                note is not None and note not in seen and reverse.get(slide_id) == note,
                "inconsistent slide-to-notes reference",
            )
            assert note is not None
            seen.add(note)
        else:
            _require(slide_id not in reverse, "unlinked notes page")
    _require(seen == set(notes.values()), "unreferenced notes page")


def _objects(host: PptHost) -> None:
    data, records = host.data, host.records
    atoms = [p for p, r in records.items() if r.kind == 4035]
    refs = [p for p, r in records.items() if r.kind == 3009]
    _require(len(atoms) == len(refs) == len(host.storages) <= 64, "object/reference count")
    consumers: Dict[int, int] = {}
    for pos in refs:
        record = records[pos]
        _require(
            record.flags == 0
            and record.size == 4
            and record.parent is not None
            and records[record.parent].kind == 61457,
            "invalid object shape reference",
        )
        identity = struct.unpack_from("<I", data, pos + 8)[0]
        _require(identity > 0 and identity not in consumers, "duplicate object shape reference")
        owner = pos
        while records[owner].parent is not None:
            parent = records[owner].parent
            assert parent is not None
            owner = parent
        _require(
            owner in host.live and records[owner].kind in (1006, 1016, 1008),
            "object shape outside a live slide/master/notes page",
        )
        consumers[identity] = owner
    used: Set[int] = set()
    identities: Set[int] = set()
    for pos in atoms:
        record = records[pos]
        parent = record.parent
        _require(
            record.flags == 1
            and record.size == 24
            and parent is not None
            and records[parent].kind == 4044,
            "object outside embedded-object container",
        )
        assert parent is not None
        ancestor = records[parent].parent
        _require(
            records[parent].flags == 15
            and ancestor is not None
            and records[ancestor].kind == 1033
            and records[ancestor].flags == 15
            and records[ancestor].parent == 0,
            "object outside live document list",
        )
        children = [records[p] for p in host.children[parent]]
        embeds = [r for r in children if r.kind == 4045]
        _require(
            len(embeds) == 1
            and embeds[0].flags == 0
            and embeds[0].size == 8
            and sum(r.kind == 4035 for r in children) == 1
            and all(r.kind in (4035, 4045, 4026) for r in children),
            "unknown embedded-object children",
        )
        names = [r for r in children if r.kind == 4026]
        _require(
            all(r.flags in (16, 32, 48) and r.size % 2 == 0 for r in names)
            and len({r.flags for r in names}) == len(names),
            "unknown OLE name/class strings",
        )
        aspect, kind, identity, subtype, identifier = struct.unpack_from("<5I", data, pos + 8)
        target = host.persist.get(identifier)
        _require(
            aspect == 1
            and kind == 0
            and subtype in (0, 2, 3)
            and identity in consumers
            and identity not in identities
            and target in host.storages
            and target not in used,
            "missing/ambiguous external object identity/storage",
        )
        assert target is not None
        wrapper = records[target]
        _require(
            wrapper.flags == 16
            and 4 < wrapper.size <= 16 * 1024 * 1024
            and 512 <= struct.unpack_from("<I", data, target + 8)[0] <= 16 * 1024 * 1024,
            "unqualified immutable storage wrapper",
        )
        identities.add(identity)
        used.add(target)
    _require(
        used == set(host.storages) and identities == set(consumers),
        "unaccounted embedded storages/consumers",
    )


def inspect_host(compound: CompoundFile, budget: Budget, *, pictures: bool = False) -> PptHost:
    from .ole import _profile

    _require(_profile(compound, "ppt") == ("ppt", False), "host VBA is not qualified")
    independent_manifest(io.BytesIO(compound.data), compound)
    data, current = compound.streams[DOCUMENT], compound.streams[CURRENT]
    _require(
        len(current) <= 4096
        and struct.unpack_from("<HH", current) == (0, 4086)
        and current[22:26] == struct.pack("<HBB", 0x3F4, 3, 0),
        "unknown Current User",
    )
    records = read_records(data)
    budget.consume(nodes=len(records) + len(compound.entries))
    children: Dict[Optional[int], List[int]] = defaultdict(list)
    for pos in sorted(records):
        children[records[pos].parent].append(pos)
    if pictures:
        from .ole_ppt_extensions import check_picture_records

        check_picture_records(data, records, children, budget)
    else:
        _extensions(data, records)
    top = children[None]
    edits = [p for p, r in records.items() if r.kind == 4085]
    indexes = [p for p, r in records.items() if r.kind == 6002]
    _require(len(edits) == len(indexes) == 1, "multiple user edits/indexes are not qualified")
    edit, directory = edits[0], indexes[0]
    previous, index, doc_id, seed = struct.unpack_from("<4I", data, edit + 16)
    _require(
        previous == 0
        and index == directory
        and doc_id == 1
        and data[edit + 14 : edit + 16] == b"\0\3"
        and edit == directory + 8 + records[directory].size
        and edit + 8 + records[edit].size == len(data)
        and struct.unpack_from("<I", current, 16)[0] == edit,
        "unknown single-edit/index tail",
    )
    persist, fields = _persist(data, records, directory, seed)
    _require(persist.get(doc_id) == 0 and records[0].kind == 1000, "document must be first")
    storages = [p for p in top if records[p].kind == 4113]
    _require(
        sum(r.kind == 4113 for r in records.values()) == len(storages),
        "compressed storage outside top-level object block",
    )
    _require(
        top[-len(storages) - 2 :] == storages + [directory, edit],
        "storages must form final contiguous object block",
    )
    host = PptHost(
        data, current, records, children, persist, fields, directory, edit, {0}, storages
    )
    lists = _lists(host)
    _notes(host, lists)
    if pictures:
        from .ole_ppt_extensions import check_picture_layout_refs

        check_picture_layout_refs(data, records, children, lists[0], lists[1])
    _objects(host)
    _require(
        host.live == set(top[: -len(storages) - 2])
        and set(persist.values()) == host.live | set(storages),
        "unaccounted persist objects",
    )
    return host
