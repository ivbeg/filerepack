"""Shared request validation, before any filesystem mutation."""

import math
from typing import Any, Dict, Optional

from .consts import PDF_PROFILES
from .transactions import validate_durability


def normalize_pdf_profile(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    key = str(value).strip().lower().lstrip('/')
    if key not in PDF_PROFILES:
        raise ValueError(
            f'Unknown PDF profile {value!r}; expected one of ' + ', '.join(PDF_PROFILES)
        )
    return key


def _number(name: str, value: Any, low: float, high: Optional[float] = None,
            *, integer: bool = False) -> None:
    if value is None:
        return
    valid_type = type(value) is int if integer else type(value) in (int, float)
    if not valid_type or (type(value) is float and not math.isfinite(value)) or value < low or (
        high is not None and value > high
    ):
        limits = f'{low:g}–{high:g}' if high is not None else f'at least {low:g}'
        raise ValueError(f'{name} must be a finite {"integer" if integer else "number"} {limits}')


def validate_options(options: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(options)
    validate_durability(result.get('durability', 'atomic'))
    if result.get('compression_level', 9) is None:
        raise ValueError('compression_level must be an integer 1–9')
    _number('compression_level', result.get('compression_level', 9), 1, 9, integer=True)
    _number('jpeg_quality', result.get('jpeg_quality'), 1, 100, integer=True)
    _number('min_savings', result.get('min_savings'), 0, 100)
    _number('max_extract_bytes', result.get('max_extract_bytes'), 0, integer=True)
    _number('max_extract_ratio', result.get('max_extract_ratio'), 0)
    _number('max_depth', result.get('max_depth'), 0, integer=True)
    _number('format_max_depth', result.get('format_max_depth'), 0, integer=True)
    _validate_selection(result)
    video_mode(result)
    from .profiles import PROFILES, PROFILE_VERSION
    if result.get('profile') is not None and result['profile'] not in PROFILES:
        raise ValueError('profile must be fast, balanced, maximum or preserve')
    if result.get('profile_version') not in (None, PROFILE_VERSION):
        raise ValueError('unsupported profile version')
    _number('tool_threads', result.get('tool_threads', 1), 1, integer=True)
    for name in ('format_max_decoded_bytes', 'format_max_memory_bytes',
                 'format_max_scratch_bytes', 'format_max_nodes'):
        _number(name, result.get(name), 1, integer=True)
        if name in result and result[name] is None:
            raise ValueError(name + ' must be a positive integer')
    _number('format_timeout', result.get('format_timeout'), 0.001)
    if 'format_timeout' in result and result['format_timeout'] is None:
        raise ValueError('format_timeout must be positive')
    choices = {'r_compression': ('preserve', 'gzip', 'bzip2', 'xz'),
               'checkpoint_compatibility': ('preserve-mmap', 'load-only'),
               'zarr_codec_policy': ('preserve', 'compatible-upgrade')}
    for name, values in choices.items():
        if name in result and result[name] not in values:
            raise ValueError(name + ' must be one of ' + ', '.join(values))
    result['pdf_profile'] = normalize_pdf_profile(result.get('pdf_profile'))
    png = result.get('png_quality')
    if png is not None:
        if not isinstance(png, str) or png.strip().lower() not in ('high', 'medium', 'low'):
            raise ValueError('png_quality must be high, medium or low')
        result['png_quality'] = png.strip().lower()
    for name in ('overwrite', 'backup', 'dryrun', 'pdf_linearize', 'experimental_formats',
                 'sqlite_offline',
                 'ole_recompress', 'ole_embedded_recompress', 'ole_deduplicate_images'):
        if name in result and type(result[name]) is not bool:
            raise ValueError(f'{name} must be a boolean')
    return result


def video_mode(options: Dict[str, Any]) -> str:
    mode = options.get('video_mode')
    if mode is not None and mode not in ('remux', 'lossless', 'lossy'):
        raise ValueError('video_mode must be remux, lossless or lossy')
    if options.get('wmv_lossless') and mode not in (None, 'lossless'):
        raise ValueError('wmv_lossless conflicts with video_mode')
    if mode == 'lossy' and not options.get('lossy'):
        raise ValueError('video_mode=lossy requires explicit lossy permission')
    return mode or ('lossless' if options.get('wmv_lossless') else
                    'lossy' if options.get('lossy') else 'remux')


def _validate_selection(options: Dict[str, Any]) -> None:
    from .selection import CATEGORIES, _pattern
    for name in ('exclude_members', 'allow_categories', 'skip_categories'):
        values = options.get(name)
        if values is None:
            continue
        if not isinstance(values, (list, tuple)) or len(values) > 1024:
            raise ValueError(name + ' must be a list of at most 1024 strings')
        if name == 'exclude_members':
            for pattern in values:
                _pattern(pattern)
        elif any(value not in CATEGORIES for value in values):
            raise ValueError(name + ' must use image, audio, video, document or data')


def validate_size_bounds(minimum: Optional[int], maximum: Optional[int]) -> None:
    _number('min_size', minimum, 0, integer=True)
    _number('max_size', maximum, 0, integer=True)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError('min_size must not exceed max_size')


def validate_progress_interval(value: int) -> None:
    _number('progress_interval', value, 1, integer=True)
