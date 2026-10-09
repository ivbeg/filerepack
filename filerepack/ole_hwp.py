"""HWP 5 exact raw-DEFLATE stream contracts; no semantic reserialization."""

import hashlib
import struct
import zlib
from dataclasses import dataclass, replace
from typing import Dict, List, Tuple

from .format_support import Budget, FormatLimit, inflate
from .ole_verify import CompoundFile

Path = Tuple[str, ...]
LIMIT = 16 * 1024 * 1024
TOTAL = 64 * 1024 * 1024
ZOPFLI_CUTOFF = 1024 * 1024
# Empty event-handler template from the pinned pyhwp 5.0.1.7 corpus. Other script
# bodies, including different encodings of this template, remain unqualified.
EMPTY_SCRIPTS = {
    "JScriptVersion": "adf376246e26101841c763bfb6052a4af4673461e021742bc8fd13ecb62be36f",
    "DefaultJScript": "f9a93cbdbb3a4f4d419a4df9289c8382f9cb12a90ea560a3884194d4f9dd95dc",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("HWP: " + reason)


def profile(compound: CompoundFile) -> int:
    head = compound.streams.get(("FileHeader",), b"")
    require(
        len(head) == 256 and head[:32] == b"HWP Document File".ljust(32, b"\0"),
        "missing/invalid FileHeader",
    )
    version, flags, license_flags, encryption = struct.unpack_from("<4I", head, 32)
    require(0x05000100 <= version <= 0x05000302, "unqualified HWP 5 version")
    require(
        not flags & ~0x3FFFF and not flags & 0x2796,
        "encrypted/distribution/DRM/signed/private HWP document",
    )
    require(
        encryption == 0 and not license_flags & ~7 and not any(head[49:]),
        "unqualified encryption/reserved header fields",
    )
    scripts = {
        p[1]: hashlib.sha256(v).hexdigest()
        for p, v in compound.streams.items()
        if len(p) == 2 and p[0] == "Scripts"
    }
    require(not scripts or scripts == EMPTY_SCRIPTS, "unqualified script-bearing document")
    require(not flags & 8, "script activation flag is not qualified")
    require(
        ("DocInfo",) in compound.streams and ("BodyText", "Section0") in compound.streams,
        "missing DocInfo/BodyText",
    )
    for entry in compound.entries:
        require(
            not any(
                part.lower().startswith(("drm", "signature", "cert", "viewtext"))
                for part in entry.path
            ),
            "protected HWP storage",
        )
    return int(flags)


def records(data: bytes, budget: Budget) -> List[Tuple[int, int, bytes]]:
    result, at, previous = [], 0, 0
    while at < len(data):
        budget.consume(nodes=1)
        require(at + 4 <= len(data), "truncated record header")
        value = struct.unpack_from("<I", data, at)[0]
        at += 4
        tag, level, size = value & 1023, (value >> 10) & 1023, value >> 20
        if size == 4095:
            require(at + 4 <= len(data), "truncated extended record size")
            size = struct.unpack_from("<I", data, at)[0]
            at += 4
        require(
            16 <= tag <= 127 and level <= previous + 1 and size <= len(data) - at,
            "record type/level/bounds",
        )
        result.append((tag, level, data[at : at + size]))
        at += size
        previous = level
    require(bool(result), "empty record stream")
    return result


@dataclass
class HwpLayout:
    compound: CompoundFile
    decoded: Dict[Path, bytes]
    version: int
    trailers: Dict[Path, bytes]

    def fingerprint(self) -> Tuple[object, ...]:
        entries = tuple(
            replace(e, size=0, sha256="") if e.path in self.decoded else e
            for e in self.compound.manifest.entries
        )
        return (
            entries,
            tuple(sorted(self.trailers.items())),
            tuple(sorted((p, hashlib.sha256(v).digest(), len(v)) for p, v in self.decoded.items())),
        )

    def reencode(self, budget: Budget) -> Tuple[Dict[Path, bytes], Dict[str, object]]:
        from .ole_officeart import _zopfli

        stronger = _zopfli()
        replacements, count, encoders = {}, 0, []
        for path, raw in self.decoded.items():
            budget.check()
            encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
            trial = encoder.compress(raw) + encoder.flush() + self.trailers[path]
            original = self.compound.streams[path]
            require(
                decode_stream(trial, budget) == (raw, self.trailers[path]),
                "zlib encoder changed decoded stream/trailer",
            )
            payload, selected = original, "original"
            if len(trial) < len(payload):
                payload, selected = trial, "raw-deflate-zlib9"
            if stronger is not None and len(raw) <= ZOPFLI_CUTOFF:
                budget.check()
                framed = bytes(stronger(raw, numiterations=15))
                budget.check()
                trial = qualified_zopfli_raw(framed, raw, budget) + self.trailers[path]
                if len(trial) < len(payload):
                    payload, selected = trial, "raw-deflate-zopfli15"
            require(
                decode_stream(payload, budget) == (raw, self.trailers[path]),
                "encoder changed decoded stream/trailer",
            )
            replacements[path] = payload
            count += payload != original
            encoders.append(selected)
        return replacements, {
            "hwp_version": self.version,
            "selected_streams": len(replacements),
            "recompressed_streams": count,
            "encoder": "raw-deflate-v1",
            "encoders": encoders,
            "hwp_encoder_version": 1,
            "zopfli_version": "0.4.3" if stronger is not None else None,
            "zopfli_cutoff_bytes": ZOPFLI_CUTOFF,
            "zopfli_skipped_streams": sum(
                len(raw) > ZOPFLI_CUTOFF for raw in self.decoded.values()
            ),
            "effort_note": "qualified HWP Zopfli15 trials available"
            if stronger is not None
            else "Zopfli 0.4.3 unavailable; original/raw-zlib9 trials only",
            "stream_savings_bytes": sum(
                len(self.compound.streams[p]) - len(v) for p, v in replacements.items()
            ),
        }


def qualified_zopfli_raw(framed: bytes, raw: bytes, budget: Budget) -> bytes:
    """Qualify RFC1950 before extracting its RFC1951 body; never strip blindly.

    The pinned binding exports a zlib container, not a raw-DEFLATE interface.
    Require its exact dictionary-free 32K window header, checksum, termination
    and decoded identity, then independently verify the extracted raw frame.
    """
    require(
        len(framed) >= 8
        and framed[0] == 0x78
        and not framed[1] & 0x20
        and int.from_bytes(framed[:2], "big") % 31 == 0,
        "unqualified Zopfli zlib header/dictionary",
    )
    require(
        int.from_bytes(framed[-4:], "big") == zlib.adler32(raw) & 0xFFFFFFFF,
        "Zopfli zlib checksum differs",
    )
    try:
        require(inflate(framed, budget, maximum=len(raw)) == raw, "Zopfli changed decoded stream")
    except zlib.error as exc:
        raise ValueError("HWP: invalid Zopfli zlib frame") from exc
    payload = framed[2:-4]
    require(decode_stream(payload, budget) == (raw, b""), "Zopfli raw frame differs")
    return payload


def inspect_hwp(compound: CompoundFile, budget: Budget) -> HwpLayout:
    flags = profile(compound)
    require(bool(flags & 1), "uncompressed document retains its compression mode")
    decoded: Dict[Path, bytes] = {}
    trailers: Dict[Path, bytes] = {}
    total = 0

    def decode(path: Path, record_stream: bool = False) -> bytes:
        nonlocal total
        require(path in compound.streams, "missing resolved stream")
        require(len(decoded) < 64, "selected stream count limit")
        raw, trailer = decode_stream(compound.streams[path], budget)
        total += len(raw)
        if total > TOTAL:
            raise FormatLimit("HWP aggregate decoded stream limit exceeded")
        decoded[path] = raw
        trailers[path] = trailer
        if record_stream:
            records(raw, budget)
        return raw

    doc = records(decode(("DocInfo",)), budget)
    require(doc[0][0:2] == (16, 0) and len(doc[0][2]) == 26, "unqualified document properties")
    sections = struct.unpack_from("<H", doc[0][2])[0]
    require(
        0 < sections < 64
        and len(doc) > 1
        and doc[1][0:2] == (17, 0)
        and len(doc[1][2]) in (60, 64, 68, 72),
        "section/ID mapping bounds",
    )
    expected = {("BodyText", "Section" + str(i)) for i in range(sections)}
    actual = {
        e.path for e in compound.entries if e.path and e.path[0] == "BodyText" and len(e.path) > 1
    }
    require(expected == actual, "section inventory differs from DocInfo")
    for path in sorted(expected):
        raw = decode(path, True)
        require(records(raw, budget)[0][0] == 66, "section does not start with paragraph header")
    binaries = [body for tag, level, body in doc if tag == 18]
    require(len(binaries) == struct.unpack_from("<I", doc[1][2])[0], "BinData mapping count")
    targets = set()
    for body in binaries:
        require(len(body) >= 2, "truncated BinData flags")
        attr = struct.unpack_from("<H", body)[0]
        kind, policy = attr & 15, (attr >> 4) & 3
        require(
            kind in (0, 1, 2) and policy != 3 and not attr & ~0x073F,
            "unknown BinData type/compression/status",
        )
        if kind != 1:
            # Link and storage payloads are retained; their contracts are separate.
            continue
        require(len(body) >= 6, "truncated embedded BinData")
        ident, count = struct.unpack_from("<HH", body, 2)
        require(
            ident > 0 and len(body) == 6 + 2 * count and 0 < count <= 16,
            "BinData ID/extension bounds",
        )
        ext = body[6:].decode("utf-16le")
        require(ext.isascii() and ext.isalnum(), "unqualified BinData extension")
        path = ("BinData", "BIN" + format(ident, "04X") + "." + ext)
        require(path in compound.streams and path not in targets, "missing/aliased BinData target")
        targets.add(path)
        if policy == 1 or policy == 0 and flags & 1:
            decode(path)
    return HwpLayout(
        compound,
        decoded,
        struct.unpack_from("<I", compound.streams["FileHeader",], 32)[0],
        trailers,
    )


def decode_stream(data: bytes, budget: Budget) -> Tuple[bytes, bytes]:
    """Exact RFC1951, optionally followed by a verified CRC32/ISIZE trailer.

    The 5.0.1.7 real corpus uses the eight-byte gzip trailer without its header.
    Accept that qualified suffix only when both fields agree; retain it exactly.
    """
    maximum = min(LIMIT, budget.limits.memory // 8, budget.limits.decoded - budget.decoded)
    decoder = zlib.decompressobj(-15)
    try:
        raw = decoder.decompress(data, maximum + 1)
    except zlib.error as exc:
        raise ValueError("HWP: invalid raw-DEFLATE stream") from exc
    if len(raw) > maximum:
        raise FormatLimit("HWP decoded stream limit exceeded")
    require(decoder.eof and not decoder.unconsumed_tail, "incomplete raw-DEFLATE stream")
    suffix = decoder.unused_data
    require(
        not suffix or suffix == struct.pack("<II", zlib.crc32(raw) & 0xFFFFFFFF, len(raw)),
        "unqualified/trailing/concatenated stream data",
    )
    budget.consume(decoded=len(raw))
    return bytes(raw), suffix
