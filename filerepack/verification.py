"""Declared structural checks; discovery signatures never authorize publication."""

import bz2
import gzip
import hashlib
import json
import io
import struct
import logging
import lzma
import os
from pathlib import Path
import sqlite3
import tarfile
import warnings
import zipfile
from dataclasses import dataclass
from typing import Any, Callable, ContextManager, Dict, Literal, Optional, Tuple

from .commands import capture_bytes, consume_command, check_command
from .tools import resolve_szip, resolve_tool
from .streams import BinaryReader

MAX_PARSE_BYTES = 256 * 1024 * 1024
MAX_DECODE_BYTES = 512 * 1024 * 1024
_LOG = logging.getLogger(__name__)


class VerificationUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    kind: str
    reason: str = ""
    preservation: bool = False


def read_bounded(path: str) -> bytes:
    with open(path, "rb") as source:
        data = source.read(MAX_PARSE_BYTES + 1)
    if len(data) > MAX_PARSE_BYTES:
        raise VerificationUnavailable("Parser input exceeds the supported 256 MiB bound")
    return data


def _hash_reader(source: Any) -> str:
    checksum = hashlib.sha256()
    count = 0
    for block in iter(lambda: source.read(65536), b""):
        count += len(block)
        if count > MAX_DECODE_BYTES:
            raise VerificationUnavailable("Decoded payload exceeds the supported 512 MiB bound")
        checksum.update(block)
    return checksum.hexdigest()


def stream_fingerprint(path: str, kind: str) -> str:
    readers: Dict[str, Callable[[str, Literal["rb"]], ContextManager[BinaryReader]]] = {
        "gz": gzip.open,
        "svgz": gzip.open,
        "bz2": bz2.open,
        "xz": lzma.open,
        "lzma": lzma.open,
    }
    if kind in readers:
        from .streams import _native_stream
        return str(_native_stream('fingerprint', path, kind)['fingerprint'])
    tools = {"zst": "zstd", "br": "brotli", "lz4": "lz4", "lz": "lzip", "lzo": "lzop", "z": "gzip"}
    tool = resolve_tool(tools[kind])
    if tool is None:
        raise VerificationUnavailable("Required stream decoder is unavailable: " + tools[kind])
    checksum = hashlib.sha256()
    if not consume_command(
        [tool, "-d", "-c", os.path.abspath(path)], checksum.update, max_output=MAX_DECODE_BYTES
    ):
        raise ValueError("Stream decode failed, timed out or exceeded its output bound")
    return checksum.hexdigest()


def _stream(path: str, kind: str) -> None:
    stream_fingerprint(path, kind)
    if kind == "svgz":
        from .markup import minify_xml_bytes

        with gzip.open(path, "rb") as source:
            data = source.read(MAX_PARSE_BYTES + 1)
        if len(data) > MAX_PARSE_BYTES or minify_xml_bytes(data) is None:
            raise ValueError("Invalid or unsupported compressed SVG markup")
        _svg_root(data)


def _zip(path: str, kind: str) -> None:
    with zipfile.ZipFile(path) as archive:
        total = 0
        for member in archive.infolist():
            total += member.file_size
            if total > MAX_DECODE_BYTES:
                raise VerificationUnavailable("ZIP validation exceeds its decoded-byte bound")
            with archive.open(member) as source:
                _hash_reader(source)  # Reads to EOF, including the CRC check.


def _tar(path: str, kind: str) -> None:
    # TarFile can stop at a short zero tail; require complete end-of-archive blocks.
    size = os.path.getsize(path)
    if size < 1024 or size % 512:
        raise ValueError("Truncated tar blocks")
    with open(path, "rb") as source:
        source.seek(-1024, os.SEEK_END)
        if source.read() != b"\0" * 1024:
            raise ValueError("Missing tar end-of-archive blocks")
    with tarfile.open(path, mode="r:", errorlevel=2) as archive:
        total = 0
        for member in archive:
            total += member.size
            if total > MAX_DECODE_BYTES:
                raise VerificationUnavailable("Tar validation exceeds its decoded-byte bound")
            if member.isfile():
                payload = archive.extractfile(member)
                if payload is None:
                    raise ValueError("Missing tar payload")
                with payload:
                    _hash_reader(payload)


def _cpio(path: str, kind: str) -> None:
    from .cpio import validate_cpio

    validate_cpio(path)


def _cpbz2(path: str, kind: str) -> None:
    from .cpio import validate_cpbz2

    validate_cpbz2(path)


def _archive_tool(path: str, kind: str) -> None:
    tool = resolve_szip()
    if tool is None:
        raise VerificationUnavailable("7z/7zz is required for archive integrity testing")
    listing = capture_bytes(
        [tool, "l", "-slt", "-y", "-spd", "--", os.path.abspath(path)], max_output=8 * 1024 * 1024
    )
    if listing is None:
        raise ValueError("Archive container inspection failed or exceeded its bound")
    header = listing.split(b"----------", 1)[0]
    formats = {
        line[7:].strip().lower() for line in header.splitlines() if line.startswith(b"Type = ")
    }
    expected = {b"rar", b"rar5"} if kind == "rar" else {kind.encode()}
    if not formats.intersection(expected):
        raise ValueError("Archive parser identified a different container")
    if not check_command([tool, "t", "-y", "-spd", "--", os.path.abspath(path)]):
        raise ValueError("Archive integrity test failed or timed out")


_IMAGE_FORMATS = {
    "jpg": {"JPEG"},
    "png": {"PNG"},
    "gif": {"GIF"},
    "webp": {"WEBP"},
    "bmp": {"BMP"},
    "tga": {"TGA"},
    "pnm": {"PPM"},
    "pcx": {"PCX"},
    "tif": {"TIFF"},
    "dng": {"TIFF"},
    "ico": {"ICO"},
    "cur": {"CUR"},
    "icns": {"ICNS"},
    "avif": {"AVIF"},
    "heic": {"HEIF"},
    "jp2": {"JPEG2000"},
    "jxl": {"JXL"},
    "exr": {"EXR"},
}


def _icon_fingerprint(path: str, kind: str) -> Tuple[object, ...]:
    from PIL import Image

    data = read_bounded(path)
    reserved, encoded_kind, count = struct.unpack_from("<HHH", data)
    expected = 2 if kind == "cur" else 1
    if reserved or encoded_kind != expected or not 0 < count <= 4096:
        raise ValueError("Invalid icon directory or unsupported frame count")
    result = []
    for index in range(count):
        entry = data[6 + index * 16 : 22 + index * 16]
        length, offset = struct.unpack_from("<II", entry, 8)
        if offset < 6 + count * 16 or not length or offset + length > len(data):
            raise ValueError("Truncated icon directory/payload")
        payload = data[offset : offset + length]
        if payload.startswith(b"\x89PNG"):
            with Image.open(io.BytesIO(payload)) as embedded:
                embedded.verify()
        single = data[:4] + b"\x01\0" + entry[:12] + struct.pack("<I", 22) + payload
        with Image.open(io.BytesIO(single)) as frame:
            frame.load()
            pixels = frame.convert("RGBA").tobytes()
            hotspot = entry[4:8] if kind == "cur" else b""
            result.append((frame.size, hotspot, hashlib.sha256(pixels).hexdigest()))
    return tuple(result)


def _icns_fingerprint(path: str) -> Tuple[object, ...]:
    from PIL import Image
    from PIL.IcnsImagePlugin import IcnsFile

    data = read_bounded(path)
    signature, size = struct.unpack_from(">4sI", data)
    if signature != b"icns" or size != len(data):
        raise ValueError("Truncated ICNS container")
    supported = {code for variants in IcnsFile.SIZES.values() for code, _reader in variants}
    offset, seen = 8, set()
    while offset < size:
        code, length = struct.unpack_from(">4sI", data, offset)
        if length < 8 or offset + length > size or code in seen:
            raise ValueError("Invalid/duplicate ICNS resource")
        if code not in supported and code not in (b"TOC ", b"icnV"):
            raise VerificationUnavailable("Unsupported ICNS resource decoder")
        seen.add(code)
        payload = data[offset + 8 : offset + length]
        if payload.startswith(b"\x89PNG"):
            with Image.open(io.BytesIO(payload)) as embedded:
                embedded.verify()
        offset += length
    result = []
    total = 0
    with Image.open(path) as image:
        for size_key in sorted(getattr(image, "icns").itersizes()):
            frame = getattr(image, "icns").getimage(size_key)
            total += frame.width * frame.height * 4
            if total > MAX_DECODE_BYTES:
                raise VerificationUnavailable("ICNS decoding exceeds its byte bound")
            frame.load()
            result.append((size_key, hashlib.sha256(frame.convert("RGBA").tobytes()).hexdigest()))
    if not result:
        raise ValueError("ICNS has no decodable icon resources")
    return tuple(result)


def _raster_encoding(path: str, image: Any) -> Optional[Tuple[str, object]]:
    if image.format == 'JPEG2000':
        from .raster_layout import _jpx_layout
        from .format_support import current_budget
        budget = current_budget()
        if budget:
            budget.memory(os.path.getsize(path) * 2 + image.width * image.height * 16)
        return 'jpx_layout', _jpx_layout(read_bounded(path))
    if image.format == 'PNG':
        with open(path, 'rb') as source:
            header = source.read(26)
        if len(header) != 26:
            raise ValueError('Truncated PNG sample header')
        if header[24] == 16 and header[25] != 0:
            raise VerificationUnavailable('Unsupported multichannel 16-bit PNG decoding')
        return 'png_encoding', (header[24], header[25])
    return None


def image_fingerprint(path: str, kind: str) -> Tuple[object, ...]:
    try:
        from PIL import Image, ImageFile
    except ImportError as exc:
        raise VerificationUnavailable("Install filerepack[validation] for raster decoding") from exc
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise VerificationUnavailable("Pillow truncated-image loading is enabled")
    if kind in ("ico", "cur"):
        return _icon_fingerprint(path, kind)
    if kind == "icns":
        return _icns_fingerprint(path)
    result = []
    pixels = 0
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as image:
            if image.format not in _IMAGE_FORMATS[kind]:
                raise ValueError("Image parser identified a different format")
            image.verify()
        with Image.open(path) as image:
            encoded_layout = _raster_encoding(path, image)
            frames = getattr(image, "n_frames", 1)
            if frames > 4096:
                raise VerificationUnavailable("Image frame count exceeds the supported bound")
            for frame in range(frames):
                image.seek(frame)
                if image.format == "TIFF":
                    bits = getattr(image, "tag_v2").get(258, (8,))
                    if any(bit > 8 for bit in bits) and image.mode not in ("I", "I;16", "F"):
                        raise VerificationUnavailable("Unsupported high-depth TIFF decoding")
                pixels += image.width * image.height
                if pixels > MAX_DECODE_BYTES // 8:
                    raise VerificationUnavailable("Image pixels exceed the supported bound")
                image.load()
                decoded = image if image.mode in ("I", "I;16", "F") else image.convert("RGBA")
                result.append(
                    (
                        image.size,
                        decoded.mode,
                        image.info.get("duration"),
                        hashlib.sha256(decoded.tobytes()).hexdigest(),
                    )
                )
            critical = {key: image.info.get(key) for key in
                        ('icc_profile', 'gamma', 'srgb', 'chromaticity', 'dpi', 'xmp')}
            if encoded_layout is not None:
                critical[encoded_layout[0]] = encoded_layout[1]
            critical['orientation'] = image.getexif().get(274)
            from .format_support import current_options
            if current_options().get('keep_meta'):
                critical.update({key: image.info.get(key) for key in ('exif', 'comment')})
                critical['text'] = dict(getattr(image, 'text', {}))
            return (image.info.get("loop"), critical, tuple(result))


def _image(path: str, kind: str) -> None:
    try:
        image_fingerprint(path, kind)
    except ImportError as exc:
        raise VerificationUnavailable("Pillow is required for image validation") from exc


def _markup(path: str, kind: str) -> None:
    if kind == "jsonl":
        from .markup import _json_line, _MAX_JSON_LINE

        with open(path, "rb") as source:
            for line in iter(lambda: source.readline(_MAX_JSON_LINE + 1), b""):
                if len(line) > _MAX_JSON_LINE or _json_line(line) is None:
                    raise ValueError("Invalid or unsupported JSON Lines structure")
        return
    from .markup import minify_json_bytes, minify_xml_bytes

    data = read_bounded(path)
    if kind == "json":
        valid = minify_json_bytes(data) is not None
    elif kind == "qgs":
        from .qgis import minify_qgis_bytes

        valid = minify_qgis_bytes(data) is not None
    else:
        valid = minify_xml_bytes(data) is not None
    if not valid:
        raise ValueError("Invalid or unsupported markup structure")
    if kind == "svg":
        _svg_root(data)


def _svg_root(data: bytes) -> None:
    from xml.etree import ElementTree

    # The lexical XML validator has already refused DTD/entity declarations.
    root = ElementTree.fromstring(data)
    if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
        raise ValueError("SVG parser identified a different document root")


def _sqlite(path: str, kind: str) -> None:
    # immutable read-only inspection neither creates journals nor repairs files.
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
    finally:
        connection.close()


def _arrow_table(path: str, kind: str) -> Any:
    try:
        import pyarrow as pa

        if kind == "parquet":
            import pyarrow.parquet as pq

            return pq.read_table(path)
        if kind == "orc":
            import pyarrow.orc as orc

            return orc.read_table(path)
        if kind == "feather":
            import pyarrow.feather as feather

            return feather.read_table(path)
        with pa.memory_map(path, "r") as source:
            try:
                return pa.ipc.open_file(source).read_all()
            except pa.ArrowInvalid:
                source.seek(0)
                return pa.ipc.open_stream(source).read_all()
    except ImportError as exc:
        raise VerificationUnavailable("PyArrow is required for data validation") from exc


def _arrow(path: str, kind: str) -> None:
    if os.path.getsize(path) > MAX_PARSE_BYTES:
        raise VerificationUnavailable("Data validation exceeds its input-byte bound")
    if kind == "parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise VerificationUnavailable("PyArrow is required for data validation") from exc
        total = 0
        with pq.ParquetFile(path) as source:
            for batch in source.iter_batches(batch_size=65536):
                total += batch.nbytes
                if total > MAX_DECODE_BYTES:
                    raise VerificationUnavailable("Decoded data exceeds its byte bound")
                batch.validate(full=True)
        return
    from .format_support import run_operation
    run_operation(kind + '-native', 'inspect', path)


def _avro(path: str, kind: str) -> None:
    try:
        import fastavro
    except ImportError as exc:
        raise VerificationUnavailable("fastavro is required for Avro validation") from exc
    with open(path, "rb") as source:
        for _record in fastavro.reader(source):
            pass


def _hdf(path: str, kind: str) -> None:
    try:
        import h5py
    except ImportError as exc:
        raise VerificationUnavailable("h5py is required for HDF5 validation") from exc
    with h5py.File(path, "r") as source:

        def read(_name: str, item: Any) -> None:
            if isinstance(item, h5py.Dataset):
                if item.size * item.dtype.itemsize > MAX_DECODE_BYTES:
                    raise VerificationUnavailable("HDF5 dataset exceeds its decoded-byte bound")
                item[()]

        source.visititems(read)


def _netcdf(path: str, kind: str) -> None:
    try:
        import netCDF4
    except ImportError as exc:
        raise VerificationUnavailable("netCDF4 is required for NetCDF validation") from exc
    with netCDF4.Dataset(path, "r") as source:

        def read(group: Any) -> None:
            for variable in group.variables.values():
                if variable.size * variable.dtype.itemsize > MAX_DECODE_BYTES:
                    raise VerificationUnavailable("NetCDF variable exceeds its decoded-byte bound")
                variable[:]
            for child in group.groups.values():
                read(child)

        read(source)


def _font(path: str, kind: str) -> None:
    from .format_support import run_operation
    with open(path, 'rb') as source:
        if source.read(4) != {'woff': b'wOFF', 'woff2': b'wOF2'}[kind]:
            raise ValueError('Font parser identified a different format')
    run_operation('font-native', 'inspect', path)


_MEDIA_KINDS = {
    "mp4",
    "mov",
    "m4v",
    "m4a",
    "3gp",
    "video",
    "mkv",
    "webm",
    "avi",
    "asf",
    "wmv",
    "ts",
    "mts",
    "m2ts",
    "flac",
    "wv",
    "ape",
    "tta",
    "oga",
    "ogg",
    "opus",
    "mp3",
}


_MEDIA_CONTAINERS = {
    **dict.fromkeys(("mp4", "mov", "m4v", "m4a", "3gp"), {"mov", "mp4", "m4a", "3gp"}),
    **dict.fromkeys(("mkv", "webm"), {"matroska", "webm"}),
    **dict.fromkeys(("asf", "wmv"), {"asf"}),
    **dict.fromkeys(("ts", "mts", "m2ts"), {"mpegts"}),
    **dict.fromkeys(("oga", "ogg", "opus"), {"ogg"}),
    "avi": {"avi"},
    "flac": {"flac"},
    "wv": {"wv"},
    "ape": {"ape"},
    "tta": {"tta"},
    "mp3": {"mp3"},
}


def _media(path: str, kind: str) -> None:
    tool, probe = resolve_tool("ffmpeg"), resolve_tool("ffprobe")
    if tool is None or probe is None:
        raise VerificationUnavailable("ffmpeg and ffprobe are required for media validation")
    output = capture_bytes(
        [
            probe,
            "-v",
            "error",
            "-show_entries",
            "format=format_name",
            "-of",
            "json",
            os.path.abspath(path),
        ],
        max_output=65536,
    )
    if output is None:
        raise ValueError("Media container inspection failed or timed out")
    formats = set(json.loads(output)["format"]["format_name"].split(","))
    if kind != "video" and not formats.intersection(_MEDIA_CONTAINERS[kind]):
        raise ValueError("Media parser identified a different container")
    if not check_command(
        [
            tool,
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-i",
            os.path.abspath(path),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
            "-f",
            "null",
            "-",
        ]
    ):
        raise ValueError("Media decoding failed or timed out")


def _pdf(path: str, kind: str) -> None:
    from .pdf_verify import inspect_pdf

    result = inspect_pdf(path)
    if not result.rewritable:
        raise ValueError(result.reason)


def _native(path: str, kind: str) -> None:
    if kind == "psd":
        tool = resolve_tool("convert")
        if tool is None:
            raise VerificationUnavailable("ImageMagick is required for PSD layer decoding")
        if not check_command([tool, "-regard-warnings", os.path.abspath(path), "null:"]):
            raise ValueError("PSD layer/composite decoding failed")
        return
    _native_fingerprint(path, kind)


def _native_fingerprint(path: str, kind: str) -> object:
    if kind == "blend":
        import tempfile
        from .blend import decode_blend, validate_blend
        from .transactions import digest

        with tempfile.TemporaryDirectory(prefix="filerepack-verify-blend-") as directory:
            decoded = os.path.join(directory, "decoded.blend")
            decode_blend(path, decoded)
            validate_blend(decoded)
            return digest(decoded)
    data = read_bounded(path)
    if kind == "psb":
        from .psb import psb_fingerprint

        return psb_fingerprint(data)
    if kind == "nrrd":
        from .nrrd import decode_nrrd

        return decode_nrrd(data)
    if kind == "aseprite":
        from .aseprite import rewrite_aseprite

        return rewrite_aseprite(data)[1]
    if kind == "swf":
        from .swf import decode_swf

        return decode_swf(data)
    if kind == "tgs":
        from .tgs import decode_tgs

        return decode_tgs(data)
    if kind == "psd":
        from .images import _recompress_psd_bytes

        return _recompress_psd_bytes(data) or data
    raise VerificationUnavailable("No supported structural parser for " + kind)


def _cpio_preservation_equal(source: str, candidate: str, kind: str) -> bool:
    if kind == "cpio":
        with open(source, "rb") as original, open(candidate, "rb") as updated:
            return _hash_reader(original) == _hash_reader(updated)
    return stream_fingerprint(source, "bz2") == stream_fingerprint(candidate, "bz2")


def _fits(path: str, kind: str) -> None:
    from .fits import validate_fits

    validate_fits(path)


def _nib(path: str, kind: str) -> None:
    from .nib import nib_file_fingerprint

    nib_file_fingerprint(path)


def _car(path: str, kind: str) -> None:
    from .car import car_file_fingerprint

    car_file_fingerprint(path)


def _duckdb(path: str, kind: str) -> None:
    from .duckdb import duckdb_fingerprint

    duckdb_fingerprint(path)


def _ole(path: str, kind: str) -> None:
    from .ole_verify import ole_fingerprint

    ole_fingerprint(path)


def _ppt_ole(path: str, kind: str) -> None:
    from .ole_recompress import run_ppt_operation

    run_ppt_operation("inspect", path)


def _officeart(path: str, kind: str) -> None:
    from .ole_recompress import run_art_operation

    run_art_operation("inspect", path)


def _hwp_ole(path: str, kind: str) -> None:
    from .ole_recompress import run_hwp_operation

    run_hwp_operation("inspect", path)


def _ole_embedded(path: str, kind: str) -> None:
    from .ole_transform import run_transform_operation

    run_transform_operation("inspect", path)


def _ole_dedup(path: str, kind: str) -> None:
    from .ole_dedup import run_dedup_operation

    run_dedup_operation("inspect", path)


_ALIASES = {
    "gzip": "gz",
    "zstd": "zst",
    "jpeg": "jpg",
    "tiff": "tif",
    "heif": "heic",
    "j2k": "jp2",
    "jpf": "jp2",
    "jpx": "jp2",
    "cpio.bz2": "cpbz2",
    "ipc": "arrow",
    "db": "sqlite",
    "h5": "hdf5",
    "nc4": "nc",
    "netcdf": "nc",
    "ai": "pdf",
    "geojson": "json",
    "ipynb": "json",
    "ndjson": "jsonl",
    "ui": "xml",
    "qgz": "zip",
    "qgd": "sqlite",
    "fit": "fits",
    "fts": "fits",
    "ase": "aseprite",
    "vscdb": "sqlite",
    "sqlitedb": "sqlite",
    "mellel": "zip",
    "rels": "xml",
    "map": "json",
    "har": "json",
    "topojson": "json",
    "gltf": "json",
}
Validator = Callable[[str, str], None]


def _warc(path: str, kind: str) -> None:
    from .warc import validate_warc_gzip

    validate_warc_gzip(path)

SCIENTIFIC_KINDS = frozenset(
    {
        'font-native',
        'tracev3',
        'arrow-native', 'feather-native', 'orc-native',
        'avro-native',
        "r-serialization",
        "mat",
        "hdf5-native",
        "netcdf-native",
        "tiff-native",
        "checkpoint",
        "spss",
    }
)


def _scientific(path: str, kind: str) -> None:
    from .format_support import run_operation

    run_operation(kind, "inspect", path)


VALIDATORS: Dict[str, Validator] = {
    "warc": _warc,
    **dict.fromkeys(SCIENTIFIC_KINDS, _scientific),
    **dict.fromkeys(
        ("gz", "svgz", "xz", "bz2", "zst", "br", "lz4", "lz", "lzo", "z", "lzma"), _stream
    ),
    **dict.fromkeys(("zip", "ooxml", "jar", "epub", "cbz"), _zip),
    **dict.fromkeys(("7z", "rar", "cab", "wim"), _archive_tool),
    **dict.fromkeys(_IMAGE_FORMATS, _image),
    **dict.fromkeys(("json", "jsonl", "xml", "svg", "qgs"), _markup),
    **dict.fromkeys(("parquet", "orc", "feather", "arrow"), _arrow),
    **dict.fromkeys(_MEDIA_KINDS, _media),
    **dict.fromkeys(("psb", "nrrd", "aseprite", "psd", "blend", "swf", "tgs"), _native),
    "tar": _tar,
    "cpio": _cpio,
    "cpbz2": _cpbz2,
    "sqlite": _sqlite,
    "avro": _avro,
    "hdf5": _hdf,
    "nc": _netcdf,
    "woff": _font,
    "woff2": _font,
    "pdf": _pdf,
    "fits": _fits,
    "nib": _nib,
    "car": _car,
    "duckdb": _duckdb,
    "ole": _ole,
    "ppt-ole": _ppt_ole,
    "officeart": _officeart,
    "hwp-ole": _hwp_ole,
    "ole-embedded": _ole_embedded,
    "ole-dedup": _ole_dedup,
}


def validate_output(path: str, kind: str, *, source_path: Optional[str] = None) -> ValidationResult:
    from .evidence import validation
    key = _ALIASES.get(kind, kind)
    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise ValueError("Candidate is missing or empty")
        if key in ("dcm", "dicom", "dic"):
            from .dicom_verify import verify_dicom

            if not verify_dicom(path, source_path):
                raise ValueError("DICOM structure/attribute/pixel check failed or unavailable")
            validation(key, 'structure-and-preservation', True)
            return ValidationResult(True, key, preservation=True)
        validator = VALIDATORS.get(key)
        if validator is None:
            raise VerificationUnavailable("Unknown validator kind: " + key)
        validator(path, key)
        validation(key, 'structure', True)
        return ValidationResult(True, key)
    except Exception as exc:
        result = ValidationResult(False, key, str(exc))
        validation(key, 'structure', False, str(exc))
        _LOG.warning("Candidate validation refused (%s): %s", key, result.reason)
        return result


def _data_equal(left: str, right: str, kind: str) -> bool:
    from .format_support import run_operation
    return bool(run_operation(kind + '-native', 'compare', left, right).get('equal'))


def preservation_equal(source: str, candidate: str, kind: str) -> bool:  # noqa: C901
    key = _ALIASES.get(kind, kind)
    if key in ("warc", "nib", "car"):
        from .warc import warc_fingerprint
        from .nib import nib_file_fingerprint
        from .car import car_file_fingerprint

        fingerprint = {"warc": warc_fingerprint, "nib": nib_file_fingerprint,
                       "car": car_file_fingerprint}[key]
        return fingerprint(source) == fingerprint(candidate)
    if key in SCIENTIFIC_KINDS:
        from .format_support import run_operation

        return bool(run_operation(key, "compare", source, candidate).get("equal"))
    if key == "ole":
        from .ole_verify import ole_fingerprint

        return ole_fingerprint(source) == ole_fingerprint(candidate)
    if key in ("ppt-ole", "officeart", "hwp-ole", "ole-embedded", "ole-dedup"):
        from .ole_recompress import run_ppt_operation, run_art_operation, run_hwp_operation
        from .ole_transform import run_transform_operation
        from .ole_dedup import run_dedup_operation

        runner = {
            "ppt-ole": run_ppt_operation,
            "officeart": run_art_operation,
            "hwp-ole": run_hwp_operation,
            "ole-embedded": run_transform_operation,
            "ole-dedup": run_dedup_operation,
        }[key]
        return bool(runner("compare", source, candidate).get("equal"))
    if key in ("gz", "xz", "bz2", "zst", "br", "lz4", "lz", "lzo", "z", "lzma"):
        return stream_fingerprint(source, key) == stream_fingerprint(candidate, key)
    if key in ('woff', 'woff2'):
        from .format_support import run_operation
        return bool(run_operation('font-native', 'compare', source, candidate).get('equal'))
    if key in ("cpio", "cpbz2"):
        return _cpio_preservation_equal(source, candidate, key)
    if key in _IMAGE_FORMATS:
        return image_fingerprint(source, key) == image_fingerprint(candidate, key)
    if key in ("arrow", "feather", "orc"):
        return _data_equal(source, candidate, key)
    if key == "sqlite":
        from .qgis import sqlite_fingerprint

        return sqlite_fingerprint(source) == sqlite_fingerprint(candidate)
    if key == "json":
        from .markup import minify_json_bytes

        original_json = minify_json_bytes(read_bounded(source))
        return original_json is not None and original_json == minify_json_bytes(
            read_bounded(candidate),
        )
    if key == "jsonl":
        from .markup import verify_jsonl

        return verify_jsonl(source, candidate)
    if key == "fits":
        from .fits import verify_fits

        return verify_fits(source, candidate)
    if key == "pdf":
        from .pdf_verify import pdf_fingerprint

        return pdf_fingerprint(source) == pdf_fingerprint(candidate)
    if key == "duckdb":
        from .duckdb import verify_duckdb

        return verify_duckdb(source, candidate)
    if key in ("psd", "psb", "aseprite", "nrrd", "blend", "swf", "tgs"):
        return _native_fingerprint(source, key) == _native_fingerprint(candidate, key)
    raise VerificationUnavailable("No declared source-preservation adapter for " + key)


def verify_preservation(source: str, candidate: str, kind: str) -> bool:
    from .evidence import validation
    try:
        if not preservation_equal(source, candidate, kind):
            raise ValueError("Decoded/logical candidate content differs from the source")
        validation(kind, 'preservation', True)
        return True
    except Exception as exc:
        validation(kind, 'preservation', False, str(exc))
        _LOG.warning("Candidate preservation refused (%s): %s", kind, exc)
        return False
