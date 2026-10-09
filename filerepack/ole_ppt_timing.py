"""Immutable PPT10 checker/fly-bottom/visibility forms (MS-PPT 2.8.29-82).

These references name live shape IDs, never Pictures offsets. Admission does
not permit changing timing bytes or expanding the trailing-storage contract.
"""

import struct
from collections import defaultdict
from typing import Dict, List, Optional, Set

from .ole_ppt import PptRecord
from .ole_ppt_records import _require


def _fly_bottom(
    data: bytes, records: Dict[int, PptRecord], children: Dict[Optional[int], List[int]], pos: int,
) -> None:
    """MS-PPT 2.8.29-33, 3.7.2: two exact linear coordinate keyframes.

    A horizontal track retains #ppt_x. A vertical track starts below the slide
    at 1+#ppt_h/2 and ends at #ppt_y. No general formula evaluator is admitted.
    """
    def body(p: int) -> bytes:
        return data[p + 8:p + 8 + records[p].size]

    def kinds(p: int) -> List[int]:
        return [records[q].kind for q in children[p]]

    _require(kinds(pos) == [61748, 61759, 61738], "PPT10 fly behavior children")
    atom, values, behavior = children[pos]
    _require(body(atom) == struct.pack("<III", 1, 0x38, 1),
             "unqualified PPT10 fly calculation/flags/type")
    _require(kinds(behavior) == [61747, 61758, 61756], "PPT10 fly common behavior children")
    common, names, _ = children[behavior]
    _require(body(common) == struct.pack("<IIII", 5, 0, 0, 0),
             "unqualified PPT10 fly common behavior flags")
    _require(kinds(names) == [61762], "PPT10 fly coordinate count")
    name = body(children[names][0])
    axes = {b"\3" + (axis + "\0").encode("utf-16le"): axis for axis in ("ppt_x", "ppt_y")}
    _require(name in axes, "unqualified PPT10 fly coordinate")
    axis = axes[name]
    _require(kinds(values) == [61763, 61762, 61762] * 2, "PPT10 fly keyframe children")
    for index, time in enumerate((0, 1000)):
        timestamp, value, formula = children[values][index * 3:index * 3 + 3]
        expected = "1+#ppt_h/2" if axis == "ppt_y" and index == 0 else "#" + axis
        _require(
            body(timestamp) == struct.pack("<I", time)
            and records[value].flags == 0
            and body(value) == b"\3" + (expected + "\0").encode("utf-16le")
            and records[formula].flags == 16
            and body(formula) == b"\3\0\0",
            "unqualified PPT10 fly keyframe time/value/formula",
        )


def _timing_string(
    body: bytes, record: PptRecord, records: Dict[int, PptRecord],
) -> None:
    assert record.parent is not None
    parent = records[record.parent].kind
    if parent == 61759:
        # The owning fly container checks both entries together.
        return
    if parent == 61757:
        _require(record.size == 5 and body[0] == 1, "PPT10 integer variant")
        return
    if parent == 61758:
        behavior = records[record.parent].parent
        assert behavior is not None
        owner = records[behavior].parent
        if owner is not None and records[owner].kind == 61739:
            _require(record.flags == 0, "PPT10 fly coordinate instance")
            return
    expected = {
        61741: (16, "checkerboard(across)"),
        61745: (16, "visible"),
        61758: (0, "style.visibility"),
    }[parent]
    _require(
        record.flags == expected[0]
        and body == b"\3" + (expected[1] + "\0").encode("utf-16le"),
        "unqualified PPT10 effect/visibility string",
    )


def check_timing(data: bytes, records: Dict[int, PptRecord], shape_ids: Set[int]) -> None:
    children = defaultdict(list)
    for pos in sorted(records):
        children[records[pos].parent].append(pos)
    for pos, record in records.items():
        body = data[pos + 8 : pos + 8 + record.size]
        kinds = [records[p].kind for p in children[pos]]
        if record.kind == 61739:
            _fly_bottom(data, records, children, pos)
        elif record.kind in (61741, 61745):
            _require(
                kinds == [61750 if record.kind == 61741 else 61754, 61762, 61738],
                "PPT10 effect/set children",
            )
        elif record.kind == 61738:
            _require(kinds in ([61747, 61756], [61747, 61758, 61756]),
                     "PPT10 behavior children")
        elif record.kind == 61747:
            assert record.parent is not None
            behavior = records[record.parent]
            fly = behavior.parent is not None and records[behavior.parent].kind == 61739
            _require(body == struct.pack("<IIII", 5, 0, 0, 0) if fly
                     else body in (b"\0" * 16, b"\4" + b"\0" * 15),
                     "unqualified PPT10 behavior flags")
        elif record.kind in (61750, 61754):
            _require(body == struct.pack("<II", 3, 0) if record.kind == 61750
                     else body == struct.pack("<II", 1, 1), "PPT10 effect/set fields")
        elif record.kind == 61758:
            _require(kinds == [61762], "PPT10 visibility string list")
        elif record.kind == 61756 and record.parent is not None:
            if records[record.parent].kind == 61738:
                _require(kinds == [11003], "PPT10 behavior visual target")
        elif record.kind == 11003:
            kind, reference, shape, first, last = struct.unpack("<5I", body)
            _require(
                (kind, reference, first, last) == (0, 1, 0xFFFFFFFF, 0xFFFFFFFF)
                and shape > 0 and shape in shape_ids,
                "PPT10 missing/unknown visual shape target",
            )
        elif record.kind == 61733 and record.flags == 31:
            _require(kinds == [61736], "PPT10 begin condition children")
        elif record.kind == 61762:
            _timing_string(body, record, records)
