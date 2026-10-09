"""Typed standalone dispatch; registry values retain existing public contracts."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .models import PackResult
from .outcomes import record
from .selection import category_enabled, embedded_images_enabled
from .aseprite import pack_aseprite
from .blend import pack_blend
from .fits import pack_fits
from .nrrd import pack_nrrd
from .nib import pack_nib
from .car import pack_car
from .tracev3 import pack_tracev3
from .warc import pack_warc
from .psb import pack_psb
from .qgis import pack_qgs, pack_qgd
from .duckdb import pack_duckdb
from .swf import pack_swf
from .tgs import pack_tgs
from .ole import pack_ole
from .r_serialization import pack_r_serialization
from .mat import pack_mat
from .checkpoint import pack_checkpoint
from .spss import pack_spss
from .model_formats import pack_gguf, pack_onnx, pack_safetensors

from .data import (
    pack_arrow,
    pack_avro,
    pack_feather,
    pack_hdf5,
    pack_netcdf,
    pack_orc,
    pack_parquet,
    pack_sqlite,
    pack_woff,
    pack_woff2,
)

from .documents import (
    pack_ai,
    pack_pdf,
)

from .images import (
    pack_avif,
    pack_bmp,
    pack_dng,
    pack_exr,
    pack_gif,
    pack_heic,
    pack_icns,
    pack_ico,
    pack_jp2,
    pack_jpg,
    pack_jxl,
    pack_pcx,
    pack_png,
    pack_pnm,
    pack_psd,
    pack_svg,
    pack_svgz,
    pack_tga,
    pack_tif,
    pack_webp,
)

from .markup import (
    pack_json,
    pack_jsonl,
    pack_xml,
)

from .media import (
    pack_3gp,
    pack_ape,
    pack_asf,
    pack_avi,
    pack_flac,
    pack_m4a,
    pack_m4v,
    pack_mkv,
    pack_mov,
    pack_mp3,
    pack_mp4,
    pack_oga,
    pack_ogg,
    pack_ts,
    pack_tta,
    pack_webm,
    pack_wmv,
    pack_wv,
)

from .medical import (
    pack_dcm,
)

from .streams import (
    pack_brotli,
    pack_bz2,
    pack_compress,
    pack_gzip,
    pack_lz4,
    pack_lzip,
    pack_lzma,
    pack_lzo,
    pack_xz,
    pack_zstd,
)


@dataclass
class PackerSpec:
    func: Callable[..., Optional[PackResult]]
    category: str
    extra: Dict[str, str] = field(default_factory=dict)


_PACKERS: Dict[str, PackerSpec] = {
    'tracev3': PackerSpec(pack_tracev3, 'data'),
    "warc": PackerSpec(pack_warc, "data", {
        "convert_container": "convert_container", "ultra": "ultra",
    }),
    "r-serialization": PackerSpec(pack_r_serialization, "data"),
    "mat": PackerSpec(pack_mat, "data"),
    "checkpoint": PackerSpec(pack_checkpoint, "data"),
    "spss": PackerSpec(pack_spss, "data"),
    "safetensors": PackerSpec(pack_safetensors, "data"),
    "gguf": PackerSpec(pack_gguf, "data"),
    "onnx": PackerSpec(pack_onnx, "data"),
    "nib": PackerSpec(pack_nib, "document"),
    "car": PackerSpec(pack_car, "document"),
    "ole": PackerSpec(
        pack_ole,
        "document",
        {
            "ole_recompress": "ole_recompress",
            "ole_embedded_recompress": "ole_embedded_recompress",
            "ole_deduplicate_images": "ole_deduplicate_images",
        },
    ),
    "jpg": PackerSpec(
        pack_jpg,
        "image",
        {
            "jpeg_quality": "jpeg_quality",
            "keep_meta": "keep_meta",
        },
    ),
    "png": PackerSpec(
        pack_png,
        "image",
        {
            "png_quality": "png_quality",
            "ultra": "ultra",
            "keep_meta": "keep_meta",
        },
    ),
    "gif": PackerSpec(pack_gif, "image"),
    "webp": PackerSpec(pack_webp, "image"),
    "svg": PackerSpec(pack_svg, "image", {"keep_meta": "keep_meta"}),
    "svgz": PackerSpec(pack_svgz, "image"),
    "tif": PackerSpec(pack_tif, "image"),
    "tiff": PackerSpec(pack_tif, "image"),
    "jxl": PackerSpec(pack_jxl, "image"),
    "jp2": PackerSpec(pack_jp2, "image"),
    "j2k": PackerSpec(pack_jp2, "image"),
    "jpf": PackerSpec(pack_jp2, "image"),
    "jpx": PackerSpec(pack_jp2, "image"),
    "exr": PackerSpec(pack_exr, "image"),
    "dng": PackerSpec(pack_dng, "image"),
    "dcm": PackerSpec(pack_dcm, "image"),
    "dicom": PackerSpec(pack_dcm, "image"),
    "dic": PackerSpec(pack_dcm, "image"),
    "ico": PackerSpec(pack_ico, "image"),
    "icns": PackerSpec(pack_icns, "image"),
    "bmp": PackerSpec(pack_bmp, "image"),
    "tga": PackerSpec(pack_tga, "image"),
    "pnm": PackerSpec(pack_pnm, "image"),
    "pcx": PackerSpec(pack_pcx, "image"),
    "xml": PackerSpec(
        pack_xml,
        "document",
        {
            "keep_meta": "keep_meta",
            "ultra": "ultra",
            "jpeg_quality": "jpeg_quality",
            "png_quality": "png_quality",
        },
    ),
    "json": PackerSpec(pack_json, "document"),
    "jsonl": PackerSpec(pack_jsonl, "document"),
    "qgs": PackerSpec(pack_qgs, "document"),
    "qgd": PackerSpec(pack_qgd, "data"),
    "parquet": PackerSpec(pack_parquet, "data", {"ultra": "ultra"}),
    "orc": PackerSpec(pack_orc, "data"),
    "avro": PackerSpec(pack_avro, "data"),
    "feather": PackerSpec(pack_feather, "data"),
    "arrow": PackerSpec(pack_arrow, "data"),
    "ipc": PackerSpec(pack_arrow, "data"),
    "sqlite": PackerSpec(pack_sqlite, "data"),
    "duckdb": PackerSpec(pack_duckdb, "data"),
    "swf": PackerSpec(pack_swf, "image"),
    "tgs": PackerSpec(pack_tgs, "image"),
    "sqlite3": PackerSpec(pack_sqlite, "data"),
    "gpkg": PackerSpec(pack_sqlite, "data"),
    "mbtiles": PackerSpec(pack_sqlite, "data"),
    "h5": PackerSpec(pack_hdf5, "data"),
    "hdf5": PackerSpec(pack_hdf5, "data"),
    "hdf": PackerSpec(pack_hdf5, "data"),
    "nc": PackerSpec(pack_netcdf, "data"),
    "nc4": PackerSpec(pack_netcdf, "data"),
    "gz": PackerSpec(pack_gzip, "data"),
    "xz": PackerSpec(pack_xz, "data"),
    "bz2": PackerSpec(pack_bz2, "data"),
    "zst": PackerSpec(pack_zstd, "data"),
    "br": PackerSpec(pack_brotli, "data"),
    "lz4": PackerSpec(pack_lz4, "data"),
    "lz": PackerSpec(pack_lzip, "data"),
    "lzma": PackerSpec(pack_lzma, "data"),
    "lzo": PackerSpec(pack_lzo, "data"),
    "z": PackerSpec(pack_compress, "data"),
    "pdf": PackerSpec(
        pack_pdf,
        "document",
        {
            "pdf_profile": "pdf_profile",
            "pdf_linearize": "pdf_linearize",
            "jpeg_quality": "jpeg_quality",
            "keep_meta": "keep_meta",
            "ultra": "ultra",
        },
    ),
    "avif": PackerSpec(pack_avif, "image"),
    "heic": PackerSpec(pack_heic, "image"),
    "heif": PackerSpec(pack_heic, "image"),
    "flac": PackerSpec(pack_flac, "audio", {"keep_meta": "keep_meta"}),
    "m4a": PackerSpec(pack_m4a, "audio", {"keep_meta": "keep_meta"}),
    "wv": PackerSpec(pack_wv, "audio"),
    "ape": PackerSpec(pack_ape, "audio", {"keep_meta": "keep_meta"}),
    "tta": PackerSpec(pack_tta, "audio"),
    "oga": PackerSpec(pack_oga, "audio", {"keep_meta": "keep_meta"}),
    "ogg": PackerSpec(pack_ogg, "audio", {"keep_meta": "keep_meta"}),
    "mp3": PackerSpec(
        pack_mp3,
        "audio",
        {
            "ultra": "ultra",
            "keep_meta": "keep_meta",
        },
    ),
    "psd": PackerSpec(pack_psd, "image"),
    "psb": PackerSpec(pack_psb, "image"),
    "aseprite": PackerSpec(pack_aseprite, "image"),
    "blend": PackerSpec(pack_blend, "data"),
    "fits": PackerSpec(pack_fits, "data"),
    "nrrd": PackerSpec(pack_nrrd, "data"),
    "ai": PackerSpec(
        pack_ai,
        "document",
        {
            "pdf_profile": "pdf_profile",
            "pdf_linearize": "pdf_linearize",
            "jpeg_quality": "jpeg_quality",
        },
    ),
    "woff": PackerSpec(pack_woff, "data"),
    "woff2": PackerSpec(pack_woff2, "data"),
    "wmv": PackerSpec(
        pack_wmv,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "mp4": PackerSpec(
        pack_mp4,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "avi": PackerSpec(
        pack_avi,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "asf": PackerSpec(
        pack_asf,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "mkv": PackerSpec(pack_mkv, "video", {"wmv_lossless": "lossless"}),
    "webm": PackerSpec(pack_webm, "video", {"wmv_lossless": "lossless"}),
    "mov": PackerSpec(pack_mov, "video", {"wmv_lossless": "lossless"}),
    "m4v": PackerSpec(pack_m4v, "video", {"wmv_lossless": "lossless"}),
    "3gp": PackerSpec(
        pack_3gp,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "ts": PackerSpec(
        pack_ts,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "mts": PackerSpec(
        pack_ts,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
    "m2ts": PackerSpec(
        pack_ts,
        "video",
        {
            "wmv_lossless": "lossless",
            "convert_container": "convert_container",
        },
    ),
}


def dispatch_packer(ext: str, fullname: str, options: Dict[str, Any]) -> Optional[PackResult]:
    spec = _PACKERS.get(ext)
    if spec is None:
        record('unsupported', 'unknown_format', ext)
        return None
    if not category_enabled(spec.category, options):
        record('skipped', 'disabled_category', spec.category + ' processing is disabled')
        return None
    kwargs: Dict[str, Any] = {
        "debug": options.get("debug", False),
        "quiet": options.get("quiet", False),
        "dryrun": options.get("dryrun", False),
        "keep_if_larger": options.get("keep_if_larger", True),
        "min_savings": options.get("min_savings"),
        "lossy": options.get("lossy", False),
    }
    if ext in ('sqlite', 'sqlite3', 'gpkg', 'mbtiles'):
        kwargs['sqlite_offline'] = options.get('sqlite_offline', False)
    if spec.category == 'video':
        kwargs['video_mode'] = options.get('video_mode')
        kwargs['keep_meta'] = options.get('keep_meta', False)
    if ext in ('xml', 'pdf', 'ai') or spec.category == 'audio':
        kwargs['pack_images'] = embedded_images_enabled(options)
    for key in ('max_depth', '_optimization_depth', 'allow_categories', 'skip_categories'):
        if key in options:
            kwargs[key] = options[key]
    if ext in {
        'tracev3',
        "ole",
        "r-serialization",
        "mat",
        "checkpoint",
        "spss",
        "safetensors",
        "gguf",
        "onnx",
        "nib",
        "car",
        "warc",
        "h5",
        "hdf5",
        "hdf",
        "nc",
        "nc4",
        "tif",
        "tiff",
    }:
        for key in (
            'compression_level',
            "r_compression",
            "checkpoint_compatibility",
            "experimental_formats",
            "format_max_decoded_bytes",
            "format_max_memory_bytes",
            "format_max_scratch_bytes",
            "format_max_nodes",
            "format_max_depth",
            "format_timeout",
            "_cancel_event",
            "_nested_member",
            "_warc_index_source",
        ):
            if key in options:
                kwargs[key] = options[key]
    if ext == "ole":
        kwargs.update(
            ultra=options.get("ultra", False),
            pack_images=options.get("pack_images", True),
            pack_archives=options.get("pack_archives", True),
            deep=options.get("deep_walking", True),
        )
    for opt_key, arg_name in spec.extra.items():
        kwargs[arg_name] = (
            options.get(opt_key, False)
            if opt_key
            in (
                "pdf_linearize",
                "ole_recompress",
                "ole_embedded_recompress",
                "ole_deduplicate_images",
            )
            else (options.get(opt_key))
        )
    return spec.func(fullname, **kwargs)
