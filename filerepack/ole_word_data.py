"""Bounded, fully covered Word Data references, including chained PrcData.

MS-DOC 2.6.2 and 2.9.210: HugePapx/TableProps contain Data offsets, unlike
ordinary table operands. Unknown/nested formatting families remain rejected.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple

from .format_support import Budget
from .ole_officeart import require


@dataclass
class DataReferences:
    data: bytes
    budget: Budget
    refs: Dict[int, int] = field(default_factory=dict)
    internal: Dict[int, int] = field(default_factory=dict)
    regions: Dict[int, Tuple[int, str]] = field(default_factory=dict)

    def region(self, target: int, size: int, kind: str) -> None:
        require(0 <= target and 0 < size <= len(self.data) - target, "Data region bounds")
        old = self.regions.get(target)
        require(old is None or old == (size, kind), "conflicting Data region interpretations")
        self.regions[target] = size, kind

    def paragraph(self, grp: bytes, base: int, *, internal: bool = False, depth: int = 0) -> None:
        from .ole_word_art import PARA, PARA_REFS, TABLE, properties, u32

        self.budget.depth(depth)
        parsed = properties(grp, base, PARA | TABLE | PARA_REFS)
        for code, (offset, operand) in parsed.items():
            if code not in PARA_REFS:
                continue
            require(code != 0x6646 or offset == base + 2,
                    "nonleading HugePapx is not qualified")
            target = u32(operand, 0)
            refs = self.internal if internal else self.refs
            require(offset not in refs or refs[offset] == target, "ambiguous PrcData reference")
            refs[offset] = target
            self._prc(target, depth + 1)

    def _prc(self, target: int, depth: int) -> None:
        from .ole_word_art import u16

        self.budget.depth(depth)
        self.budget.consume(nodes=1)
        # A visiting region is not installed until its children have terminated.
        require(target not in self._visiting, "cyclic PrcData references")
        if target in self.regions:
            require(self.regions[target][1] == "prc", "PrcData aliases a different Data region")
            return
        size = u16(self.data, target)
        require(10 <= size <= 0x3FA2 and target + 2 + size <= len(self.data), "PrcData bounds")
        self._visiting.add(target)
        try:
            self.paragraph(self.data[target + 2 : target + 2 + size], target + 2,
                           internal=True, depth=depth)
        finally:
            self._visiting.remove(target)
        self.region(target, size + 2, "prc")

    _visiting: Set[int] = field(default_factory=set)

    def binary(self, target: int) -> None:
        from .ole_word_art import u16, u32

        size = u32(self.data, target)
        require(
            68 <= size <= 0x7FFFFFFF and target + size <= len(self.data)
            and u16(self.data, target + 4) == 68
            and self.data[target + 6 : target + 68] == b"\0" * 62,
            "NilPICFAndBinData bounds/header",
        )
        self.region(target, size, "binary")
