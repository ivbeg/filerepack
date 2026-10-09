"""Passive XDR R serialization validation and exact envelope recompression.

No R runtime, object constructor, namespace resolver or ALTREP hook is invoked.
Unknown extension records and compiled bytecode are outside the initial profile.
"""

import bz2
import hashlib
import lzma
import struct
import zlib
from typing import Any, Dict, List, Optional, Tuple

from .format_support import Budget, UnsupportedFormat, inflate, pack_format, read_small
from .models import PackResult
from .transactions import guard_packer


class XDRParser:
    def __init__(self, data: bytes, budget: Budget):
        self.data = memoryview(data)
        self.position = 0
        self.budget = budget
        self.references: List[Tuple[int, Optional[bytes]]] = []

    def take(self, size: int) -> memoryview:
        if size < 0 or size > len(self.data) - self.position:
            raise ValueError("truncated XDR serialization record")
        start = self.position
        self.position += size
        return self.data[start : self.position]

    def integer(self) -> int:
        return int(struct.unpack(">i", self.take(4))[0])

    def length(self) -> int:
        length = self.integer()
        if length == -1:
            high, low = self.integer(), self.integer()
            if high < 0:
                raise ValueError("invalid long R vector length")
            length = (high << 32) | (low & 0xFFFFFFFF)
        if length < 0:
            raise ValueError("invalid R vector length")
        return length

    def node(self, depth: int = 0, flags: Optional[int] = None) -> Tuple[int, Optional[bytes]]:
        if depth > 128:
            raise UnsupportedFormat("R object nesting exceeds supported profile")
        self.budget.consume(nodes=1)
        flags = self.integer() if flags is None else flags
        kind = flags & 255
        attributes, tag = bool(flags & 512), bool(flags & 1024)
        if kind in (241, 242, 250, 251, 252, 253, 254):
            if flags != kind:
                raise ValueError("invalid flags on special R record")
            return kind, None
        if kind == 255:
            index = (flags & 0xFFFFFFFF) >> 8
            index = index or self.integer()
            if not 1 <= index <= len(self.references):
                raise ValueError("invalid R reference index")
            return self.references[index - 1]
        if kind == 1:
            value = self.node(depth + 1)
            if value[0] != 9 or value[1] is None:
                raise ValueError("R symbol has no character name")
            result = (kind, value[1])
            self.references.append(result)
            return result
        if kind == 4:
            if self.integer() not in (0, 1):
                raise ValueError("invalid environment lock flag")
            self.references.append((kind, None))
            for _ in range(4):
                self.node(depth + 1)
            return kind, None
        if kind in (2, 3, 5, 6, 17):
            return self._pairlist(depth, flags)
        if kind == 238:
            # Only the two built-in compact sequence representations are profiled.
            info = self.node(depth + 1)
            if info[1] not in (b"compact_intseq", b"compact_realseq"):
                raise UnsupportedFormat("unsupported R ALTREP representation")
            self.node(depth + 1)
            self.node(depth + 1)
            return kind, None
        if tag:
            raise UnsupportedFormat("tag on unsupported R record type")
        return self._value(kind, depth, attributes)

    def _pairlist(self, depth: int, flags: int) -> Tuple[int, Optional[bytes]]:
        # Pairlist CDR traversal is iterative, so long attribute lists do not
        # consume the Python call stack. No values are instantiated.
        kind = flags & 255
        original, name = kind, None
        while kind in (2, 3, 5, 6, 17):
            if flags & 512:
                self.node(depth + 1)
            if flags & 1024:
                self.node(depth + 1)
            item = self.node(depth + 1)
            name = name or item[1]
            flags = self.integer()
            kind = flags & 255
            if kind in (2, 3, 5, 6, 17):
                self.budget.consume(nodes=1)
        self.node(depth + 1, flags)
        return original, name

    def _value(self, kind: int, depth: int, attributes: bool) -> Tuple[int, Optional[bytes]]:
        name = None
        if kind == 9:
            length = self.integer()
            if length < -1:
                raise ValueError("invalid R string length")
            if length >= 0:
                content = self.take(length)
                name = bytes(content) if length <= 1024 else b""
        elif kind in (10, 13, 14, 15, 24):
            widths = {10: 4, 13: 4, 14: 8, 15: 16, 24: 1}
            self.take(self.length() * widths[kind])
        elif kind in (16, 19, 20):
            count = self.length()
            if count > len(self.data) // 4:
                raise ValueError("impossible R object-vector length")
            for _ in range(count):
                item = self.node(depth + 1)
                if kind == 16 and item[0] != 9:
                    raise ValueError("R character vector contains a non-character record")
        elif kind == 25:
            pass
        else:
            raise UnsupportedFormat("unsupported R serialization record type: " + str(kind))
        if attributes:
            self.node(depth + 1)
        return kind, name


def parse_stream(raw: bytes, budget: Budget) -> Dict[str, Any]:
    workspace = raw.startswith((b"RDX2\n", b"RDX3\n"))
    prefix = raw[:5] if workspace else b""
    parser = XDRParser(raw, budget)
    if workspace:
        parser.take(5)
    if bytes(parser.take(2)) != b"X\n":
        raise UnsupportedFormat("only XDR R serialization versions 2/3 are supported")
    version, writer, minimum = parser.integer(), parser.integer(), parser.integer()
    if version not in (2, 3) or minimum <= 0 or writer < minimum:
        raise UnsupportedFormat("unsupported or inconsistent R serialization version")
    if prefix and prefix[3] != ord(str(version)):
        raise ValueError("workspace and serialization versions disagree")
    if version == 3:
        encoding = parser.integer()
        if not 0 < encoding <= 1024:
            raise ValueError("invalid R native-encoding header")
        parser.take(encoding)
    root = parser.node()
    if workspace and root[0] not in (2, 254):
        raise ValueError("workspace root is not a named pairlist")
    if parser.position != len(raw):
        raise ValueError("trailing R serialization bytes")
    return {
        "profile": "XDR-v" + str(version),
        "kind": "workspace" if workspace else "RDS",
        "serialization_version": version,
        "writer_version": writer,
        "minimum_reader_version": minimum,
    }


def envelope(data: bytes, budget: Budget) -> Tuple[str, bytes, bytes]:
    if data.startswith(b"\x1f\x8b"):
        if len(data) < 18 or data[2] != 8 or data[3] & 0xE0:
            raise ValueError("invalid gzip header")
        flags, position = data[3], 10
        if flags & 4:
            if len(data) < position + 2:
                raise ValueError("truncated gzip extra header")
            length = int.from_bytes(data[position : position + 2], "little")
            position += 2 + length
            # Private extras can contain payload-dependent fields.
            raise UnsupportedFormat("R gzip extra fields have no verified preservation profile")
        for bit in (8, 16):
            if flags & bit:
                end = data.find(b"\0", position)
                if end < 0:
                    raise ValueError("unterminated gzip metadata")
                position = end + 1
        if flags & 2:
            position += 2
        if position > len(data) - 8:
            raise ValueError("truncated gzip header")
        return "gzip", inflate(data, budget, "gzip"), data[:position]
    if data.startswith(b"BZh"):
        return "bzip2", inflate(data, budget, "bzip2"), b""
    if data.startswith(b"\xfd7zXZ\0"):
        return "xz", inflate(data, budget, "xz"), b""
    budget.consume(decoded=len(data))
    return "uncompressed", data, b""


def write_envelope(path: str, raw: bytes, codec: str, header: bytes, budget: Budget) -> None:
    compressor: Any = None
    prefix = b""
    if codec == "gzip":
        metadata = bytearray(header or b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff")
        metadata[8] = 2
        if metadata[3] & 2:
            metadata[-2:] = (zlib.crc32(metadata[:-2]) & 65535).to_bytes(2, "little")
        prefix = bytes(metadata)
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    elif codec == "bzip2":
        compressor = bz2.BZ2Compressor(9)
    elif codec == "xz":
        compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=6)
    with open(path, "wb") as output:

        def emit(block: bytes) -> None:
            budget.consume(written=len(block))
            output.write(block)

        emit(prefix)
        for position in range(0, len(raw), 65536):
            block = raw[position : position + 65536]
            emit(compressor.compress(block) if compressor else block)
        if compressor:
            emit(compressor.flush())
        if codec == "gzip":
            emit(struct.pack("<II", zlib.crc32(raw), len(raw) & 0xFFFFFFFF))


def inspect(path: str, budget: Budget) -> Tuple[Dict[str, Any], bytes, bytes]:
    data = read_small(path, budget)
    codec, raw, header = envelope(data, budget)
    details = parse_stream(raw, budget)
    details.update(
        source_codec=codec, decoded_bytes=len(raw), decoded_sha256=hashlib.sha256(raw).hexdigest()
    )
    return details, raw, header


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    details, raw, header = inspect(source, budget)
    if action == "inspect":
        return {"details": details}
    if action == "compare":
        other, decoded, _ = inspect(candidate or "", budget)
        if raw != decoded:
            raise ValueError("R serialization streams differ")
        return {"details": details, "equal": True}
    codec = options.get("r_compression", "preserve")
    codec = details["source_codec"] if codec == "preserve" else codec
    if codec not in ("uncompressed", "gzip", "bzip2", "xz"):
        raise ValueError("invalid R compression option")
    if header and codec != "gzip" and (header[3] & 0x1E or any(header[4:8])):
        raise UnsupportedFormat("gzip metadata has no equivalent in the selected R wrapper")
    assert candidate is not None
    write_envelope(candidate, raw, codec, header if codec == "gzip" else b"", budget)
    other, decoded, _ = inspect(candidate, budget)
    if raw != decoded or other["kind"] != details["kind"]:
        raise ValueError("R envelope rewrite changed serialization")
    details.update(
        output_codec=codec,
        reader_validation="trusted fixture matrix; passive runtime",
        wrapper_reader_floor="R 2.10+" if codec in ("xz", "bzip2") else "source profile",
    )
    return {"changed": True, "details": details}


@guard_packer
def pack_r_serialization(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any
) -> PackResult:
    return pack_format("r-serialization", filepath, {"debug": debug, "quiet": quiet, **commit})
