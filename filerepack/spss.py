"""Exact dictionary/case-element SAV candidates and separately gated ZSAV envelopes.

No dataframe conversion, character decoding or object deserialization is used.
IEEE numeric abbreviations are selected only after a bit-exact decode check.
"""

import hashlib
import math
import struct
import zlib
from typing import Any, Dict, List, Optional

from .format_support import Budget, UnsupportedFormat, inflate, read_small, write_bytes
from .transactions import guard_packer

EXTENSIONS = {3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22}


class SystemFile:
    def __init__(self, data: bytes, budget: Budget):
        self.data, self.budget, self.pos = data, budget, 176
        if len(data) < 184 or data[:4] not in (b"$FL2", b"$FL3"):
            raise UnsupportedFormat("not an ASCII SAV/ZSAV system file")
        self.endian = "<" if struct.unpack_from("<i", data, 64)[0] in (2, 3) else ">"
        layout, nominal, self.mode, weight, self.cases = struct.unpack_from(
            self.endian + "5i", data, 64
        )
        self.bias = struct.unpack_from(self.endian + "d", data, 84)[0]
        if (
            layout not in (2, 3)
            or self.mode not in (0, 1, 2)
            or self.cases < -1
            or ((self.mode == 2) != (data[:4] == b"$FL3"))
            or self.bias != 100.0
        ):
            raise UnsupportedFormat("unsupported SAV header/bias/endianness")
        self.types: List[bool] = []
        self.system_missing = struct.pack(
            self.endian + "d", -float.fromhex("0x1.fffffffffffffp1023")
        )
        self._dictionary()
        if not self.types or weight < 0 or weight > len(self.types):
            raise ValueError("invalid SAV variable/weight index")
        self.dictionary = data[: self.pos]

    def take(self, count: int) -> bytes:
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("truncated SAV dictionary/data record")
        raw = self.data[self.pos : self.pos + count]
        self.pos += count
        return raw

    def integer(self) -> int:
        return int(struct.unpack(self.endian + "i", self.take(4))[0])

    def count(self) -> int:
        count = self.integer()
        if count < 0:
            raise ValueError("negative SAV record length/count")
        self.budget.consume(nodes=count)
        return count

    def _variable(self) -> None:
        width, label, missing, _, _ = struct.unpack(self.endian + "5i", self.take(20))
        self.take(8)
        if width < -1 or width > 255 or label not in (0, 1) or missing not in (0, 1, 2, 3, -2, -3):
            raise ValueError("invalid SAV variable record")
        if width == -1 and (not self.types or not self.types[-1]):
            raise ValueError("orphan SAV string continuation")
        self.types.append(width != 0)
        if label:
            size = self.count()
            self.take((size + 3) // 4 * 4)
        self.take(abs(missing) * 8)

    def _extension(self) -> None:
        subtype, size, count = self.integer(), self.count(), self.count()
        if subtype not in EXTENSIONS or size < 1:
            raise UnsupportedFormat("unknown SAV dictionary extension")
        raw = self.take(size * count)
        if subtype == 3:
            if (size, count) != (4, 8):
                raise ValueError("invalid SAV machine integer record")
            values = struct.unpack(self.endian + "8i", raw)
            if values[4] != 1 or values[6] != (2 if self.endian == "<" else 1) or values[7] == 1:
                raise UnsupportedFormat("non-IEEE/EBCDIC SAV data")
        if subtype == 4:
            if (size, count) != (8, 3) or raw[:8] != self.system_missing:
                raise UnsupportedFormat("nonstandard SAV system-missing bit representation")

    def _dictionary(self) -> None:
        while True:
            self.budget.consume(nodes=1)
            record = self.integer()
            if record == 2:
                self._variable()
            elif record == 3:
                for _ in range(self.count()):
                    self.take(8)
                    size = self.take(1)[0]
                    self.take((size + 1 + 7) // 8 * 8 - 1)
                if self.integer() != 4:
                    raise ValueError("SAV value labels lack variable associations")
                for _ in range(self.count()):
                    index = self.integer()
                    if not 1 <= index <= len(self.types):
                        raise ValueError("invalid SAV value-label variable index")
            elif record == 6:
                self.take(self.count() * 80)
            elif record == 7:
                self._extension()
            elif record == 999:
                if self.integer() != 0:
                    raise ValueError("invalid SAV dictionary terminator")
                return
            else:
                raise UnsupportedFormat("unknown SAV dictionary record: " + str(record))

    def zblocks(self) -> List[bytes]:
        start, trailer, trailer_len = struct.unpack(self.endian + "3q", self.take(24))
        if (
            start != len(self.dictionary)
            or trailer_len < 48
            or (trailer_len - 24) % 24
            or (trailer + trailer_len != len(self.data))
            or trailer < self.pos
        ):
            raise ValueError("invalid ZSAV data header/trailer bounds")
        bias, zero, size, count = struct.unpack_from(self.endian + "qqii", self.data, trailer)
        if bias != -100 or zero or size <= 0 or count != (trailer_len - 24) // 24:
            raise ValueError("invalid ZSAV trailer/header")
        self.budget.consume(nodes=count)
        uncompressed, compressed, blocks = start, self.pos, []
        for index in range(count):
            uofs, cofs, usize, csize = struct.unpack_from(
                self.endian + "qqii", self.data, trailer + 24 + 24 * index
            )
            if (
                (uofs, cofs) != (uncompressed, compressed)
                or usize <= 0
                or csize <= 0
                or (index < count - 1 and usize != size)
                or usize > size
                or cofs + csize > trailer
            ):
                raise ValueError("invalid ZSAV block index/size")
            block = inflate(self.data[cofs : cofs + csize], self.budget)
            if len(block) != usize:
                raise ValueError("ZSAV decoded block size mismatch")
            blocks.append(block)
            uncompressed += usize
            compressed += csize
        if compressed != trailer:
            raise ValueError("ZSAV block stream/trailer gap")
        self.budget.memory(sum(map(len, blocks)) * 2)
        return blocks

    def elements(self, stream: bytes) -> bytes:
        if self.mode == 0:
            raw = stream
        else:
            raw = decode_cases(stream, self)
        case_size = len(self.types) * 8
        if len(raw) % case_size or (self.cases >= 0 and len(raw) != self.cases * case_size):
            raise ValueError("SAV complete case count/framing mismatch")
        self.budget.consume(decoded=len(raw), nodes=len(raw) // 8)
        return raw


def decode_cases(stream: bytes, source: SystemFile) -> bytes:
    """Independent passive bytecode decoder; no writer callbacks or numeric coercion."""
    position, output, finished = 0, bytearray(), False
    while position < len(stream):
        if len(stream) - position < 8:
            raise ValueError("truncated SAV bytecode instruction block")
        codes = stream[position : position + 8]
        position += 8
        for index, code in enumerate(codes):
            source.budget.check()
            if code == 0:
                continue
            if code == 252:
                if any(codes[index + 1 :]) or position != len(stream):
                    raise ValueError("SAV payload after EOF bytecode")
                finished = True
                break
            string = source.types[(len(output) // 8) % len(source.types)]
            if code == 253:
                element = stream[position : position + 8]
                if len(element) != 8:
                    raise ValueError("truncated SAV literal element")
                position += 8
            elif code == 254 and string:
                element = b" " * 8
            elif code == 255 and not string:
                element = source.system_missing
            elif code <= 251 and not string:
                element = struct.pack(source.endian + "d", code - source.bias)
            elif code == 100 and string:
                element = b"\0" * 8
            else:
                raise UnsupportedFormat("invalid SAV code for case-element type")
            output.extend(element)
            if len(output) > min(
                source.budget.limits.memory // 8,
                source.budget.limits.decoded - source.budget.decoded,
            ):
                raise UnsupportedFormat("SAV decoded cases exceed bounded parser profile")
        if finished:
            break
    return bytes(output)


def encode_cases(raw: bytes, source: SystemFile) -> bytes:
    output, codes, literals = bytearray(), bytearray(), bytearray()
    for index in range(0, len(raw), 8):
        source.budget.check()
        element = raw[index : index + 8]
        string = source.types[(index // 8) % len(source.types)]
        code = 253
        if string and element == b" " * 8:
            code = 254
        elif string and element == b"\0" * 8:
            code = 100
        elif not string:
            if element == source.system_missing:
                code = 255
            else:
                value = struct.unpack(source.endian + "d", element)[0]
                if math.isfinite(value) and 1 <= value + source.bias <= 251:
                    trial = int(value + source.bias)
                    if struct.pack(source.endian + "d", trial - source.bias) == element:
                        code = trial
        codes.append(code)
        if code == 253:
            literals.extend(element)
        if len(codes) == 8:
            output.extend(codes + literals)
            codes, literals = bytearray(), bytearray()
    codes.append(252)
    output.extend(codes + b"\0" * (8 - len(codes)) + literals)
    return bytes(output)


def _zsav(source: SystemFile, blocks: List[bytes]) -> bytes:
    base = source.dictionary
    compressed = [zlib.compress(block, 9) for block in blocks]
    trailer = len(base) + 24 + sum(map(len, compressed))
    header = struct.pack(source.endian + "3q", len(base), trailer, 24 + 24 * len(blocks))
    start, position = len(base), len(base) + 24
    original_trailer = struct.unpack_from(source.endian + "q", source.data, len(base) + 8)[0]
    table = source.data[original_trailer : original_trailer + 24]
    for raw, packed in zip(blocks, compressed):
        table += struct.pack(source.endian + "qqii", start, position, len(raw), len(packed))
        start += len(raw)
        position += len(packed)
    return base + header + b"".join(compressed) + table


def fingerprint(source: SystemFile, raw: bytes) -> Any:
    dictionary = bytearray(source.dictionary)
    if source.mode != 2:
        dictionary[72:76] = b"\0" * 4
    return bytes(dictionary), hashlib.sha256(raw).hexdigest()


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    original = SystemFile(read_small(source, budget), budget)
    blocks = original.zblocks() if original.mode == 2 else None
    stream = b"".join(blocks) if blocks else original.data[original.pos :]
    raw = original.elements(stream)
    details = {
        "profile": "ZSAV-zlib" if blocks else "SAV-IEEE-bytecode",
        "source_compression": original.mode,
        "case_elements": len(raw) // 8,
        "dictionary_policy": "exact bytes",
        "tested_reader": "ReadStat via pyreadstat 1.3.6",
    }
    if blocks:
        details.update(experimental=True, native_reader_gate="independent ZSAV corpus pending")
    if action == "inspect":
        return {"details": details}
    assert candidate is not None
    if action == "rewrite":
        if blocks:
            # No real independent-origin ZSAV corpus gate has passed yet.
            if not options.get("experimental_formats"):
                return {
                    "changed": False,
                    "reason": "ZSAV rewrite requires experimental_formats; "
                    "real-corpus compatibility gate pending",
                    "details": details,
                }
            encoded = _zsav(original, blocks)
        else:
            header = bytearray(original.dictionary)
            header[72:76] = struct.pack(original.endian + "i", 1)
            encoded = bytes(header) + encode_cases(raw, original)
        write_bytes(candidate, encoded, budget)
    other = SystemFile(read_small(candidate, budget), budget)
    otherblocks = other.zblocks() if other.mode == 2 else None
    otherraw = other.elements(b"".join(otherblocks) if otherblocks else other.data[other.pos :])
    if fingerprint(original, raw) != fingerprint(other, otherraw):
        raise ValueError("SAV dictionary or exact case bytes changed")
    if blocks and otherblocks != blocks:
        raise ValueError("ZSAV inflated block partition changed")
    return {"equal": True, "changed": action == "rewrite", "details": details}


@guard_packer
def pack_spss(filepath: str, debug: bool = False, quiet: bool = False, **commit: Any) -> Any:
    from .format_support import pack_format

    return pack_format("spss", filepath, {"debug": debug, "quiet": quiet, **commit})
