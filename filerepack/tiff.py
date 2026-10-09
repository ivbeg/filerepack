"""TIFF compression with unchanged IFD/metadata positions and native sample checks.

Metadata stays at its original addresses. Only a fully described image-data suffix
is compacted; earlier pages remain byte-identical. Private offset-bearing tags and
COG block-leader/trailer layouts are refused rather than copied speculatively.
"""

import hashlib
import mmap
import os
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set

from .format_support import Budget, UnsupportedFormat, inflate

WIDTHS = {
    1: 1,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    6: 1,
    7: 1,
    8: 2,
    9: 4,
    10: 8,
    11: 4,
    12: 8,
    13: 4,
    16: 8,
    17: 8,
    18: 8,
}
KNOWN = (
    set(range(254, 267))
    | set(range(269, 298))
    | set(range(301, 322))
    | {
        322,
        323,
        324,
        325,
        326,
        327,
        328,
        330,
        332,
        333,
        334,
        336,
        337,
        338,
        339,
        340,
        341,
        342,
        343,
        344,
        346,
        347,
        529,
        530,
        531,
        532,
        700,
        33723,
        34377,
        33550,
        33922,
        34264,
        34665,
        34675,
        34735,
        34736,
        34737,
        34853,
        42112,
        42113,
        33432,
        33434,
        33437,
        34850,
        34855,
        36864,
        36867,
        36868,
        37121,
        37122,
        37377,
        37378,
        37379,
        37380,
        37381,
        37382,
        37383,
        37384,
        37385,
        37386,
        37500,
        37510,
        40960,
        40961,
        40962,
        40963,
        40965,
        41483,
        41484,
        41486,
        41487,
        41488,
        41492,
        41493,
        41495,
        41728,
        41729,
        41730,
        41985,
        41986,
        41987,
        41988,
        41989,
        41990,
        41991,
        41992,
        41993,
        41994,
        41995,
        41996,
    }
)
# MakerNote can contain private offsets even though its outer tag is standardized.
KNOWN.discard(37500)
KNOWN.difference_update({288, 289})  # FreeOffsets/FreeByteCounts refer to unowned data.
POINTERS = {330, 34665, 34853, 40965}
DERIVED = {259, 273, 279, 324, 325}


@dataclass
class Tag:
    code: int
    dtype: int
    count: int
    position: int
    size: int
    raw: bytes

    def numbers(self, endian: str) -> List[int]:
        formats = {3: "H", 4: "I", 13: "I", 16: "Q", 18: "Q"}
        if self.dtype not in formats:
            raise UnsupportedFormat("unsupported TIFF offset/count datatype")
        return [value[0] for value in struct.iter_unpack(endian + formats[self.dtype], self.raw)]


class Graph:
    def __init__(self, data: Any, budget: Budget):
        self.data, self.budget = data, budget
        if data[:2] not in (b"II", b"MM"):
            raise ValueError("invalid TIFF byte order")
        self.endian = "<" if data[:2] == b"II" else ">"
        version = self.number(2, 2)
        if version == 42:
            self.offset_size, self.count_size, self.entry_size = 4, 2, 12
            root = self.number(4, 4)
            self.metadata_end = 8
        elif version == 43 and self.number(4, 2) == 8 and self.number(6, 2) == 0:
            self.offset_size, self.count_size, self.entry_size = 8, 8, 20
            root = self.number(8, 8)
            self.metadata_end = 16
        else:
            raise UnsupportedFormat("unsupported TIFF header")
        self.version = version
        self.nodes: List[Tuple[int, Dict[int, Tag], int]] = []
        self.ranges: List[Tuple[int, int]] = [(0, self.metadata_end)]
        self.visited: Set[int] = set()
        self.active: Set[int] = set()
        self.visit(root)
        if not self.nodes:
            raise ValueError("TIFF has no IFD")
        if b"GDAL_STRUCTURAL_METADATA_SIZE" in data[: min(self.metadata_end, 4096)]:
            raise UnsupportedFormat("COG structural/block layout requires a dedicated validator")

    def number(self, offset: int, size: int) -> int:
        if offset < 0 or offset + size > len(self.data):
            raise ValueError("TIFF offset exceeds file bounds")
        return int.from_bytes(
            self.data[offset : offset + size], "little" if self.endian == "<" else "big"
        )

    def visit(self, offset: int) -> None:
        if not offset:
            return
        if offset in self.active:
            raise ValueError("cyclic TIFF IFD graph")
        if offset in self.visited:
            return
        self.budget.consume(nodes=1)
        self.active.add(offset)
        self.visited.add(offset)
        count = self.number(offset, self.count_size)
        self.budget.consume(nodes=count)
        end = offset + self.count_size + count * self.entry_size + self.offset_size
        if end > len(self.data):
            raise ValueError("truncated TIFF directory")
        self.ranges.append((offset, end))
        self.metadata_end = max(self.metadata_end, end)
        tags = {}
        for index in range(count):
            entry = offset + self.count_size + index * self.entry_size
            code, dtype = self.number(entry, 2), self.number(entry + 2, 2)
            if code not in KNOWN or code in tags or dtype not in WIDTHS:
                raise UnsupportedFormat("unknown/ambiguous TIFF tag: " + str(code))
            number = self.number(entry + 4, self.offset_size)
            size = number * WIDTHS[dtype]
            self.budget.memory(size)
            field = entry + 4 + self.offset_size
            position = field if size <= self.offset_size else self.number(field, self.offset_size)
            if position + size > len(self.data):
                raise ValueError("TIFF tag payload exceeds file bounds")
            self.ranges.append((position, position + size))
            self.metadata_end = max(self.metadata_end, position + size)
            tags[code] = Tag(
                code, dtype, number, position, size, self.data[position : position + size]
            )
        next_ifd = self.number(end - self.offset_size, self.offset_size)
        self.nodes.append((offset, tags, next_ifd))
        for code in POINTERS & tags.keys():
            for child in tags[code].numbers(self.endian):
                self.visit(child)
        self.visit(next_ifd)
        self.active.remove(offset)

    def fingerprint(self) -> Any:
        return (
            self.version,
            self.endian,
            [
                (
                    offset,
                    next_ifd,
                    [
                        (code, tag.dtype, tag.count, hashlib.sha256(tag.raw).hexdigest())
                        for code, tag in sorted(tags.items())
                        if code not in DERIVED
                    ],
                )
                for offset, tags, next_ifd in self.nodes
            ],
        )

    def chunks(self) -> List[Any]:
        result = []
        for node, tags, _ in self.nodes:
            offset_code = 324 if 324 in tags else 273
            count_code = 325 if offset_code == 324 else 279
            if offset_code not in tags and count_code not in tags:
                continue  # EXIF/GPS metadata directories have no image chunks.
            if count_code not in tags or offset_code not in tags:
                raise ValueError("incomplete TIFF strip/tile framing")
            offsets = tags[offset_code].numbers(self.endian)
            counts = tags[count_code].numbers(self.endian)
            if not offsets or len(offsets) != len(counts):
                raise ValueError("inconsistent TIFF chunk counts")
            compression = tags[259].numbers(self.endian)[0] if 259 in tags else 1
            if 259 not in tags or compression not in (1, 5, 8, 32946):
                raise UnsupportedFormat("TIFF compression is outside the native lossless profile")
            if 266 in tags and tags[266].numbers(self.endian) != [1]:
                raise UnsupportedFormat("non-default TIFF bit fill order")
            if 258 not in tags or any(
                bit not in (8, 16, 32, 64) for bit in tags[258].numbers(self.endian)
            ):
                raise UnsupportedFormat("unsupported TIFF sample depth")
            for index, (offset, size) in enumerate(zip(offsets, counts)):
                if not size or offset + size > len(self.data):
                    raise ValueError("invalid TIFF image-data range")
                if any(offset < end and offset + size > start for start, end in self.ranges):
                    raise ValueError("TIFF image data overlaps metadata")
                result.append(
                    (
                        offset,
                        size,
                        node,
                        index,
                        compression,
                        tags[offset_code],
                        tags[count_code],
                        tags[259],
                    )
                )
        ordered = sorted(result)
        if any(a[0] + a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError("TIFF image-data ranges overlap")
        return ordered


def sample_manifest(path: str, budget: Budget) -> Any:
    import tifffile

    result = []
    with tifffile.TiffFile(path) as file:

        def visit(pages: Any) -> None:
            for page in pages:
                budget.consume(nodes=1)
                # No complete image allocation: compare native decoded segments.
                if page.is_subsampled:
                    raise UnsupportedFormat("subsampled TIFF images are outside the profile")
                expected = page.tilelength if page.is_tiled else page.rowsperstrip
                width = page.tilewidth if page.is_tiled else page.imagewidth
                budget.memory(expected * width * page.samplesperpixel * page.dtype.itemsize)
                tokens = []
                for array, index, shape in page.segments(maxworkers=1):
                    if array is None:
                        raise UnsupportedFormat("sparse TIFF segments are outside the profile")
                    budget.consume(decoded=array.nbytes)
                    tokens.append(
                        (index, shape, array.dtype.str, hashlib.sha256(array.tobytes()).hexdigest())
                    )
                result.append((page.shape, page.dtype.str, tokens))
                if page.subifds:
                    visit(page.pages)

        visit(file.pages)
    return result


def _patch(stream: Any, tag: Tag, index: int, value: int, endian: str) -> None:
    width = WIDTHS[tag.dtype]
    if value < 0 or value >= 1 << (8 * width):
        raise UnsupportedFormat("TIFF derived offset/count exceeds its retained datatype")
    stream.seek(tag.position + index * width)
    stream.write(value.to_bytes(width, "little" if endian == "<" else "big"))


def rewrite(graph: Graph, source: str, candidate: str, budget: Budget) -> bool:
    chunks = graph.chunks()
    suffix = [chunk for chunk in chunks if chunk[0] >= graph.metadata_end]
    if not suffix:
        return False
    # Only optimize a page when all its chunks are in the mutable suffix.
    retained_pages = {chunk[2] for chunk in chunks if chunk[0] < graph.metadata_end}
    position = graph.metadata_end
    for chunk in suffix:
        if any(graph.data[position : chunk[0]]):
            raise UnsupportedFormat("non-padding TIFF image suffix framing")
        position = chunk[0] + chunk[1]
    if any(graph.data[position:]):
        raise UnsupportedFormat("unknown trailing TIFF payload")
    import imagecodecs

    changed = False
    with open(source, "rb") as original, open(candidate, "w+b") as output:
        remaining = graph.metadata_end
        while remaining:
            block = original.read(min(remaining, 65536))
            budget.consume(written=len(block))
            output.write(block)
            remaining -= len(block)
        for offset, size, node, index, compression, offsets, counts, method in suffix:
            budget.memory(size * 4)
            data = graph.data[offset : offset + size]
            encoded, target_method = data, compression
            if node not in retained_pages:
                if compression in (8, 32946):
                    raw = inflate(data, budget)
                elif compression == 5:
                    raw = imagecodecs.lzw_decode(data)
                    budget.memory(len(raw) * 4)
                    budget.consume(decoded=len(raw))
                else:
                    raw = data
                    budget.consume(decoded=len(raw))
                proposed = zlib.compress(raw, 9)
                if compression not in (8, 32946) or len(proposed) < len(data):
                    encoded = proposed
                    target_method = compression if compression in (8, 32946) else 8
                    changed = True
            location = output.tell()
            budget.consume(written=len(encoded))
            output.write(encoded)
            end = output.tell()
            _patch(output, offsets, index, location, graph.endian)
            _patch(output, counts, index, len(encoded), graph.endian)
            _patch(output, method, 0, target_method, graph.endian)
            output.seek(end)
    return changed or os.path.getsize(candidate) < os.path.getsize(source)


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    if os.path.getsize(source) < 8:
        raise ValueError("truncated TIFF header")
    with (
        open(source, "rb") as stream,
        mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data,
    ):
        graph = Graph(data, budget)
        graph.chunks()
        fingerprint = graph.fingerprint()
        samples = sample_manifest(source, budget)
        details = {
            "profile": "TIFF-native-data-suffix",
            "ifds": len(graph.nodes),
            "metadata_policy": "retained positions and exact non-storage tag payloads",
            "reader_lineage": "tifffile/imagecodecs",
        }
        if action == "inspect":
            return {"details": details}
        if action == "rewrite":
            assert candidate is not None
            if not rewrite(graph, source, candidate, budget):
                return {
                    "changed": False,
                    "reason": "no eligible TIFF suffix compression",
                    "details": details,
                }
    assert candidate is not None
    with (
        open(candidate, "rb") as stream,
        mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data,
    ):
        other = Graph(data, budget)
        other.chunks()
        if fingerprint != other.fingerprint():
            raise ValueError("TIFF IFD graph or semantic metadata changed")
    if samples != sample_manifest(candidate, budget):
        raise ValueError("TIFF native samples changed")
    return {"equal": True, "changed": action == "rewrite", "details": details}
