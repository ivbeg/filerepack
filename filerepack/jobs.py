# -*- coding: utf-8 -*-

"""Picklable bulk worker used by ProcessPoolExecutor."""

import os
from typing import Any, Dict, List, Mapping, Optional, TypedDict, cast

from .models import RepackOptions
from .outcomes import Status
from .repack import FileRepacker
from .utils import should_process_file
from .validation import validate_size_bounds


class JobOptions(TypedDict, total=False):
    min_size_bytes: Optional[int]
    max_size_bytes: Optional[int]
    include_exts: Optional[List[str]]
    exclude_exts: Optional[List[str]]
    output_dir: Optional[str]
    base_directory: Optional[str]
    profile: Optional[str]
    profile_version: Optional[int]
    tool_threads: int
    debug: bool
    ultra: bool
    dryrun: bool
    deep: bool
    no_images: bool
    no_archives: bool
    compression_level: int
    jpeg_quality: Optional[int]
    png_quality: Optional[str]
    pdf_profile: Optional[str]
    pdf_linearize: bool
    ole_recompress: bool
    ole_embedded_recompress: bool
    ole_deduplicate_images: bool
    wmv_lossless: bool
    video_mode: Optional[str]
    lossy: bool
    convert_container: bool
    keep_if_larger: bool
    keep_meta: bool
    min_savings: Optional[float]
    max_extract_bytes: Optional[int]
    max_extract_ratio: Optional[float]
    overwrite: bool
    backup: bool
    r_compression: str
    checkpoint_compatibility: str
    experimental_formats: bool
    sqlite_offline: bool
    format_max_decoded_bytes: int
    format_max_memory_bytes: int
    format_max_scratch_bytes: int
    format_max_nodes: int
    format_max_depth: int
    format_timeout: float
    backup_dir: Optional[str]
    _cancel_event: Any
    _backup_path: Optional[str]
    exclude_members: List[str]
    allow_categories: Optional[List[str]]
    skip_categories: List[str]
    max_depth: Optional[int]


class JobRequest(JobOptions):
    filepath: str


class JobResult(TypedDict, total=False):
    status: Status
    file: str
    reason: str
    error: str
    details: Dict[str, Any]
    output_file: str
    original_size: int
    final_size: int
    savings_percent: float
    savings_bytes: int
    reason_code: str
    elapsed_time: float
    published: bool
    members: List[Dict[str, Any]]


def process_file_job(job: Mapping[str, object]) -> JobResult:
    """Process one file and return a result dictionary. No stdout."""
    # Keep accepting legacy dictionaries; option validation below must still
    # reject malformed values rather than coerce them at this boundary.
    return _process_file_job(cast(JobRequest, job))


def _process_file_job(job: JobRequest) -> JobResult:
    filepath = job['filepath']
    original_size = 0
    try:
        options = _job_options(job).to_dict()
        if job.get('_cancel_event') is not None:
            options['_cancel_event'] = job['_cancel_event']
            if job['_cancel_event'].is_set():
                return {'status': 'cancelled', 'file': filepath, 'reason_code': 'cancelled',
                        'reason': 'Cancelled before processing', 'published': False}
        if '_backup_path' in job:
            options['_backup_path'] = job['_backup_path']
        validate_size_bounds(job.get('min_size_bytes'), job.get('max_size_bytes'))
        original_size = os.path.getsize(filepath)
        should, reason = should_process_file(
            filepath,
            min_size=job.get('min_size_bytes'),
            max_size=job.get('max_size_bytes'),
            include_exts=job.get('include_exts'),
            exclude_exts=job.get('exclude_exts'),
        )
        if not should:
            return {'status': 'skipped', 'file': filepath, 'reason': reason,
                    'reason_code': 'filtered', 'original_size': original_size,
                    'final_size': original_size, 'published': False}

        output_dir = job.get('output_dir')
        base_directory = job.get('base_directory') or os.path.dirname(filepath)
        outfile = None
        if output_dir:
            rel_path = os.path.relpath(filepath, base_directory)
            if rel_path == '..' or rel_path.startswith('..' + os.sep):
                raise ValueError('Source is outside base_directory')
            outfile = os.path.join(output_dir, rel_path)
        results = FileRepacker(quiet=True).repack_zip_file(
            filepath, outfile=outfile, def_options=options,
        )
        if results is None:
            return {'status': 'failed', 'file': filepath, 'error': 'No results'}

        original_size = results.total_insize
        final_size = results.total_outsize
        savings = results.total_savings_pct

        assert results.outcome is not None
        return {
            'status': results.outcome.status,
            'file': filepath,
            'output_file': results.filepath,
            'original_size': original_size,
            'final_size': final_size,
            'savings_percent': savings,
            'savings_bytes': original_size - final_size,
            'reason': results.outcome.reason,
            'reason_code': results.outcome.reason_code,
            'elapsed_time': results.elapsed_seconds,
            'published': results.outcome.published,
            'members': [item.to_dict() for item in results.member_outcomes],
            'details': results.outcome.details,
        }
    except Exception as exc:
        cancelled = job.get('_cancel_event') is not None and job['_cancel_event'].is_set()
        return {'status': 'cancelled' if cancelled else 'failed', 'file': filepath,
                'error': str(exc), 'reason': str(exc),
                'reason_code': 'cancelled' if cancelled else 'operation_error', 'published': False,
                'original_size': original_size, 'final_size': original_size}


def _job_options(job: JobRequest) -> RepackOptions:
    if job.get('profile'):
        from .profiles import resolve_profile
        job = cast(JobRequest, resolve_profile(job.get('profile'), dict(job)))
    return RepackOptions(
        profile=job.get('profile'),
        profile_version=job.get('profile_version'),
        tool_threads=job.get('tool_threads', 1),
        debug=bool(job.get('debug')),
        ultra=bool(job.get('ultra')),
        dryrun=job.get('dryrun', False),
        deep_walking=bool(job.get('deep', True)),
        quiet=True,
        pack_images=not job.get('no_images', False),
        pack_archives=not job.get('no_archives', False),
        compression_level=job.get('compression_level', 9),
        jpeg_quality=job.get('jpeg_quality'),
        png_quality=job.get('png_quality'),
        pdf_profile=job.get('pdf_profile'),
        pdf_linearize=job.get('pdf_linearize', False),
        ole_recompress=job.get('ole_recompress', False),
        ole_embedded_recompress=job.get('ole_embedded_recompress', False),
        ole_deduplicate_images=job.get('ole_deduplicate_images', False),
        wmv_lossless=bool(job.get('wmv_lossless')),
        video_mode=job.get('video_mode'),
        lossy=bool(job.get('lossy')),
        convert_container=bool(job.get('convert_container', True)),
        keep_if_larger=bool(job.get('keep_if_larger', True)),
        keep_meta=bool(job.get('keep_meta', False)),
        r_compression=job.get('r_compression', 'preserve'),
        checkpoint_compatibility=job.get('checkpoint_compatibility', 'preserve-mmap'),
        experimental_formats=job.get('experimental_formats', False),
        sqlite_offline=job.get('sqlite_offline', False),
        exclude_members=job.get('exclude_members', []),
        allow_categories=job.get('allow_categories'),
        skip_categories=job.get('skip_categories', []),
        max_depth=job.get('max_depth'),
        format_max_decoded_bytes=job.get('format_max_decoded_bytes', 536870912),
        format_max_memory_bytes=job.get('format_max_memory_bytes', 268435456),
        format_max_scratch_bytes=job.get('format_max_scratch_bytes', 2147483648),
        format_max_nodes=job.get('format_max_nodes', 100000),
        format_max_depth=job.get('format_max_depth', 16),
        format_timeout=job.get('format_timeout', 120.0),

        min_savings=job.get('min_savings'),
        max_extract_bytes=job.get('max_extract_bytes'),
        max_extract_ratio=job.get('max_extract_ratio'),
        overwrite=job.get('overwrite', False),
        backup=job.get('backup', False),
        backup_dir=job.get('backup_dir'),
    )
