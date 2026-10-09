# -*- coding: utf-8 -*-

"""Resolve external compression tools from env, config, and PATH."""

import os
from dataclasses import dataclass
from os.path import expanduser, exists
from shutil import which
from typing import Dict, List, Optional, Sequence, Tuple

from .install_hints import format_install_instructions, install_command


_CONFIG_CACHE: Optional[Dict[str, str]] = None
_CONFIG_SIGNATURE: Optional[Tuple[object, ...]] = None


@dataclass(frozen=True)
class ToolSpec:
    key: str
    binaries: Tuple[str, ...]
    env: str
    required: bool
    purpose: str


TOOL_SPECS: Tuple[ToolSpec, ...] = (
    ToolSpec('ole_compactor', ('filerepack-ole',), 'FILEREPACK_OLE_COMPACTOR',
             False, 'legacy DOC/XLS/PPT CFB compaction'),
    ToolSpec('szip', ('7zz', '7z'), 'FILEREPACK_7ZZ', True, 'archives (ZIP/7z/OOXML)'),
    ToolSpec('zip', ('zip',), 'FILEREPACK_ZIP', False, 'ZIP fallback for OOXML'),
    ToolSpec('unrar', ('unrar',), 'FILEREPACK_UNRAR', False, 'RAR extraction'),
    ToolSpec('rar', ('rar',), 'FILEREPACK_RAR', False, 'RAR recompression'),
    ToolSpec('jpegoptim', ('jpegoptim',), 'FILEREPACK_JPEGOPTIM', False, 'JPEG'),
    ToolSpec(
        'jpegtran', ('jpegtran',), 'FILEREPACK_JPEGTRAN', False,
        'JPEG (mozjpeg / libjpeg-turbo)',
    ),
    ToolSpec('pngquant', ('pngquant',), 'FILEREPACK_PNGQUANT', False, 'lossy PNG'),
    ToolSpec('oxipng', ('oxipng',), 'FILEREPACK_OXIPNG', False, 'lossless PNG'),
    ToolSpec(
        'zopflipng', ('zopflipng',), 'FILEREPACK_ZOPFLIPNG', False,
        'lossless PNG (ultra)',
    ),
    ToolSpec('optipng', ('optipng',), 'FILEREPACK_OPTIPNG', False, 'lossless PNG'),
    ToolSpec('gifsicle', ('gifsicle',), 'FILEREPACK_GIFSICLE', False, 'GIF'),
    ToolSpec('dwebp', ('dwebp',), 'FILEREPACK_DWEBP', False, 'WebP decode'),
    ToolSpec('cwebp', ('cwebp',), 'FILEREPACK_CWEBP', False, 'WebP encode'),
    ToolSpec('svgo', ('svgo',), 'FILEREPACK_SVGO', False, 'SVG'),
    ToolSpec('scour', ('scour',), 'FILEREPACK_SCOUR', False, 'SVG fallback'),
    ToolSpec(
        'convert', ('magick', 'convert'), 'FILEREPACK_CONVERT', False,
        'TIFF/HEIC/AVIF/BMP/TGA/PNM/PCX',
    ),
    ToolSpec('tiffcp', ('tiffcp',), 'FILEREPACK_TIFFCP', False, 'TIFF fallback'),
    ToolSpec('gs', ('gs', 'gswin64c', 'gswin32c'), 'FILEREPACK_GS', False, 'lossy PDF'),
    ToolSpec('qpdf', ('qpdf',), 'FILEREPACK_QPDF', False, 'lossless PDF'),
    ToolSpec('ffmpeg', ('ffmpeg',), 'FILEREPACK_FFMPEG', False, 'video'),
    ToolSpec('ffprobe', ('ffprobe',), 'FILEREPACK_FFPROBE', False, 'media inventory validation'),
    ToolSpec('pigz', ('pigz',), 'FILEREPACK_PIGZ', False, 'parallel gzip'),
    ToolSpec('xz', ('xz',), 'FILEREPACK_XZ', False, 'XZ'),
    ToolSpec('bzip2', ('bzip2',), 'FILEREPACK_BZIP2', False, 'BZ2'),
    ToolSpec('zstd', ('zstd',), 'FILEREPACK_ZSTD', False, 'Zstandard'),
    ToolSpec('brotli', ('brotli',), 'FILEREPACK_BROTLI', False, 'Brotli'),
    ToolSpec('lz4', ('lz4',), 'FILEREPACK_LZ4', False, 'LZ4'),
    ToolSpec('lzip', ('lzip',), 'FILEREPACK_LZIP', False, 'lzip'),
    ToolSpec('lzma', ('lzma',), 'FILEREPACK_LZMA', False, 'LZMA'),
    ToolSpec('lzop', ('lzop',), 'FILEREPACK_LZOP', False, 'LZO'),
    ToolSpec('compress', ('compress',), 'FILEREPACK_COMPRESS', False, 'Unix compress (.Z)'),
    ToolSpec('gzip', ('gzip',), 'FILEREPACK_GZIP', False, 'gzip / decompress .Z'),
    ToolSpec('avifenc', ('avifenc',), 'FILEREPACK_AVIFENC', False, 'AVIF encode'),
    ToolSpec('avifdec', ('avifdec',), 'FILEREPACK_AVIFDEC', False, 'AVIF decode'),
    ToolSpec('cjxl', ('cjxl',), 'FILEREPACK_CJXL', False, 'JPEG XL encode'),
    ToolSpec('djxl', ('djxl',), 'FILEREPACK_DJXL', False, 'JPEG XL decode'),
    ToolSpec('flac', ('flac',), 'FILEREPACK_FLAC', False, 'FLAC recompress'),
    ToolSpec('h5repack', ('h5repack',), 'FILEREPACK_H5REPACK', False, 'HDF5'),
    ToolSpec('nccopy', ('nccopy',), 'FILEREPACK_NCCOPY', False, 'NetCDF'),
    ToolSpec('mac', ('mac',), 'FILEREPACK_MAC', False, "Monkey's Audio"),
    ToolSpec(
        'woff2_compress', ('woff2_compress',), 'FILEREPACK_WOFF2_COMPRESS',
        False, 'WOFF2 encode',
    ),
    ToolSpec(
        'woff2_decompress', ('woff2_decompress',), 'FILEREPACK_WOFF2_DECOMPRESS',
        False, 'WOFF2 decode',
    ),
    ToolSpec(
        'mp3packer', ('mp3packer',), 'FILEREPACK_MP3PACKER',
        False, 'lossless MP3',
    ),
    ToolSpec(
        'optivorbis', ('optivorbis',), 'FILEREPACK_OPTIVORBIS',
        False, 'Ogg Vorbis/Opus',
    ),
    ToolSpec(
        'gdcmconv', ('gdcmconv',), 'FILEREPACK_GDCMCONV',
        False, 'DICOM JPEG-LS',
    ),
    ToolSpec(
        'dcmcjpls', ('dcmcjpls',), 'FILEREPACK_DCMCJPLS',
        False, 'DICOM JPEG-LS fallback',
    ),
)


def _config_paths() -> List[str]:
    paths = []
    xdg = os.environ.get('XDG_CONFIG_HOME')
    if xdg:
        paths.append(os.path.join(xdg, 'filerepack', 'config.toml'))
    paths.append(expanduser('~/.config/filerepack/config.toml'))
    paths.append(expanduser('~/.filerepack.toml'))
    return paths


def _load_config_tools() -> Dict[str, str]:
    global _CONFIG_CACHE, _CONFIG_SIGNATURE
    paths = _config_paths()
    signature: Tuple[object, ...] = tuple(_file_signature(path) for path in paths)
    if _CONFIG_CACHE is not None and signature == _CONFIG_SIGNATURE:
        return _CONFIG_CACHE
    tools: Dict[str, str] = {}
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            _CONFIG_CACHE = tools
            return tools
    for path in paths:
        if not exists(path):
            continue
        try:
            with open(path, 'rb') as fh:
                data = tomllib.load(fh)
            section = data.get('tools') or {}
            if isinstance(section, dict):
                tools = {str(k): str(v) for k, v in section.items() if v}
            break
        except (OSError, ValueError) as exc:
            from .outcomes import record
            record('failed', 'invalid_tool_config', str(exc))
            continue
    _CONFIG_CACHE = tools
    _CONFIG_SIGNATURE = signature
    return tools


def _file_signature(path: str) -> Tuple[object, ...]:
    try:
        stat = os.stat(path)
        return path, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except OSError:
        return path, None


def _executable(value: str, key: str) -> Optional[str]:
    path = which(expanduser(value))
    if path and os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    from .outcomes import record
    record('unsupported', 'invalid_tool_override', 'Configured executable is unavailable: ' + key)
    return None


def resolve_tool(key: str) -> Optional[str]:
    """Resolve a tool by spec key (e.g. 'szip', 'jpegoptim')."""
    spec = next((s for s in TOOL_SPECS if s.key == key), None)
    if spec is None:
        return which(key)

    env_val = os.environ.get(spec.env)
    if env_val:
        return _executable(env_val, key)

    configured = _load_config_tools().get(key) or _load_config_tools().get(spec.binaries[0])
    if configured:
        return _executable(configured, key)

    for name in spec.binaries:
        found = which(name)
        if found:
            return found
    from .outcomes import record
    record('unsupported', 'missing_tool', 'Required tool is unavailable: ' + key)
    return None


def resolve_szip() -> Optional[str]:
    return resolve_tool('szip')


def doctor_rows() -> List[Dict[str, str]]:
    """Rows for `filerepack doctor`: name, path, status, purpose, install."""
    rows = []
    for spec in TOOL_SPECS:
        path = resolve_tool(spec.key)
        version = probe_version(path, spec.key) if path else None
        if path:
            status = 'ok' if version else 'unverified executable'
        elif spec.required:
            status = 'missing (required)'
        else:
            status = 'missing (optional)'
        rows.append({
            'tool': spec.key,
            'binaries': ', '.join(spec.binaries),
            'path': path or '',
            'status': status,
            'version': version or '',
            'purpose': spec.purpose,
            'install': '' if path else install_command(spec.key),
        })
    return rows


def probe_version(path: str, key: str) -> Optional[str]:
    """Bounded read-only tool identity probe; availability is not writer qualification."""
    from .commands import capture_bytes
    flags = [] if key == 'szip' else ['-version' if key in ('ffmpeg', 'ffprobe') else '--version']
    raw = capture_bytes([path] + flags, max_output=65536, timeout=2)
    if raw:
        return raw.decode('utf-8', 'replace').strip().split('\n')[0][:300]
    return None


def install_instructions(
    missing_keys: Optional[Sequence[str]] = None,
    *,
    system: Optional[str] = None,
    managers: Optional[Sequence[str]] = None,
) -> str:
    """OS-specific install commands for missing tools (all missing if omitted)."""
    if missing_keys is None:
        missing_keys = [row['tool'] for row in doctor_rows() if not row['path']]
    return format_install_instructions(
        missing_keys, system=system, managers=managers,
    )
