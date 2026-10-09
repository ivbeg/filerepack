"""Level-5 MAT envelope rewriting, with passive matrix framing validation.

Object/function/subsystem records are excluded. Production never loads MATLAB
objects. Native MATLAB compatibility is a distinct release gate.
"""

import hashlib
import struct
import zlib
from typing import Any, Dict, List, Optional, Tuple

from .format_support import Budget, UnsupportedFormat, inflate, pack_format, read_small, write_bytes
from .models import PackResult
from .transactions import guard_packer

WIDTHS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 4, 6: 4, 7: 4, 9: 8, 12: 8, 13: 8, 16: 1, 17: 2, 18: 4}


class Elements:
    def __init__(self, data: Any, endian: str, budget: Budget):
        self.data = memoryview(data)
        self.endian = endian
        self.budget = budget
        self.position = 0

    def tag(self) -> Tuple[int, memoryview, memoryview]:
        self.budget.consume(nodes=1)
        start = self.position
        if len(self.data) - start < 8:
            raise ValueError("truncated MAT tag")
        word = struct.unpack_from(self.endian + "I", self.data, start)[0]
        if word in (*WIDTHS, 14, 15):
            kind, size = word, struct.unpack_from(self.endian + "I", self.data, start + 4)[0]
            end = start + 8 + size
            stop = end if kind == 15 else end + (-size % 8)
            if stop > len(self.data):
                raise ValueError("MAT element extends beyond its container")
            payload = self.data[start + 8 : end]
        else:
            kind, size = struct.unpack_from(self.endian + "HH", self.data, start)
            if kind not in WIDTHS or not 1 <= size <= 4:
                raise UnsupportedFormat("unsupported MAT small-data tag")
            stop = start + 8
            payload = self.data[start + 4 : start + 4 + size]
        self.position = stop
        return kind, payload, self.data[start:stop]

    def ended(self) -> bool:
        return self.position == len(self.data)


def _integers(payload: memoryview, endian: str) -> List[int]:
    if len(payload) % 4:
        raise ValueError("invalid MAT integer element size")
    return [entry[0] for entry in struct.iter_unpack(endian + "i", payload)]


def matrix(payload: memoryview, endian: str, budget: Budget, depth: int = 0) -> None:
    if depth > 64:
        raise UnsupportedFormat("MAT nesting exceeds supported profile")
    if not payload:
        return
    parts = Elements(payload, endian, budget)
    kind, flags, _ = parts.tag()
    if kind != 6 or len(flags) != 8:
        raise ValueError("invalid MAT array flags")
    bits, nzmax = struct.unpack(endian + "II", flags)
    cls, complex_values = bits & 255, bool(bits & 0x800)
    kind, dimensions, _ = parts.tag()
    if kind != 5:
        raise ValueError("invalid MAT dimensions tag")
    shape = _integers(dimensions, endian)
    if len(shape) < 2 or len(shape) > 32 or any(n < 0 for n in shape):
        raise ValueError("invalid MAT dimensions")
    count = 1
    for n in shape:
        count *= n
    kind, name, _ = parts.tag()
    if kind not in (1, 2, 16):
        raise UnsupportedFormat("unsupported MAT variable name representation")
    if cls in (1, 2):
        _container(parts, cls, complex_values, count, endian, budget, depth)
    elif cls == 5:
        _sparse(parts, shape, nzmax, complex_values, endian)
    elif cls == 4 or 6 <= cls <= 15:
        _primitive(parts, cls, count, complex_values)
    else:
        raise UnsupportedFormat("unsupported MAT class/object representation: " + str(cls))
    if not parts.ended():
        raise ValueError("unconsumed MAT matrix subelements")


def _container(
    parts: Elements,
    cls: int,
    complex_values: bool,
    count: int,
    endian: str,
    budget: Budget,
    depth: int,
) -> None:
    fields = 1
    if complex_values:
        raise ValueError("complex flag on a MAT container")
    if cls == 2:
        kind, length, _ = parts.tag()
        if kind != 5 or len(length) != 4:
            raise ValueError("invalid MAT structure field-name length")
        length = struct.unpack(endian + "i", length)[0]
        kind, names, _ = parts.tag()
        if kind != 1 or not 1 <= length <= 65536 or len(names) % length:
            raise ValueError("invalid MAT structure field names")
        fields = len(names) // length
    if count * fields > budget.limits.nodes - budget.nodes:
        raise UnsupportedFormat("MAT container exceeds record budget")
    for _ in range(count * fields):
        kind, content, _ = parts.tag()
        if kind != 14:
            raise ValueError("MAT cell/struct member is not a matrix")
        matrix(content, endian, budget, depth + 1)


def _sparse(parts: Elements, shape: Any, nzmax: int, complex_values: bool, endian: str) -> None:
    if len(shape) != 2:
        raise ValueError("MAT sparse matrix is not two-dimensional")
    kind, row_data, _ = parts.tag()
    if kind != 5:
        raise ValueError("invalid MAT sparse row indexes")
    rows = _integers(row_data, endian)
    kind, column_data, _ = parts.tag()
    if kind != 5:
        raise ValueError("invalid MAT sparse column indexes")
    columns = _integers(column_data, endian)
    if (
        len(columns) != shape[1] + 1
        or not columns
        or columns[0] != 0
        or any(a > b for a, b in zip(columns, columns[1:]))
        or not 0 <= columns[-1] <= len(rows) <= nzmax
        or any(not 0 <= row < shape[0] for row in rows[: columns[-1]])
    ):
        raise ValueError("invalid MAT sparse index structure")
    for _ in range(2 if complex_values else 1):
        kind, values, _ = parts.tag()
        if kind not in WIDTHS or len(values) != len(rows) * WIDTHS[kind]:
            raise ValueError("invalid MAT sparse values")


def _primitive(parts: Elements, cls: int, count: int, complex_values: bool) -> None:
    for _ in range(2 if complex_values else 1):
        kind, values, _ = parts.tag()
        allowed = (1, 2, 3, 4, 16, 17, 18) if cls == 4 else (1, 2, 3, 4, 5, 6, 7, 9, 12, 13)
        if kind not in allowed or (cls == 4 and complex_values):
            raise ValueError("invalid MAT numeric/character payload")
        if cls == 4 and kind == 16:
            if len(bytes(values).decode("utf-8")) != count:
                raise ValueError("MAT UTF-8 dimensions do not match")
        elif len(values) != count * WIDTHS[kind]:
            raise ValueError("MAT array dimensions and payload length disagree")


def level5(data: bytes, budget: Budget, rewrite: bool = False) -> Tuple[bytes, Tuple[Any, ...]]:
    if len(data) < 128 or data[126:128] not in (b"IM", b"MI"):
        raise UnsupportedFormat("not a supported Level-5 MAT file")
    endian = "<" if data[126:128] == b"IM" else ">"
    if struct.unpack(endian + "H", data[124:126])[0] != 256:
        raise UnsupportedFormat("unsupported MAT header version")
    if any(data[116:124]):
        raise UnsupportedFormat("nonzero MAT subsystem offset is outside the profile")
    parts = Elements(memoryview(data)[128:], endian, budget)
    output = bytearray(data[:128])
    fingerprints: List[Any] = [data[:128].hex()]
    compressed = 0
    while not parts.ended():
        kind, content, original = parts.tag()
        if kind == 15:
            raw = inflate(bytes(content), budget)
            inner = Elements(raw, endian, budget)
            inner_kind, values, _ = inner.tag()
            if inner_kind != 14 or not inner.ended():
                raise ValueError("compressed MAT element must contain one complete matrix")
            matrix(values, endian, budget)
            fingerprints.append(("compressed", hashlib.sha256(raw).hexdigest()))
            compressed += 1
            if rewrite:
                encoded = zlib.compress(raw, 9)
                output.extend(struct.pack(endian + "II", 15, len(encoded)))
                output.extend(encoded)
            else:
                output.extend(original)
        elif kind == 14:
            matrix(content, endian, budget)
            budget.consume(decoded=len(content))
            fingerprints.append(("raw", hashlib.sha256(original).hexdigest()))
            output.extend(original)
        else:
            raise UnsupportedFormat("unsupported top-level MAT element")
    if not compressed and rewrite:
        raise UnsupportedFormat("no existing compressed MAT elements; dialect conversion disabled")
    return bytes(output), tuple(fingerprints)


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    with open(source, "rb") as stream:
        header = stream.read(520)
    if header.startswith(b"MATLAB 7.3 MAT-file") and header[512:520] == b"\x89HDF\r\n\x1a\n":
        if action == "rewrite" and not options.get("experimental_formats"):
            raise UnsupportedFormat(
                "MAT v7.3 native MATLAB reader gate pending; experimental opt-in required"
            )
        from .hierarchical import operate as hdf_operation

        result = hdf_operation("hdf5-native", action, source, candidate, options, budget)
        result.setdefault("details", {}).update(
            profile="MAT-v7.3", experimental=True, native_reader_gate="MATLAB pending"
        )
        return result
    data = read_small(source, budget)
    _, fingerprint = level5(data, budget)
    details = {
        "profile": "MAT-Level-5-existing-compression",
        "experimental": True,
        "native_reader_gate": "MATLAB pending",
    }
    if action == "inspect":
        return {"details": details}
    if action == "compare":
        _, other = level5(read_small(candidate or "", budget), budget)
        if fingerprint != other:
            raise ValueError("MAT decoded elements or retained records differ")
        return {"equal": True, "details": details}
    if not options.get("experimental_formats"):
        raise UnsupportedFormat(
            "MAT native MATLAB reader gate pending; experimental opt-in required"
        )
    output, expected = level5(data, budget, rewrite=True)
    assert candidate is not None
    write_bytes(candidate, output, budget)
    _, actual = level5(read_small(candidate, budget), budget)
    if expected != actual or fingerprint != actual:
        raise ValueError("MAT rewrite changed header, framing or decoded elements")
    return {"changed": True, "details": details}


@guard_packer
def pack_mat(filepath: str, debug: bool = False, quiet: bool = False, **commit: Any) -> PackResult:
    return pack_format("mat", filepath, dict(commit))
