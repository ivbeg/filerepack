"""Bounded MS-ODRAW records and preserving metafile/raster codecs.

Hosts own discovery and relocation; this module never searches opaque streams.
Unselected BLIPs stay byte-identical. No image conversion or metadata stripping.
"""

import hashlib
import struct
import zlib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Callable, Dict, List, Optional, Tuple, Union, cast

from .format_support import Budget, FormatLimit, UnsupportedFormat, inflate
from .ole_raster import (
    JpegData,
    PngData,
    PngIdentity,
    jpeg_data,
    optimize_jpeg,
    optimize_png,
    optimize_refiltered_png,
    png_data,
    png_sample_bytes,
    qualified_png_tool,
)

MAX_PAYLOAD = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_OBJECTS = 64
METAFILES = {0xF01A: (0x3D4, 0x3D5), 0xF01B: (0x216, 0x217)}
CONTAINERS = {0xF000, 0xF001, 0xF004}
LEAVES = {0xF006: 0, 0xF00A: 2, 0xF00B: 3, 0xF010: 0, 0xF11E: 0}
BLIPS = {**METAFILES, 0xF01D: (0x46A, 0x46B), 0xF01E: (0x6E0, 0x6E1)}
# Default colors/protection and inline picture identity/name/flags. These carry
# no byte offsets into host streams. Other properties need their own audit.
PROPERTY_IDS = {0xBF, 0x104, 0x105, 0x106, 0x13F, 0x181, 0x1BF, 0x1C0, 0x1FF,
                0x380, 0x3BF}
# Word-only, immutable scalar flags and empty complex fill/line image defaults.
WORD_PROPERTY_IDS = {0x7F, 0x33F, 0x186, 0x1C5}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise UnsupportedFormat("OfficeArt: " + reason)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def header(flags: int, kind: int, body: bytes) -> bytes:
    require(len(body) <= 0xFFFFFFFF, "record length overflow")
    return struct.pack("<HHI", flags, kind, len(body)) + body


def leaf_bounds(
    flags: int, kind: int, body: bytes, *, word_properties: bool = False
) -> None:
    if kind == 0xF006:
        require(
            flags == 0
            and len(body) >= 16
            and (len(body) - 16) % 8 == 0
            and struct.unpack_from("<I", body, 4)[0] == 1 + (len(body) - 16) // 8,
            "FDGG cluster bounds",
        )
    elif kind in (0xF00A, 0xF010, 0xF11E):
        require(
            len(body) == {0xF00A: 8, 0xF010: 4, 0xF11E: 16}[kind], "fixed OfficeArt leaf length"
        )
        require(kind != 0xF11E or flags == 0x40, "split menu color instance")
    elif kind == 0xF00B:
        count, previous = flags >> 4, -1
        position = count * 6
        require(0 < count and position <= len(body), "FOPT property table bounds")
        allowed = PROPERTY_IDS | (WORD_PROPERTY_IDS if word_properties else set())
        for index in range(count):
            code, value = struct.unpack_from("<HI", body, index * 6)
            identity = code & 0x3FFF
            require(identity in allowed, "unsupported FOPT property: " + hex(identity))
            require(
                identity > previous,
                "duplicate/out-of-order FOPT property: " + hex(identity),
            )
            previous = identity
            if identity in (0x7F, 0x33F):
                require(not code & 0xC000, "Word scalar drawing property flags")
            if identity in (0x186, 0x1C5):
                require(code & 0x8000 and value == 0, "nonempty Word fill/line image default")
                continue  # Zero complex length owns no bytes and no BStore index.
            if code & 0x8000:
                require(
                    identity in (0x105, 0x380)
                    and value > 0
                    and value % 2 == 0
                    and value <= len(body) - position,
                    "complex picture name bounds",
                )
                require(
                    body[position + value - 2 : position + value] == b"\0\0",
                    "complex picture name terminator",
                )
                position += value
        require(position == len(body), "unaccounted FOPT complex bytes")
    elif kind == 0xF122:
        require(
            word_properties and flags == 0x13 and len(body) == 6
            and struct.unpack_from("<H", body)[0] == 0x3AA,
            "unqualified Word tertiary drawing property",
        )


@dataclass(frozen=True)
class Metafile:
    prefix: bytes  # UIDs and complete 34-byte metafile header.
    raw: bytes
    encoded: bytes

    def fingerprint(self) -> Tuple[object, ...]:
        prefix = bytearray(self.prefix)
        struct.pack_into("<I", prefix, len(prefix) - 6, 0)  # cbSave only.
        return bytes(prefix), len(self.raw), digest(self.raw)


@dataclass(frozen=True)
class Raster:
    prefix: bytes
    encoded: Union[bytes, memoryview]
    parsed: Union[PngData, JpegData, PngIdentity]

    def fingerprint(self) -> Tuple[object, ...]:
        return self.prefix, self.parsed.fingerprint()


@dataclass(frozen=True)
class Record:
    flags: int
    kind: int
    body: bytes
    children: Tuple["Record", ...] = ()
    metafile: Optional[Metafile] = None
    raster: Optional[Raster] = None

    def original(self) -> bytes:
        return header(self.flags, self.kind, self.body)

    def fingerprint(self) -> Tuple[object, ...]:
        if self.metafile is not None:
            body: object = self.metafile.fingerprint()
        elif self.raster is not None:
            body = self.raster.fingerprint()
        elif self.children:
            prefix = (
                bytearray(self.body[: 36 + self.body[33]]) if self.kind == 0xF007 else bytearray()
            )
            if prefix:
                struct.pack_into("<I", prefix, 20, 0)  # Embedded BLIP size only.
            body = bytes(prefix), tuple(child.fingerprint() for child in self.children)
        else:
            body = self.body
        return self.flags, self.kind, body

    def encode(self, payloads: Dict[int, bytes]) -> bytes:
        if self.metafile is not None:
            encoded = payloads.get(id(self), self.metafile.encoded)
            prefix = bytearray(self.metafile.prefix)
            struct.pack_into("<I", prefix, len(prefix) - 6, len(encoded))
            body = bytes(prefix) + encoded
        elif self.raster is not None:
            body = self.raster.prefix + bytes(payloads.get(id(self), self.raster.encoded))
        elif self.children:
            body = b"".join(child.encode(payloads) for child in self.children)
            if self.kind == 0xF007:
                prefix = bytearray(self.body[: 36 + self.body[33]])
                struct.pack_into("<I", prefix, 20, len(body))
                body = bytes(prefix) + body
        else:
            body = self.body
        return header(self.flags, self.kind, body)


class Parser:
    def __init__(
        self, budget: Budget, raster: bool = True, *, bounded_png: bool = False,
        word_properties: bool = False,
    ):
        self.budget = budget
        self.metafiles: List[Record] = []
        self.rasters: List[Record] = []
        self.raster_skips: List[str] = []
        self.raster_enabled = raster
        self.decoded = 0
        self.bounded_png = bounded_png
        self.word_properties = word_properties
        # Five full original-sample passes cover source inspection, lazy source,
        # optional refilter output, a winning exact-filtered trial and final host.
        self.png_allowance = budget.limits.decoded // 5 if bounded_png else MAX_TOTAL
        if word_properties:
            self.png_allowance = min(self.png_allowance, MAX_TOTAL)
        self.retain_jpeg = False

    def sequence(
        self, data: bytes, depth: int = 0, *, owner: Optional[int] = None
    ) -> Tuple[Record, ...]:
        require(depth <= 32, "record depth limit")
        records = []
        offset = 0
        while offset < len(data):
            require(offset + 8 <= len(data), "truncated record header")
            flags, kind, size = struct.unpack_from("<HHI", data, offset)
            end = offset + 8 + size
            require(end <= len(data), "truncated record body")
            self.budget.consume(nodes=1)
            body = data[offset + 8 : end]
            if kind == 0xF122 and self.word_properties:
                require(owner == 0xF004, "Word tertiary drawing property outside a shape")
            records.append(self.one(flags, kind, body, depth))
            offset = end
        return tuple(records)

    def one(self, flags: int, kind: int, body: bytes, depth: int) -> Record:
        if kind in METAFILES:
            return self.metafile(flags, kind, body)
        if kind == 0xF007:
            return self.fbse(flags, body, depth)
        if kind in CONTAINERS:
            require(
                flags & 15 == 15 and (kind == 0xF001 or flags == 15), "container version/instance"
            )
            children = self.sequence(body, depth + 1, owner=kind)
            require(bool(children), "empty OfficeArt container")
            if kind == 0xF001:
                require(
                    len(children) == flags >> 4 and all(c.kind == 0xF007 for c in children),
                    "BStore count/type differs",
                )
            return Record(flags, kind, body, children)
        if kind in BLIPS:
            require(flags & 15 == 0 and flags >> 4 in BLIPS[kind], "raster BLIP version/instance")
            uid_size = 16 * (1 + (flags >> 4 == BLIPS[kind][1]))
            require(len(body) > uid_size, "truncated opaque raster BLIP")
            if self.raster_enabled:
                try:
                    require(body[uid_size] == 255, "unqualified raster resource tag")
                    encoded = body[uid_size + 1 :]
                    if self.retain_jpeg and kind == 0xF01D:
                        self.raster_skips.append("PPT bounded PNG profile retains JPEG bytes")
                        return Record(flags, kind, body)
                    if self.bounded_png and kind == 0xF01E:
                        samples = png_sample_bytes(encoded)
                        if samples > self.budget.limits.decoded - self.budget.decoded:
                            raise FormatLimit(
                                "PNG samples exceed remaining root decoded-byte budget"
                            )
                        if self.decoded + samples > self.png_allowance:
                            self.raster_skips.append(
                                "OfficeArt PNG root decode reservation exhausted; retained"
                            )
                            return Record(flags, kind, body)
                    before = self.budget.decoded
                    parsed = (
                        png_data(encoded, self.budget)
                        if kind == 0xF01E
                        else jpeg_data(encoded, self.budget)
                    )
                    self.decoded += self.budget.decoded - before
                    if self.decoded > MAX_TOTAL and (not self.bounded_png or self.word_properties):
                        raise FormatLimit("OfficeArt aggregate picture limit exceeded")
                    if len(self.rasters) + len(self.metafiles) >= MAX_OBJECTS:
                        raise FormatLimit("OfficeArt picture count limit exceeded")
                    identity = (
                        PngIdentity.from_data(parsed, refilter=True, budget=self.budget)
                        if (self.bounded_png and isinstance(parsed, PngData))
                        else parsed
                    )
                    retained = memoryview(body)[uid_size + 1 :] if self.bounded_png else encoded
                    result = Record(
                        flags, kind, body, raster=Raster(body[: uid_size + 1], retained, identity)
                    )
                    self.rasters.append(result)
                    return result
                except (UnsupportedFormat, zlib.error) as exc:
                    self.raster_skips.append(str(exc))
        else:
            require(
                LEAVES.get(kind) == flags & 15
                or self.word_properties and kind == 0xF122 and flags & 15 == 3,
                f"unsupported OfficeArt type/version: {hex(kind)}, version {flags & 15}",
            )
            leaf_bounds(flags, kind, body, word_properties=self.word_properties)
        return Record(flags, kind, body)

    def metafile(self, flags: int, kind: int, body: bytes) -> Record:
        require(flags & 15 == 0 and flags >> 4 in METAFILES[kind], "metafile version/instance")
        uid_size = 16 * (1 + (flags >> 4 == METAFILES[kind][1]))
        require(len(body) >= uid_size + 34, "truncated metafile header")
        decoded = struct.unpack_from("<I", body, uid_size)[0]
        saved = struct.unpack_from("<I", body, uid_size + 28)[0]
        require(
            body[uid_size + 32 : uid_size + 34] == b"\x00\xfe",
            "only compressed EMF/WMF with filter FE are qualified",
        )
        if not 0 < decoded <= MAX_PAYLOAD or not 0 < saved <= MAX_PAYLOAD:
            raise FormatLimit("OfficeArt encoded/decoded metafile exceeds 16 MiB")
        if (
            len(self.metafiles) + len(self.rasters) >= MAX_OBJECTS
            or self.decoded + decoded > MAX_TOTAL
        ):
            raise FormatLimit("OfficeArt metafile count/aggregate limit exceeded")
        encoded = body[uid_size + 34 :]
        require(len(encoded) == saved, "cbSave/record length differs")
        self.budget.memory(decoded * 2)
        try:
            raw = inflate(encoded, self.budget, maximum=decoded)
        except zlib.error as exc:
            raise UnsupportedFormat("OfficeArt: invalid metafile zlib envelope") from exc
        require(len(raw) == decoded, "decoded cbSize differs")
        result = Record(flags, kind, body, metafile=Metafile(body[: uid_size + 34], raw, encoded))
        self.metafiles.append(result)
        self.decoded += decoded
        return result

    def fbse(self, flags: int, body: bytes, depth: int) -> Record:
        require(flags & 15 == 2 and len(body) >= 36, "FBSE version/length")
        name_size = body[33]
        require(
            name_size % 2 == 0 and name_size <= 254 and 36 + name_size <= len(body),
            "FBSE name bounds",
        )
        require(
            not name_size or body[34 + name_size : 36 + name_size] == b"\0\0",
            "FBSE name terminator",
        )
        embedded = body[36 + name_size :]
        if not embedded:
            return Record(flags, 0xF007, body)
        require(flags >> 4 in body[:2], "FBSE type differs")
        require(
            struct.unpack_from("<I", body, 20)[0] == len(embedded), "embedded FBSE size differs"
        )
        children = self.sequence(embedded, depth + 1)
        require(len(children) == 1 and children[0].kind in BLIPS, "embedded FBSE BLIP count/type")
        require(
            flags >> 4 == {0xF01A: 2, 0xF01B: 3, 0xF01D: 5, 0xF01E: 6}[children[0].kind],
            "embedded FBSE type/BLIP mismatch",
        )
        child = children[0]
        uid_size = 16 * (1 + (child.flags >> 4 == BLIPS[child.kind][1]))
        require(body[2:18] == child.body[uid_size - 16 : uid_size], "embedded FBSE UID differs")
        return Record(flags, 0xF007, body, children)


def _zopfli() -> Optional[Callable[..., bytes]]:
    try:
        if version("zopfli") != "0.4.3":
            return None
        from zopfli.zlib import compress

        return cast(Callable[..., bytes], compress)
    except (ImportError, PackageNotFoundError):
        return None


def encode_metafiles(
    records: List[Record], budget: Budget, ultra: bool = False
) -> Tuple[Dict[int, bytes], List[str]]:
    stronger = _zopfli()
    result, encoders = {}, []
    for record in records:
        budget.check()
        meta = record.metafile
        assert meta is not None
        payload, encoder = meta.encoded, "original"
        trial = zlib.compress(meta.raw, 9)
        require(
            inflate(trial, budget, maximum=len(meta.raw)) == meta.raw,
            "zlib encoder changed decoded metafile bytes",
        )
        if len(trial) < len(payload):
            payload, encoder = trial, "zlib9"
        if stronger is not None:
            for iterations, cutoff in ((15, 1024 * 1024), (50, 2 * 1024 * 1024)):
                if (iterations == 15 or ultra) and len(meta.raw) <= cutoff:
                    budget.check()
                    trial = bytes(stronger(meta.raw, numiterations=iterations))
                    budget.check()
                    require(
                        inflate(trial, budget, maximum=len(meta.raw)) == meta.raw,
                        "Zopfli encoder changed decoded metafile bytes",
                    )
                    if len(trial) < len(payload):
                        payload, encoder = trial, "zopfli" + str(iterations)
        require(
            inflate(payload, budget, maximum=len(meta.raw)) == meta.raw,
            "encoder changed decoded metafile bytes",
        )
        result[id(record)] = payload
        encoders.append(encoder)
    return result, encoders


def encode_rasters(
    records: List[Record], budget: Budget, ultra: bool = False,
    skips: Optional[List[str]] = None,
) -> Tuple[Dict[int, bytes], List[str]]:
    stronger, result, encoders = _zopfli(), {}, []
    tool = None
    if any(r.raster is not None and isinstance(r.raster.parsed, PngIdentity)
           and r.raster.parsed.refilter for r in records):
        tool, reason = qualified_png_tool(budget)
        if reason and skips is not None and reason not in skips:
            skips.append(reason)
    for record in records:
        budget.check()
        image = record.raster
        assert image is not None
        source = bytes(image.encoded)
        if isinstance(image.parsed, (PngData, PngIdentity)):
            parsed = image.parsed if isinstance(image.parsed, PngData) else png_data(source, budget)
            if isinstance(image.parsed, PngIdentity):
                require(image.parsed.matches_source(parsed), "PNG lazy identity changed")
            if isinstance(image.parsed, PngIdentity) and image.parsed.refilter:
                encoded, encoder = optimize_refiltered_png(
                    source, parsed, image.parsed, budget, stronger, ultra, tool, skips
                )
            else:
                encoded, encoder = optimize_png(source, parsed, budget, stronger, ultra)
            del parsed
        else:
            encoded, encoder = optimize_jpeg(source, image.parsed, budget)
        if not encoder.startswith("original"):
            result[id(record)] = encoded
        encoders.append(encoder)
    return result, encoders
