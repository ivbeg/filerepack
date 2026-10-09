"""Passive inspection for model-weight formats without a qualified writer.

The module never loads tensor payloads or executes model graphs. It reports
bounded structural facts and deliberately leaves every input unchanged.
"""

import json
import os
import struct
import stat
import ntpath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .format_support import Budget, FormatLimit, UnsupportedFormat, pack_inspection_only


_MAX_HEADER_BYTES = 32 * 1024 * 1024
_SAFETENSORS_DTYPE_BYTES = {
    "BOOL": 1,
    "U8": 1,
    "I8": 1,
    "F8_E4M3": 1,
    "F8_E4M3FN": 1,
    "F8_E5M2": 1,
    "F8_E8M0": 1,
    "U16": 2,
    "I16": 2,
    "F16": 2,
    "BF16": 2,
    "U32": 4,
    "I32": 4,
    "F32": 4,
    "U64": 8,
    "I64": 8,
    "F64": 8,
}

# GGML block element count and stored byte count for common, stable GGUF types.
# Other quantization types are reported unsupported instead of guessed.
_GGUF_TYPE_BLOCKS = {
    0: (1, 4),    # F32
    1: (1, 2),    # F16
    2: (32, 18),  # Q4_0
    3: (32, 20),  # Q4_1
    6: (32, 22),  # Q5_0
    7: (32, 24),  # Q5_1
    8: (32, 34),  # Q8_0
    9: (32, 40),  # Q8_1
    24: (1, 1),   # I8
    25: (1, 2),   # I16
    26: (1, 4),   # I32
    27: (1, 8),   # I64
    28: (1, 8),   # F64
    30: (1, 2),   # BF16
}


def _state(path: str) -> Tuple[int, ...]:
    item = os.lstat(path)
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns


def _regular_file(path: str) -> os.stat_result:
    item = os.lstat(path)
    if stat.S_ISLNK(item.st_mode) or not stat.S_ISREG(item.st_mode):
        raise UnsupportedFormat("inspection requires a regular file, not a link or special file")
    return item


def _read_prefix(path: str, limit: int, budget: Budget) -> Tuple[bytes, int]:
    before = _regular_file(path)
    maximum = min(limit, _MAX_HEADER_BYTES, budget.limits.memory // 4)
    with open(path, "rb") as source:
        if os.fstat(source.fileno()) != before:
            raise ValueError("source changed before format inspection")
        raw = source.read(maximum)
    if _state(path) != _state_from_stat(before):
        raise ValueError("source changed during format inspection")
    budget.consume(decoded=len(raw))
    return raw, before.st_size


def _state_from_stat(item: os.stat_result) -> Tuple[int, ...]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns


def _json_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key in Safetensors header")
        result[key] = value
    return result


def _safetensors_tensor(
    name: str, item: Any, data_bytes: int, budget: Budget,
) -> Tuple[str, int, int]:
    if not isinstance(name, str) or not name or not isinstance(item, dict):
        raise ValueError("invalid Safetensors tensor entry")
    if set(item) != {"dtype", "shape", "data_offsets"}:
        raise UnsupportedFormat("unknown Safetensors tensor fields")
    dtype, shape, offsets = item["dtype"], item["shape"], item["data_offsets"]
    if not isinstance(dtype, str) or dtype not in _SAFETENSORS_DTYPE_BYTES:
        raise UnsupportedFormat("unsupported Safetensors dtype: " + str(dtype))
    if (not isinstance(shape, list)
            or any(type(dim) is not int or dim < 0 or dim >= 2 ** 64 for dim in shape)
            or not isinstance(offsets, list) or len(offsets) != 2
            or any(type(offset) is not int or offset < 0 or offset >= 2 ** 64
                   for offset in offsets)):
        raise ValueError("invalid Safetensors tensor shape or offsets")
    start, end = offsets
    if start > end or end > data_bytes:
        raise ValueError("Safetensors tensor offsets exceed the data section")
    elements = 1
    for dimension in shape:
        elements *= dimension
        if elements > data_bytes + 1:
            raise ValueError("Safetensors shape is larger than its data section")
    if elements * _SAFETENSORS_DTYPE_BYTES[dtype] != end - start:
        raise ValueError("Safetensors shape/dtype size disagrees with its data offsets")
    budget.consume(nodes=1)
    return dtype, start, end


def _safetensors_entries(
    header: Dict[str, Any], data_bytes: int, budget: Budget,
) -> Tuple[int, Dict[str, int], List[str]]:
    intervals: List[Tuple[int, int]] = []
    dtype_counts: Dict[str, int] = {}
    metadata = header.get("__metadata__", {})
    if not isinstance(metadata, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in metadata.items()
    ):
        raise ValueError("Safetensors metadata must be a string-to-string object")
    for name, item in header.items():
        budget.consume(nodes=1)
        if name == "__metadata__":
            continue
        dtype, start, end = _safetensors_tensor(name, item, data_bytes, budget)
        intervals.append((start, end))
        dtype_counts[dtype] = dtype_counts.get(dtype, 0) + 1
    cursor = 0
    for start, end in sorted((item for item in intervals if item[0] != item[1])):
        if start != cursor:
            raise ValueError("Safetensors data ranges overlap or contain unclaimed bytes")
        cursor = end
    if cursor != data_bytes:
        raise ValueError("Safetensors data section has unclaimed bytes")
    return len(intervals), dtype_counts, sorted(metadata)


def _safetensors(path: str, budget: Budget) -> Dict[str, Any]:
    before = _regular_file(path)
    maximum = min(_MAX_HEADER_BYTES, budget.limits.memory // 4)
    with open(path, "rb") as source:
        if os.fstat(source.fileno()) != before:
            raise ValueError("source changed before Safetensors inspection")
        length_bytes = source.read(8)
        if len(length_bytes) != 8:
            raise ValueError("truncated Safetensors header length")
        header_length = struct.unpack("<Q", length_bytes)[0]
        if header_length < 2 or header_length > maximum or header_length > before.st_size - 8:
            raise FormatLimit("Safetensors header length is outside the bounded file limits")
        encoded = source.read(header_length)
        if len(encoded) != header_length:
            raise ValueError("truncated Safetensors header")
    if _state(path) != _state_from_stat(before):
        raise ValueError("source changed during Safetensors inspection")
    budget.consume(decoded=8 + header_length)
    header = json.loads(
        encoded,
        object_pairs_hook=_json_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("non-standard JSON constant: " + value)
        ),
    )
    if not isinstance(header, dict):
        raise ValueError("Safetensors header is not an object")
    data_bytes = before.st_size - 8 - header_length
    tensor_count, dtype_counts, metadata_keys = _safetensors_entries(
        header, data_bytes, budget
    )
    return {
        "format": "safetensors",
        "profile": "bounded-header-v1",
        "file_bytes": before.st_size,
        "header_bytes": 8 + header_length,
        "tensor_bytes": data_bytes,
        "tensor_count": tensor_count,
        "dtype_counts": dtype_counts,
        "metadata_keys": metadata_keys,
        "payload_loaded": False,
        "writer_registered": False,
    }


class _GGUFReader:
    def __init__(self, data: bytes, budget: Budget):
        self.data, self.position, self.budget = data, 0, budget

    def take(self, length: int) -> bytes:
        if length < 0 or length > len(self.data) - self.position:
            raise FormatLimit("GGUF header exceeds bounded inspection limit")
        start = self.position
        self.position += length
        return self.data[start:self.position]

    def integer(self, fmt: str) -> int:
        size = struct.calcsize(fmt)
        return int(struct.unpack("<" + fmt, self.take(size))[0])

    def string(self) -> str:
        length = self.integer("Q")
        if length > 1024 * 1024:
            raise FormatLimit("GGUF string exceeds bounded inspection limit")
        try:
            return self.take(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid UTF-8 string in GGUF header") from exc


def _gguf_metadata_value(reader: _GGUFReader, value_type: int) -> Any:
    primitive = {
        0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f",
        7: "B", 10: "Q", 11: "q", 12: "d",
    }
    if value_type in primitive:
        fmt = primitive[value_type]
        value = struct.unpack("<" + fmt, reader.take(struct.calcsize(fmt)))[0]
        if value_type == 7 and value not in (0, 1):
            raise ValueError("invalid boolean in GGUF metadata")
        return value
    if value_type == 8:
        return reader.string()
    if value_type != 9:
        raise UnsupportedFormat("unknown GGUF metadata value type")
    element_type = reader.integer("I")
    count = reader.integer("Q")
    if count > reader.budget.limits.nodes:
        raise FormatLimit("GGUF metadata array exceeds node budget")
    reader.budget.consume(nodes=count)
    if element_type == 8:
        for _ in range(count):
            reader.string()
    elif element_type in primitive:
        width = struct.calcsize(primitive[element_type])
        reader.take(width * count)
    else:
        raise UnsupportedFormat("unsupported nested GGUF metadata array")
    return {"array_count": count, "element_type": element_type}


def _gguf_metadata(reader: _GGUFReader, count: int) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for _ in range(count):
        key = reader.string()
        value_type = reader.integer("I")
        if key in metadata:
            raise ValueError("duplicate GGUF metadata key")
        metadata[key] = _gguf_metadata_value(reader, value_type)
    return metadata


def _gguf_tensor(reader: _GGUFReader, alignment: int, file_bytes: int) -> Tuple[str, int, int, int]:
    name = reader.string()
    dimensions = reader.integer("I")
    if not 1 <= dimensions <= 4:
        raise UnsupportedFormat("unsupported GGUF tensor dimension count")
    shape = [reader.integer("Q") for _ in range(dimensions)]
    if any(size == 0 for size in shape):
        raise ValueError("invalid zero GGUF tensor dimension")
    tensor_type = reader.integer("I")
    offset = reader.integer("Q")
    if offset % alignment:
        raise ValueError("GGUF tensor offset violates declared alignment")
    block = _GGUF_TYPE_BLOCKS.get(tensor_type)
    if block is None:
        raise UnsupportedFormat("unsupported GGUF tensor type: " + str(tensor_type))
    elements = 1
    for size in shape:
        elements *= size
        if elements > file_bytes:
            raise ValueError("GGUF tensor shape exceeds file size")
    block_elements, block_bytes = block
    if elements % block_elements:
        raise ValueError("GGUF tensor size is invalid for its quantization block")
    stored_bytes = (elements // block_elements) * block_bytes
    return name, offset, offset + stored_bytes, tensor_type


def _gguf_data_start(
    reader: _GGUFReader, data: bytes, file_bytes: int, alignment: int,
    tensors: List[Tuple[str, int, int, int]],
) -> int:
    data_start = (reader.position + alignment - 1) // alignment * alignment
    if data_start > file_bytes or data_start > len(data):
        raise ValueError("GGUF tensor data start exceeds file/header bounds")
    if any(data[reader.position:data_start]):
        raise ValueError("non-zero GGUF header-to-tensor padding")
    ranges = sorted((start, end, name) for name, start, end, _ in tensors if start != end)
    cursor = 0
    for start, end, name in ranges:
        if start < cursor or data_start + end > file_bytes:
            raise ValueError("overlapping or out-of-bounds GGUF tensor: " + name)
        cursor = end
    return data_start


def _gguf(path: str, budget: Budget) -> Dict[str, Any]:
    data, file_bytes = _read_prefix(path, _MAX_HEADER_BYTES, budget)
    reader = _GGUFReader(data, budget)
    if reader.take(4) != b"GGUF":
        raise UnsupportedFormat("not a little-endian GGUF file")
    version = reader.integer("I")
    tensor_count = reader.integer("Q")
    metadata_count = reader.integer("Q")
    if version not in (2, 3):
        raise UnsupportedFormat("unsupported GGUF version")
    if tensor_count > budget.limits.nodes or metadata_count > budget.limits.nodes:
        raise FormatLimit("GGUF descriptor count exceeds node budget")
    budget.consume(nodes=tensor_count + metadata_count)
    metadata = _gguf_metadata(reader, metadata_count)
    alignment = metadata.get("general.alignment", 32)
    if type(alignment) is not int or alignment < 8 or alignment > 1024 * 1024 or alignment % 8:
        raise ValueError("invalid GGUF general.alignment")
    tensors = [
        _gguf_tensor(reader, alignment, file_bytes) for _ in range(tensor_count)
    ]
    names = [item[0] for item in tensors]
    if len(names) != len(set(names)):
        raise ValueError("duplicate GGUF tensor name")
    data_start = _gguf_data_start(reader, data, file_bytes, alignment, tensors)
    dtype_counts: Dict[str, int] = {}
    for _, _, _, tensor_type in tensors:
        dtype_counts[str(tensor_type)] = dtype_counts.get(str(tensor_type), 0) + 1
    return {
        "format": "gguf",
        "version": version,
        "file_bytes": file_bytes,
        "header_bytes": data_start,
        "tensor_data_bytes": file_bytes - data_start,
        "tensor_count": len(tensors),
        "metadata_count": len(metadata),
        "alignment": alignment,
        "tensor_types": dtype_counts,
        "payload_loaded": False,
        "writer_registered": False,
    }


def _external_location(base: str, location: str) -> Tuple[str, os.stat_result]:
    drive, _ = ntpath.splitdrive(location)
    parts = location.split("/")
    if (not location or drive or location.startswith("/") or "\\" in location
            or ":" in location or any(part in ("", ".", "..") for part in parts)):
        raise UnsupportedFormat("unsafe ONNX external-data location")
    current = os.path.abspath(base)
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        try:
            item = os.lstat(current)
        except FileNotFoundError as exc:
            raise UnsupportedFormat("missing ONNX external-data file") from exc
        if stat.S_ISLNK(item.st_mode):
            raise UnsupportedFormat("symlink in ONNX external-data path")
        if index < len(parts) - 1 and not stat.S_ISDIR(item.st_mode):
            raise UnsupportedFormat("non-directory ONNX external-data path component")
    if not stat.S_ISREG(item.st_mode):
        raise UnsupportedFormat("ONNX external data must reference a regular file")
    return current, item


def _onnx_messages(model: Any, budget: Budget) -> Iterable[Any]:
    pending = [model]
    while pending:
        message = pending.pop()
        budget.consume(nodes=1)
        yield message
        for field, value in message.ListFields():
            if not field.message_type:
                continue
            repeated = field.is_repeated if hasattr(field, "is_repeated") else (
                field.label == field.LABEL_REPEATED
            )
            children = value if repeated else (value,)
            for child in children:
                if not hasattr(child, "ListFields"):
                    continue
                if len(pending) >= budget.limits.nodes:
                    raise FormatLimit("ONNX message graph exceeds node budget")
                pending.append(child)


def _onnx_external_tensor(
    tensor: Any, onnx: Any, base: str,
) -> Optional[Tuple[str, os.stat_result]]:
    if tensor.data_location != onnx.TensorProto.EXTERNAL:
        return None
    fields: Dict[str, str] = {}
    for entry in tensor.external_data:
        if entry.key in fields:
            raise ValueError("duplicate ONNX external-data key")
        fields[entry.key] = entry.value
    if "location" not in fields:
        raise ValueError("ONNX external tensor has no location")
    resolved, info = _external_location(base, fields["location"])
    try:
        offset = int(fields.get("offset", "0"))
        length = int(fields["length"]) if "length" in fields else None
    except ValueError as exc:
        raise ValueError("invalid ONNX external-data offset/length") from exc
    if offset < 0 or (length is not None and length < 0):
        raise ValueError("negative ONNX external-data offset/length")
    if offset > info.st_size or (length is not None and offset + length > info.st_size):
        raise ValueError("ONNX external-data range exceeds its file")
    return resolved, info


def _onnx(path: str, budget: Budget) -> Dict[str, Any]:
    before = _regular_file(path)
    maximum = min(_MAX_HEADER_BYTES, budget.limits.memory // 8)
    if before.st_size > maximum:
        raise FormatLimit("ONNX protobuf exceeds bounded in-memory inspection limit")
    try:
        import onnx
    except ImportError as exc:
        raise UnsupportedFormat("ONNX inspection requires filerepack[onnx]") from exc
    with open(path, "rb") as source:
        if os.fstat(source.fileno()) != before:
            raise ValueError("source changed before ONNX inspection")
        payload = source.read(maximum + 1)
    if len(payload) != before.st_size or _state(path) != _state_from_stat(before):
        raise ValueError("source changed during ONNX inspection")
    budget.consume(decoded=len(payload))
    budget.memory(len(payload) * 2)
    try:
        model = onnx.load_model_from_string(payload)
    except Exception as exc:
        raise ValueError("ONNX protobuf parser rejected the model: " + str(exc)) from exc
    base = os.path.dirname(os.path.abspath(path))
    external: Dict[str, os.stat_result] = {}
    tensor_count = 0
    for message in _onnx_messages(model, budget):
        if message.DESCRIPTOR.full_name == "onnx.TensorProto":
            tensor_count += 1
            reference = _onnx_external_tensor(message, onnx, base)
            if reference:
                external[reference[0]] = reference[1]
    checker_status = "not_run_external_data"
    if not external:
        try:
            onnx.checker.check_model(model)
        except Exception as exc:
            raise ValueError("ONNX checker rejected the model: " + str(exc)) from exc
        checker_status = "passed"
    return {
        "format": "onnx",
        "ir_version": model.ir_version,
        "graph_nodes": len(model.graph.node) if model.HasField("graph") else 0,
        "tensor_messages": tensor_count,
        "file_bytes": before.st_size,
        "external_files": len(external),
        "external_bytes": sum(item.st_size for item in external.values()),
        "external_data_paths": sorted(os.path.relpath(name, base) for name in external),
        "onnx_checker": checker_status,
        "graph_executed": False,
        "writer_registered": False,
    }


def _inspect(kind: str, source: str, budget: Budget) -> Dict[str, Any]:
    if kind == "safetensors":
        return _safetensors(source, budget)
    if kind == "gguf":
        return _gguf(source, budget)
    if kind == "onnx":
        return _onnx(source, budget)
    raise UnsupportedFormat("unknown model format inspection kind")


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    details = _inspect(kind, source, budget)
    if action not in ("inspect", "rewrite"):
        raise UnsupportedFormat("model-weight formats are inspection-only")
    return {
        "changed": False,
        "reason": "no qualified lossless same-format writer; inspection only",
        "details": details,
    }


def pack_safetensors(
    filepath: str, debug: bool = False, quiet: bool = False, **options: Any,
) -> Any:
    return pack_inspection_only("safetensors", filepath, options)


def pack_gguf(
    filepath: str, debug: bool = False, quiet: bool = False, **options: Any,
) -> Any:
    return pack_inspection_only("gguf", filepath, options)


def pack_onnx(
    filepath: str, debug: bool = False, quiet: bool = False, **options: Any,
) -> Any:
    return pack_inspection_only("onnx", filepath, options)
