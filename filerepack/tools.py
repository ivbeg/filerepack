# -*- coding: utf-8 -*-

"""Resolve external compression tools from env, config, and PATH."""

import os
from dataclasses import dataclass
from os.path import expanduser, exists
from shutil import which
from typing import Dict, List, Optional, Tuple


_CONFIG_CACHE: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class ToolSpec:
    key: str
    binaries: Tuple[str, ...]
    env: str
    required: bool
    purpose: str


TOOL_SPECS: Tuple[ToolSpec, ...] = (
    ToolSpec('szip', ('7zz', '7z'), 'FILEREPACK_7ZZ', True, 'archives (ZIP/7z/OOXML)'),
    ToolSpec('zip', ('zip',), 'FILEREPACK_ZIP', False, 'ZIP fallback for OOXML'),
    ToolSpec('unrar', ('unrar',), 'FILEREPACK_UNRAR', False, 'RAR extraction'),
    ToolSpec('rar', ('rar',), 'FILEREPACK_RAR', False, 'RAR recompression'),
    ToolSpec('jpegoptim', ('jpegoptim',), 'FILEREPACK_JPEGOPTIM', False, 'JPEG'),
    ToolSpec('pngquant', ('pngquant',), 'FILEREPACK_PNGQUANT', False, 'lossy PNG'),
    ToolSpec('oxipng', ('oxipng',), 'FILEREPACK_OXIPNG', False, 'lossless PNG'),
    ToolSpec('optipng', ('optipng',), 'FILEREPACK_OPTIPNG', False, 'lossless PNG'),
    ToolSpec('gifsicle', ('gifsicle',), 'FILEREPACK_GIFSICLE', False, 'GIF'),
    ToolSpec('dwebp', ('dwebp',), 'FILEREPACK_DWEBP', False, 'WebP decode'),
    ToolSpec('cwebp', ('cwebp',), 'FILEREPACK_CWEBP', False, 'WebP encode'),
    ToolSpec('svgo', ('svgo',), 'FILEREPACK_SVGO', False, 'SVG'),
    ToolSpec('scour', ('scour',), 'FILEREPACK_SCOUR', False, 'SVG fallback'),
    ToolSpec(
        'convert', ('magick', 'convert'), 'FILEREPACK_CONVERT', False,
        'TIFF/HEIC/AVIF',
    ),
    ToolSpec('tiffcp', ('tiffcp',), 'FILEREPACK_TIFFCP', False, 'TIFF fallback'),
    ToolSpec('gs', ('gs', 'gswin64c', 'gswin32c'), 'FILEREPACK_GS', False, 'lossy PDF'),
    ToolSpec('qpdf', ('qpdf',), 'FILEREPACK_QPDF', False, 'lossless PDF'),
    ToolSpec('ffmpeg', ('ffmpeg',), 'FILEREPACK_FFMPEG', False, 'video'),
    ToolSpec('pigz', ('pigz',), 'FILEREPACK_PIGZ', False, 'parallel gzip'),
    ToolSpec('xz', ('xz',), 'FILEREPACK_XZ', False, 'XZ'),
    ToolSpec('bzip2', ('bzip2',), 'FILEREPACK_BZIP2', False, 'BZ2'),
    ToolSpec('zstd', ('zstd',), 'FILEREPACK_ZSTD', False, 'Zstandard'),
    ToolSpec('brotli', ('brotli',), 'FILEREPACK_BROTLI', False, 'Brotli'),
    ToolSpec('avifenc', ('avifenc',), 'FILEREPACK_AVIFENC', False, 'AVIF encode'),
    ToolSpec('avifdec', ('avifdec',), 'FILEREPACK_AVIFDEC', False, 'AVIF decode'),
    ToolSpec('flac', ('flac',), 'FILEREPACK_FLAC', False, 'FLAC recompress'),
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
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
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
    for path in _config_paths():
        if not exists(path):
            continue
        try:
            with open(path, 'rb') as fh:
                data = tomllib.load(fh)
            section = data.get('tools') or {}
            if isinstance(section, dict):
                tools = {str(k): str(v) for k, v in section.items() if v}
            break
        except (OSError, ValueError):
            continue
    _CONFIG_CACHE = tools
    return tools


def resolve_tool(key: str) -> Optional[str]:
    """Resolve a tool by spec key (e.g. 'szip', 'jpegoptim')."""
    spec = next((s for s in TOOL_SPECS if s.key == key), None)
    if spec is None:
        return which(key)

    env_val = os.environ.get(spec.env)
    if env_val:
        return env_val

    configured = _load_config_tools().get(key) or _load_config_tools().get(spec.binaries[0])
    if configured:
        return configured

    for name in spec.binaries:
        found = which(name)
        if found:
            return found
    return None


def resolve_szip() -> Optional[str]:
    return resolve_tool('szip')


def doctor_rows() -> List[Dict[str, str]]:
    """Rows for `filerepack doctor`: name, path, status, purpose."""
    rows = []
    for spec in TOOL_SPECS:
        path = resolve_tool(spec.key)
        if path:
            status = 'ok'
        elif spec.required:
            status = 'missing (required)'
        else:
            status = 'missing (optional)'
        rows.append({
            'tool': spec.key,
            'binaries': ', '.join(spec.binaries),
            'path': path or '',
            'status': status,
            'purpose': spec.purpose,
        })
    return rows
