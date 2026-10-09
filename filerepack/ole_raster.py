"""Bounded raster readers independent of the OfficeArt encoder.

PNG preserves non-IDAT chunks and exact filtered samples, or independently
unfiltered samples in the qualified DOC/PPT profiles. JPEG compares coefficients.
"""

import hashlib
import math
import os
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .format_support import Budget, FormatLimit, UnsupportedFormat, inflate, write_bytes

LIMIT = 16 * 1024 * 1024
PNG_REFILTER_TRIAL_SECONDS = 1.0
PNG_FINAL_SECONDS = 20.0
PNG = b"\x89PNG\r\n\x1a\n"
KNOWN_PNG = {
    b"IHDR",
    b"PLTE",
    b"IDAT",
    b"IEND",
    b"tRNS",
    b"cHRM",
    b"gAMA",
    b"iCCP",
    b"sBIT",
    b"sRGB",
    b"bKGD",
    b"hIST",
    b"pHYs",
    b"sPLT",
    b"tIME",
    b"iTXt",
    b"tEXt",
    b"zTXt",
    b"eXIf",
    b"cICP",
    b"mDCV",
    b"cLLI",
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise UnsupportedFormat("OfficeArt raster: " + reason)


def chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


@dataclass(frozen=True)
class PngData:
    chunks: Tuple[Tuple[bytes, bytes], ...]
    raw: bytes

    def fingerprint(self) -> Tuple[object, ...]:
        return tuple(c for c in self.chunks if c[0] != b"IDAT"), self.raw

    def rebuild(self, encoded: bytes) -> bytes:
        parts, emitted = [PNG], False
        for kind, body in self.chunks:
            if kind == b"IDAT":
                if not emitted:
                    parts.append(chunk(kind, encoded))
                    emitted = True
            else:
                parts.append(chunk(kind, body))
        return b"".join(parts)


@dataclass(frozen=True)
class PngIdentity:
    """Compact exact-sample identity; expanded data is released between images."""

    chunks: Tuple[Tuple[bytes, bytes], ...]
    size: int
    sha256: str
    refilter: bool = False
    filtered_sha256: str = ""

    @classmethod
    def from_data(
        cls, parsed: PngData, *, refilter: bool = False, budget: Optional[Budget] = None
    ) -> "PngIdentity":
        filtered = hashlib.sha256(parsed.raw).hexdigest()
        refilter = refilter and png_refilterable(parsed)
        return cls(
            tuple(c for c in parsed.chunks if c[0] != b"IDAT"),
            len(parsed.raw),
            png_samples_digest(parsed, budget) if refilter else filtered,
            refilter,
            filtered,
        )

    def fingerprint(self) -> Tuple[object, ...]:
        return self.chunks, self.size, self.sha256, self.refilter

    def matches_source(self, parsed: PngData) -> bool:
        return (
            self.chunks == tuple(c for c in parsed.chunks if c[0] != b"IDAT")
            and self.size == len(parsed.raw)
            and self.filtered_sha256 == hashlib.sha256(parsed.raw).hexdigest()
        )


def png_refilterable(parsed: PngData) -> bool:
    ihdr = parsed.chunks[0][1]
    return ihdr[8] == 8 and ihdr[12] == 0


def png_samples_digest(parsed: PngData, budget: Optional[Budget] = None) -> str:
    """Independently undo filters, hashing exact rows including invisible colors."""
    require(png_refilterable(parsed), "PNG refiltering requires static noninterlaced 8-bit samples")
    width, height, _, color, _, _, _ = struct.unpack(">IIBBBBB", parsed.chunks[0][1])
    step = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = width * step
    require(len(parsed.raw) == (stride + 1) * height, "PNG sample row bounds")
    if budget is not None:
        budget.memory(len(parsed.raw) + stride * 3)
        tool = _png_row_tool(budget)
        if tool is not None:
            return _native_png_samples_digest(parsed, tool, budget)
    previous = bytearray(stride)
    digest = hashlib.sha256()
    position = 0
    palette = next((len(v) // 3 for k, v in parsed.chunks if k == b"PLTE"), 0)
    for _ in range(height):
        if budget is not None:
            budget.check()
        filtering = parsed.raw[position]
        require(filtering <= 4, "PNG filter type")
        row = bytearray(parsed.raw[position + 1:position + 1 + stride])
        if filtering == 1:
            for i in range(step, stride):
                row[i] = (row[i] + row[i - step]) & 255
        elif filtering == 2:
            row = bytearray((value + previous[i]) & 255 for i, value in enumerate(row))
        elif filtering in (3, 4):
            for i in range(stride):
                left = row[i - step] if i >= step else 0
                up = previous[i]
                if filtering == 3:
                    predictor = (left + up) // 2
                else:
                    upper_left = previous[i - step] if i >= step else 0
                    pa, pb = abs(up - upper_left), abs(left - upper_left)
                    pc = abs(left + up - 2 * upper_left)
                    predictor = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
                row[i] = (row[i] + predictor) & 255
        if color == 3:
            require(bool(palette) and max(row) < palette, "PNG palette sample outside table")
        digest.update(row)
        previous = row
        position += stride + 1
    return digest.hexdigest()


def _png_row_tool(budget: Budget) -> Optional[str]:
    """One capability probe per operation; old helpers keep the Python verifier."""
    from .commands import _cancelable_run
    from .format_support import current_options

    if hasattr(budget, '_png_row_tool'):
        cached = getattr(budget, '_png_row_tool')
        return cached if isinstance(cached, str) else None
    tool = current_options().get('ole_writer')
    qualified = None
    if isinstance(tool, str):
        try:
            result = _cancelable_run(
                [tool, '--capabilities'], capture_output=True,
                timeout=budget.remaining()['seconds'],
            )
        except OSError:
            setattr(budget, '_png_row_tool', None)
            return None
        except subprocess.TimeoutExpired as exc:
            raise FormatLimit('PNG row decoder deadline exceeded') from exc
        budget.check()
        if not result.returncode and b'png-unfilter-v1' in result.stdout.split():
            qualified = tool
    setattr(budget, '_png_row_tool', qualified)
    return qualified


def _native_png_samples_digest(parsed: PngData, tool: str, budget: Budget) -> str:
    from .commands import _cancelable_run
    from .format_support import current_options, tool_environment

    width, height, _, color, _, _, _ = struct.unpack('>IIBBBBB', parsed.chunks[0][1])
    palette = next((len(v) // 3 for k, v in parsed.chunks if k == b'PLTE'), 0) if color == 3 else 0
    size = len(parsed.raw) - height
    with tempfile.TemporaryDirectory(
        prefix='filerepack-ole-samples-', dir=current_options().get('_scratch_directory')
    ) as scratch:
        budget.own(scratch)
        source, output = os.path.join(scratch, 'filtered'), os.path.join(scratch, 'samples')
        write_bytes(source, parsed.raw, budget)
        with open(output, 'xb'):
            pass
        try:
            result = _cancelable_run(
                [tool, '--png-unfilter-v1', str(width), str(height), str(color), str(palette),
                 source, output], capture_output=True,
                timeout=budget.remaining()['seconds'], env=tool_environment(),
            )
        except subprocess.TimeoutExpired as exc:
            raise FormatLimit('PNG row decoder deadline exceeded') from exc
        budget.check()
        require(result.returncode == 0, 'native PNG row verification failed')
        require(os.path.getsize(output) == size, 'native PNG sample output bounds')
        budget.consume(written=size)
        digest, consumed = hashlib.sha256(), 0
        with open(output, 'rb') as samples:
            for block in iter(lambda: samples.read(65536), b''):
                budget.check()
                consumed += len(block)
                require(consumed <= size, 'native PNG sample output grew')
                digest.update(block)
        require(consumed == size, 'native PNG sample output truncated')
        return digest.hexdigest()


def _png_rows(ihdr: bytes) -> Tuple[int, int, List[Tuple[int, int]]]:
    require(len(ihdr) == 13, "PNG IHDR length")
    width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    valid = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
    require(
        width > 0
        and height > 0
        and depth in valid.get(color, set())
        and compression == filtering == 0
        and interlace in (0, 1),
        "PNG IHDR layout",
    )
    samples = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = (
        [(0, 0, 1, 1)]
        if not interlace
        else [
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        ]
    )
    rows = []
    for x, y, sx, sy in passes:
        w, h = max(0, (width - x + sx - 1) // sx), max(0, (height - y + sy - 1) // sy)
        if w and h:
            rows.append(((w * samples * depth + 7) // 8, h))
    return depth, color, rows


def png_sample_bytes(data: bytes) -> int:
    """Bounded preflight for deterministic selection; selected images are fully parsed."""
    require(
        data.startswith(PNG) and 33 <= len(data) <= LIMIT and data[8:16] == b"\0\0\0\rIHDR",
        "PNG preflight header",
    )
    require(
        zlib.crc32(data[12:29]) & 0xFFFFFFFF == struct.unpack_from(">I", data, 29)[0],
        "PNG IHDR CRC",
    )
    _, _, rows = _png_rows(data[16:29])
    size = sum((width + 1) * height for width, height in rows)
    require(size <= LIMIT, "PNG filtered samples exceed 16 MiB")
    return size


def png_data(data: bytes, budget: Budget) -> PngData:
    require(data.startswith(PNG) and len(data) <= LIMIT, "PNG signature/size")
    position, chunks, compressed = 8, [], bytearray()
    seen_idat, closed_idat = False, False
    while position < len(data):
        budget.consume(nodes=1)
        require(position + 12 <= len(data), "truncated PNG chunk")
        size = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        end = position + 12 + size
        require(
            end <= len(data)
            and all(65 <= c <= 90 or 97 <= c <= 122 for c in kind)
            and not kind[2] & 32,
            "PNG chunk bounds/type",
        )
        body = data[position + 8 : end - 4]
        require(
            zlib.crc32(kind + body) & 0xFFFFFFFF == struct.unpack_from(">I", data, end - 4)[0],
            "PNG chunk CRC",
        )
        require(
            kind in KNOWN_PNG or bool(kind[0] & 32 and kind[3] & 32),
            "unqualified critical/unsafe PNG chunk",
        )
        require(
            kind not in (b"acTL", b"fcTL", b"fdAT", b"dSIG"),
            "animated/signed PNG is outside the profile",
        )
        if kind == b"IDAT":
            require(not closed_idat, "noncontiguous PNG IDAT")
            compressed.extend(body)
            seen_idat = True
        elif seen_idat:
            closed_idat = True
        chunks.append((kind, body))
        position = end
        if kind == b"IEND":
            require(not body and position == len(data), "PNG IEND/trailing bytes")
            break
    require(
        bool(chunks)
        and chunks[0][0] == b"IHDR"
        and len(chunks[0][1]) == 13
        and chunks[-1][0] == b"IEND"
        and seen_idat,
        "PNG mandatory chunks",
    )
    require(sum(kind == b"IHDR" for kind, _ in chunks) == 1, "duplicate PNG IHDR")
    depth, color, rows = _png_rows(chunks[0][1])
    palettes = [(i, body) for i, (kind, body) in enumerate(chunks) if kind == b"PLTE"]
    first_idat = next(i for i, (kind, _) in enumerate(chunks) if kind == b"IDAT")
    require(len(palettes) <= 1 and (color != 3 or bool(palettes)), "PNG palette inventory")
    if palettes:
        index, palette = palettes[0]
        require(
            color in (2, 3, 6)
            and index < first_idat
            and 0 < len(palette) <= 768
            and len(palette) % 3 == 0
            and (color != 3 or len(palette) // 3 <= 2**depth),
            "PNG palette bounds/order",
        )
    transparency = [(i, body) for i, (kind, body) in enumerate(chunks) if kind == b"tRNS"]
    require(len(transparency) <= 1, "duplicate PNG transparency")
    if transparency:
        index, alpha = transparency[0]
        require(
            index < first_idat
            and color in (0, 2, 3)
            and (
                len(alpha) == {0: 2, 2: 6}.get(color)
                if color != 3
                else palettes[0][0] < index and 0 < len(alpha) <= len(palettes[0][1]) // 3
            ),
            "PNG transparency bounds/order",
        )
    expected = sum((size + 1) * count for size, count in rows)
    require(expected <= LIMIT, "PNG filtered samples exceed 16 MiB")
    raw = inflate(bytes(compressed), budget, maximum=expected)
    require(len(raw) == expected, "PNG filtered scanline size")
    position = 0
    for size, count in rows:
        for _ in range(count):
            budget.check()
            require(raw[position] <= 4, "PNG filter type")
            position += size + 1
    return PngData(tuple(chunks), raw)


def optimize_png(
    data: bytes, parsed: PngData, budget: Budget, stronger: Any = None, ultra: bool = False
) -> Tuple[bytes, str]:
    best, encoder = data, "original"
    trials = [("png-zlib9", zlib.compress(parsed.raw, 9))]
    if stronger is not None:
        for iterations, cutoff in ((15, 1024 * 1024), (50, 2 * 1024 * 1024)):
            if (iterations == 15 or ultra) and len(parsed.raw) <= cutoff:
                budget.check()
                trials.append(
                    (
                        "png-zopfli" + str(iterations),
                        bytes(stronger(parsed.raw, numiterations=iterations)),
                    )
                )
    for name, encoded in trials:
        budget.check()
        trial = parsed.rebuild(encoded)
        require(
            png_data(trial, budget).fingerprint() == parsed.fingerprint(),
            "PNG encoder changed samples or metadata",
        )
        if len(trial) < len(best):
            best, encoder = trial, name
    return best, encoder


def qualified_png_tool(budget: Budget) -> Tuple[Optional[str], str]:
    from .commands import _cancelable_run
    from .tools import resolve_tool

    tool = resolve_tool("oxipng")
    if tool is None:
        return None, "OfficeArt PNG refiltering: oxipng unavailable; exact-filtered codecs retained"
    try:
        result = _cancelable_run(
            [tool, "--version"], capture_output=True, timeout=budget.remaining()["seconds"]
        )
    except OSError:
        return None, "OfficeArt PNG refiltering: oxipng probe failed; prior codecs retained"
    except subprocess.TimeoutExpired as exc:
        raise FormatLimit("OfficeArt PNG encoder deadline exceeded") from exc
    budget.check()
    if result.returncode or result.stdout.strip() != b"oxipng 10.2.0":
        return None, "OfficeArt PNG refiltering requires qualified oxipng 10.2.0"
    return tool, ""


def _png_refilter_trial(
    data: bytes, parsed: PngData, identity: PngIdentity, tool: str, budget: Budget,
    skips: Optional[List[str]] = None,
) -> Optional[bytes]:
    from .commands import _cancelable_run
    from .format_support import current_options, tool_environment, tool_threads

    directory = current_options().get("_scratch_directory")
    available = budget.remaining()['seconds'] - PNG_FINAL_SECONDS
    if available <= 0:
        if skips is not None and 'OfficeArt PNG refiltering time allowance exhausted' not in skips:
            skips.append('OfficeArt PNG refiltering time allowance exhausted')
        return None
    with tempfile.TemporaryDirectory(prefix="filerepack-ole-png-", dir=directory) as scratch:
        budget.own(scratch)
        source, output = os.path.join(scratch, "source.png"), os.path.join(scratch, "out.png")
        write_bytes(source, data, budget)
        try:
            result = _cancelable_run(
                [tool, "-o", "4", "--filters", "0,1,6,7", "--zc", "9", "--nb", "--nc", "--np",
                 "--interlace", "keep",
                 "--threads", str(tool_threads()), "-q", "--out", output, source],
                capture_output=True, timeout=min(PNG_REFILTER_TRIAL_SECONDS, available),
                env=tool_environment(),
            )
        except OSError:
            return None
        except subprocess.TimeoutExpired:
            # A local optional-trial ceiling is distinct from the root deadline.
            # Account any partial output and preserve earlier verified choices.
            budget.check()
            if os.path.isfile(output):
                budget.consume(written=os.path.getsize(output))
            reason = 'OfficeArt PNG refiltering trial time limit reached; prior codecs retained'
            if skips is not None and reason not in skips:
                skips.append(reason)
            return None
        budget.check()
        if result.returncode or not os.path.isfile(output):
            return None
        size = os.path.getsize(output)
        budget.consume(written=size)
        if not 0 < size < len(data) or size > LIMIT:
            return None
        with open(output, "rb") as candidate:
            raw = candidate.read(size + 1)
        require(len(raw) == size, "PNG encoder output length changed")
        trial = png_data(raw, budget)
        require(trial.chunks[0] == parsed.chunks[0], "PNG encoder changed IHDR")
        # Reuse only IDAT: even a lossless ICC re-encoding is outside this contract.
        idat = b"".join(v for k, v in trial.chunks if k == b"IDAT")
        rebuilt = parsed.rebuild(idat)
        restored = PngData(parsed.chunks, trial.raw)
        require(
            PngIdentity.from_data(restored, refilter=True, budget=budget).fingerprint()
            == identity.fingerprint(),
            "PNG encoder changed exact unfiltered samples",
        )
        return rebuilt


def optimize_refiltered_png(
    data: bytes, parsed: PngData, identity: PngIdentity, budget: Budget,
    stronger: Any = None, ultra: bool = False, tool: Optional[str] = None,
    skips: Optional[List[str]] = None,
) -> Tuple[bytes, str]:
    """Retain all encodings; independently verify only candidates being accepted."""
    trials = [(data, "original"), (parsed.rebuild(zlib.compress(parsed.raw, 9)), "png-zlib9")]
    if stronger is not None:
        for iterations, cutoff in ((15, 1024 * 1024), (50, 2 * 1024 * 1024)):
            if (iterations == 15 or ultra) and len(parsed.raw) <= cutoff:
                budget.check()
                encoded = bytes(stronger(parsed.raw, numiterations=iterations))
                trials.append((parsed.rebuild(encoded), "png-zopfli" + str(iterations)))
    verified = None
    if tool is not None:
        try:
            verified = _png_refilter_trial(data, parsed, identity, tool, budget, skips)
        except (UnsupportedFormat, zlib.error, OSError) as exc:
            reason = "OfficeArt PNG refiltering trial rejected: " + str(exc)
            if skips is not None and reason not in skips:
                skips.append(reason)
        if verified is not None:
            trials.append((verified, "png-oxipng10.2.0"))
        elif skips is not None:
            reason = "OfficeArt PNG refiltering trial declined; prior codecs retained"
            if reason not in skips:
                skips.append(reason)
    for candidate, encoder in sorted(trials, key=lambda item: len(item[0])):
        budget.check()
        if encoder == "original" or candidate is verified:
            return candidate, encoder
        try:
            equal = png_data(candidate, budget).fingerprint() == parsed.fingerprint()
        except (UnsupportedFormat, zlib.error):
            equal = False
        if equal:
            return candidate, encoder
    return data, "original"


class Bits:
    def __init__(self, data: bytes):
        self.data, self.position = data, 0

    def take(self, count: int) -> int:
        require(self.position + count <= len(self.data) * 8, "truncated JPEG entropy")
        value = 0
        for _ in range(count):
            value = (value << 1) | ((self.data[self.position // 8] >> (7 - self.position % 8)) & 1)
            self.position += 1
        return value

    def finish(self) -> None:
        remaining = len(self.data) * 8 - self.position
        require(
            remaining < 8 and self.take(remaining) == (1 << remaining) - 1,
            "JPEG unused entropy/padding",
        )


def huffman(data: bytes) -> Dict[Tuple[int, int], int]:
    require(len(data) >= 16 and sum(data[:16]) == len(data) - 16, "JPEG Huffman bounds")
    table, code, position = {}, 0, 16
    for length, count in enumerate(data[:16], 1):
        require(code + count < 1 << length, "oversubscribed/all-one JPEG Huffman code")
        for value in range(code, code + count):
            table[(length, value)] = data[position]
            position += 1
        code = (code + count) << 1
    require(bool(table), "empty JPEG Huffman table")
    return table


def symbol(bits: Bits, table: Dict[Tuple[int, int], int]) -> int:
    code = 0
    for length in range(1, 17):
        code = (code << 1) | bits.take(1)
        if (length, code) in table:
            return table[(length, code)]
    raise UnsupportedFormat("OfficeArt raster: invalid JPEG Huffman code")


def signed(bits: Bits, size: int) -> int:
    value = bits.take(size)
    return value if not size or value >= 1 << (size - 1) else value - ((1 << size) - 1)


def entropy(data: bytes, start: int) -> Tuple[List[bytes], List[int]]:
    parts, restarts, current = [], [], bytearray()
    position = start
    while position < len(data):
        value = data[position]
        position += 1
        if value != 255:
            current.append(value)
            continue
        require(position < len(data), "truncated JPEG marker")
        marker = data[position]
        position += 1
        if marker == 0:
            current.append(255)
        elif 0xD0 <= marker <= 0xD7:
            parts.append(bytes(current))
            current.clear()
            restarts.append(marker)
        else:
            require(
                marker == 0xD9 and position == len(data),
                "multiple JPEG scans/markers or trailing bytes are unqualified",
            )
            parts.append(bytes(current))
            return parts, restarts
    raise UnsupportedFormat("OfficeArt raster: missing JPEG EOI")


@dataclass(frozen=True)
class JpegData:
    identity: Tuple[object, ...]
    restart: int

    def fingerprint(self) -> Tuple[object, ...]:
        return self.identity


def jpeg_data(data: bytes, budget: Budget) -> JpegData:  # noqa: C901
    # Keep the marker grammar and its table inventory together for auditing.
    require(data[:2] == b"\xff\xd8" and len(data) <= LIMIT, "JPEG signature/size")
    position, frame, tables, quant, metadata = 2, b"", {}, {}, []
    restart, seen_restart = 0, False
    while position < len(data):
        budget.consume(nodes=1)
        require(data[position : position + 1] == b"\xff", "JPEG marker prefix")
        while position < len(data) and data[position] == 255:
            position += 1
        require(position + 3 <= len(data), "truncated JPEG segment")
        marker = data[position]
        size = struct.unpack_from(">H", data, position + 1)[0]
        end = position + 1 + size
        require(size >= 2 and end <= len(data), "JPEG segment bounds")
        body = data[position + 3 : end]
        position = end
        if 0xE0 <= marker <= 0xEF or marker == 0xFE:
            require(
                marker != 0xEB and not body.startswith((b"JUMBF", b"JPSEC", b"C2PA")),
                "signed JPEG metadata is unqualified",
            )
            metadata.append((marker, body))
        elif marker == 0xC0:
            require(
                not frame
                and len(body) >= 9
                and body[0] == 8
                and body[5] in (1, 3)
                and len(body) == 6 + body[5] * 3,
                "JPEG frame precision/component layout",
            )
            frame = body
        elif marker == 0xDB:
            offset = 0
            while offset < len(body):
                key = body[offset]
                offset += 1
                require(
                    key >> 4 == 0 and key < 4 and offset + 64 <= len(body) and key not in quant,
                    "JPEG quantization table layout",
                )
                values = body[offset : offset + 64]
                require(all(values), "zero JPEG quantizer")
                quant[key] = values
                offset += 64
        elif marker == 0xC4:
            offset = 0
            while offset < len(body):
                require(offset + 17 <= len(body), "truncated JPEG Huffman table")
                key = body[offset]
                length = 16 + sum(body[offset + 1 : offset + 17])
                require(
                    key >> 4 in (0, 1)
                    and key & 15 < 4
                    and key not in tables
                    and offset + 1 + length <= len(body),
                    "JPEG Huffman table layout",
                )
                tables[key] = huffman(body[offset + 1 : offset + 1 + length])
                offset += 1 + length
        elif marker == 0xDD:
            require(len(body) == 2 and not seen_restart, "JPEG restart interval layout")
            restart, seen_restart = struct.unpack(">H", body)[0], True
        elif marker == 0xDA:
            require(
                bool(frame)
                and bool(body)
                and body[0] == frame[5]
                and len(body) == 1 + 2 * body[0] + 3
                and body[-3:] == b"\x00\x3f\x00",
                "only complete sequential JPEG scans are qualified",
            )
            break
        else:
            require(False, "unqualified JPEG marker: " + hex(marker))
    else:
        raise UnsupportedFormat("OfficeArt raster: missing JPEG scan")
    height, width = struct.unpack_from(">HH", frame, 1)
    require(width > 0 and height > 0, "JPEG dimensions")
    components = {
        frame[6 + i * 3]: (frame[7 + i * 3] >> 4, frame[7 + i * 3] & 15, frame[8 + i * 3])
        for i in range(frame[5])
    }
    require(
        len(components) == frame[5]
        and all(1 <= h <= 4 and 1 <= v <= 4 and q in quant for h, v, q in components.values()),
        "JPEG component/sampling/quantizer identity",
    )
    scan = [(body[1 + i * 2], body[2 + i * 2] >> 4, body[2 + i * 2] & 15) for i in range(body[0])]
    require(
        {c for c, _, _ in scan} == set(components)
        and all(dc in tables and 16 + ac in tables for _, dc, ac in scan),
        "JPEG scan component/Huffman identity",
    )
    # Adobe transform 2 is YCCK; four-component/CMYK frames are already excluded.
    require(
        all(
            not (
                marker == 0xEE
                and payload.startswith(b"Adobe")
                and len(payload) >= 12
                and payload[11] == 2
            )
            for marker, payload in metadata
        ),
        "JPEG YCCK color interpretation",
    )
    mh = max(h for h, _, _ in components.values())
    mv = max(v for _, v, _ in components.values())
    require(sum(h * v for h, v, _ in components.values()) <= 10, "JPEG MCU block limit")
    # Noninterleaved grayscale scans contain one block per MCU regardless of factors.
    mcus = math.ceil(width / (8 * mh)) * math.ceil(height / (8 * mv))
    if len(components) == 1:
        require(mh == mv == 1, "unqualified grayscale JPEG sampling")
    block_count = mcus * sum(h * v for h, v, _ in components.values())
    require(block_count * 128 <= LIMIT, "JPEG coefficients exceed 16 MiB")
    budget.memory(block_count * 64 * 40)
    budget.consume(decoded=block_count * 128)
    segments, markers = entropy(data, position)
    expected_restarts = (mcus - 1) // restart if restart else 0
    require(
        len(markers) == expected_restarts
        and all(marker == 0xD0 + index % 8 for index, marker in enumerate(markers)),
        "JPEG restart marker count/order",
    )
    bits, segment, predictors = Bits(segments[0]), 0, dict.fromkeys(components, 0)
    coefficients: Dict[int, List[Tuple[int, ...]]] = {c: [] for c in components}
    for mcu in range(mcus):
        budget.check()
        if restart and mcu and mcu % restart == 0:
            bits.finish()
            segment += 1
            bits = Bits(segments[segment])
            predictors = dict.fromkeys(components, 0)
        for component, dc, ac in scan:
            h, v, _ = components[component]
            for _ in range(h * v):
                size = symbol(bits, tables[dc])
                require(size <= 11, "JPEG DC magnitude")
                predictors[component] += signed(bits, size)
                block = [predictors[component]] + [0] * 63
                k = 1
                while k < 64:
                    code = symbol(bits, tables[16 + ac])
                    if code == 0:
                        break
                    run, size = code >> 4, code & 15
                    if size == 0:
                        require(run == 15 and k + 16 <= 64, "JPEG zero run")
                        k += 16
                        continue
                    k += run
                    require(size <= 10 and k < 64, "JPEG AC magnitude/run")
                    block[k] = signed(bits, size)
                    k += 1
                coefficients[component].append(tuple(block))
    bits.finish()
    identity = (
        frame,
        tuple(sorted(quant.items())),
        tuple(metadata),
        tuple((c, tuple(values)) for c, values in sorted(coefficients.items())),
    )
    return JpegData(identity, restart)


def optimize_jpeg(data: bytes, parsed: JpegData, budget: Budget) -> Tuple[bytes, str]:
    from .tools import resolve_tool

    tool = resolve_tool("jpegtran")
    if tool is None:
        return data, "original: jpegtran unavailable"
    version = subprocess.run(
        [tool, "-version"], capture_output=True, timeout=budget.remaining()["seconds"]
    )
    budget.check()
    if version.returncode or b"libjpeg-turbo version 3.2.0 " not in version.stdout + version.stderr:
        return data, "original: unqualified jpegtran version (requires libjpeg-turbo 3.2.0)"
    with tempfile.TemporaryDirectory(prefix="filerepack-jpeg-") as scratch:
        source, output = os.path.join(scratch, "source.jpg"), os.path.join(scratch, "out.jpg")
        write_bytes(source, data, budget)
        args = [tool, "-copy", "all", "-optimize"]
        if parsed.restart:
            args += ["-restart", str(parsed.restart) + "B"]
        args += ["-outfile", output, source]
        result = subprocess.run(args, capture_output=True, timeout=budget.remaining()["seconds"])
        budget.check()
        require(len(result.stdout) + len(result.stderr) <= 65536, "JPEG encoder diagnostics limit")
        if result.returncode or not os.path.isfile(output):
            return data, "original: jpegtran declined profile"
        size = os.path.getsize(output)
        budget.consume(written=size)
        if size >= len(data) or size > LIMIT:
            return data, "original"
        with open(output, "rb") as file:
            trial = file.read(LIMIT + 1)
        try:
            equal = jpeg_data(trial, budget).fingerprint() == parsed.fingerprint()
        except UnsupportedFormat:
            equal = False
        return (trial, "jpegtran") if equal else (data, "original: JPEG identity differs")
