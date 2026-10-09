#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from multiprocessing import Manager
from os.path import basename, exists, isfile, join
from os import walk
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, cast, Callable

import typer

from .formats import is_supported_filename
from .destinations import same_file
from .jobs import JobRequest, JobResult, process_file_job
from .models import RepackOptions, RepackSummary
from .outcomes import RepackOutcome
from .reports import AuditReport, ResultSpool, identity
from .resume import ResumeManifest, execution_fingerprint
from .progress import ProgressReporter, stderr_is_tty
from .repack import FileRepacker, prepare_destination_plan
from .tools import doctor_rows, install_instructions
from .utils import (
    DEFAULT_EXCLUDE_DIRS,
    format_size,
    output_csv,
    output_json,
    parse_dir_names,
    parse_extensions,
    parse_jobs,
    parse_size,
    setup_logging,
    reset_logging,
    should_process_file,
)
from .validation import validate_progress_interval, validate_size_bounds

app = typer.Typer()

_output_format = None
_log_enabled = False
_active_report: Optional[AuditReport] = None
_report_failed = False
_verbose_level = 1  # 0=quiet, 1=normal, 2=verbose, 3=debug


def echo_verbose(message: str, level: int = 1, err: bool = False) -> None:
    """Echo message based on verbosity level; also write to the log file."""
    if _verbose_level >= level and (_output_format is None or err):
        typer.echo(message, err=err)
    if _log_enabled:
        logging.info(message) if level <= 2 else logging.debug(message)


def _status_label(status: str) -> str:
    if status in ('replaced', 'unchanged', 'predicted'):
        return '[SUCCESS]'
    if status == 'skipped':
        return '[SKIPPED]'
    if status == 'cancelled':
        return '[CANCELLED]'
    return '[ERROR]'


def _echo_outcome(outcome: RepackOutcome) -> None:
    failed = outcome.status in ('failed', 'unsupported', 'cancelled')
    reason = ': ' + outcome.reason if outcome.reason else ''
    echo_verbose(
        f'{_status_label(outcome.status)} {outcome.status} {outcome.source}{reason}',
        level=0 if failed else 1, err=failed,
    )


def _echo_diagnostics(reason: str, details: Dict[str, Any], status: str) -> None:
    if reason:
        label = 'Error' if status in ('failed', 'unsupported') else 'Info'
        echo_verbose(f"  {label}: {reason}", level=2)
    if details.get("strategy"):
        echo_verbose(f"  Strategy: {details['strategy']}", level=2)
    if details.get("recompression_skip"):
        echo_verbose(f"  Record recompression skipped: {details['recompression_skip']}", level=2)
    if details.get("storage_sharing_skip"):
        echo_verbose(f"  Storage sharing skipped: {details['storage_sharing_skip']}", level=2)
        echo_verbose(
            f"  PPT storage wrappers: {details.get('ppt_storage_count', 0)}; "
            f"distinct: {details.get('ppt_unique_storage_wrappers', 0)}; "
            f"duplicate bytes retained: {details.get('ppt_duplicate_wrapper_bytes', 0)}",
            level=2,
        )
    art = details.get("officeart", {})
    if art:
        echo_verbose(
            f"  OfficeArt: {art['metafile_count']} EMF/WMF payloads, "
            f"{art['recompressed_metafiles']} recompressed; "
            f"stream savings {art['stream_savings_bytes']} bytes; "
            f"encoders: {', '.join(art['encoders'])}",
            level=2,
        )
        echo_verbose(
            f"  OfficeArt rasters: {art.get('raster_count', 0)} PNG/JPEG payloads, "
            f"{art.get('recompressed_rasters', 0)} recompressed; "
            f"encoders: {', '.join(art.get('raster_encoders', []))}; "
            f"effort: {art.get('ole_effort', 'default')} "
            f"v{art.get('ole_effort_version', 1)}",
            level=2,
        )
        for reason in art.get("raster_skips", []):
            echo_verbose("  Raster skipped: " + reason, level=2)
        if art.get("effort_note"):
            echo_verbose("  OfficeArt effort: " + art["effort_note"], level=2)
    if (
        details.get("officeart_skip")
        and details["officeart_skip"] != details.get("recompression_skip")
    ):
        echo_verbose(f"  OfficeArt fallback: {details['officeart_skip']}", level=2)
    hwp = details.get("hwp", {})
    if hwp:
        echo_verbose(
            f"  HWP: {hwp.get('recompressed_streams', 0)} streams recompressed; "
            f"stream savings {hwp.get('stream_savings_bytes', 0)} bytes; "
            f"encoders: {', '.join(hwp.get('encoders', []))}; {hwp.get('effort_note', '')}",
            level=2,
        )
    for label, key in (("Embedded objects", "embedded"), ("Image deduplication", "deduplication")):
        report = details.get(key, {})
        if report:
            echo_verbose(f"  {label}: {report}", level=2)
    for key in ("embedded_skip", "deduplication_skip"):
        if details.get(key):
            echo_verbose(f"  {key.replace('_', ' ')}: {details[key]}", level=2)
    if details.get("additional_savings_bytes") is not None:
        echo_verbose(
            f"  Additional file savings beyond compaction: "
            f"{details['additional_savings_bytes']} bytes",
            level=2,
        )


def _set_verbosity(quiet: bool, verbose: bool, debug: bool) -> None:
    global _verbose_level, _log_enabled, _active_report, _report_failed
    _active_report = None
    _report_failed = False
    _log_enabled = False
    reset_logging()
    if quiet:
        _verbose_level = 0
    elif debug:
        _verbose_level = 3
    elif verbose:
        _verbose_level = 2
    else:
        _verbose_level = 1


def _set_output_format(json_flag: bool, csv_flag: bool) -> None:
    global _output_format
    if json_flag and csv_flag:
        typer.echo("[ERROR] --json and --csv are mutually exclusive.", err=True)
        raise typer.Exit(1)
    if json_flag:
        _output_format = "json"
    elif csv_flag:
        _output_format = "csv"
    else:
        _output_format = None


def _setup_log(log_file: Optional[str], debug: bool, verbose: bool) -> None:
    global _log_enabled
    _log_enabled = False
    if log_file:
        _log_enabled = True
        log_level = "DEBUG" if debug else "INFO"
        setup_logging(log_file, log_level)


def _finish_single_audit(row: Dict[str, Any]) -> None:
    global _active_report, _report_failed
    if _active_report is None:
        return
    sink, _active_report = _active_report, None
    try:
        sink.item(row)
        sink.finish({'complete': row.get('status') != 'cancelled',
                     'aborted': row.get('status') == 'cancelled', 'items': 1})
    except (OSError, ValueError) as exc:
        typer.echo('[ERROR] Report write failed: ' + str(exc), err=True)
        _report_failed = True
    finally:
        if not sink.closed:
            sink.stream.close()
            sink.closed = True


def _emit_terminal(outcome: RepackOutcome) -> None:
    row = outcome.to_dict()
    _finish_single_audit(row)
    if _output_format == 'json':
        output_json({**row, 'schema_version': 1, 'files': [row]})
    elif _output_format == 'csv':
        output_csv({'files': [row]})
    else:
        _echo_outcome(outcome)


def _build_options(
    *,
    ultra: bool,
    dryrun: bool,
    deep: bool,
    quiet: bool,
    debug: bool,
    no_images: bool,
    no_archives: bool,
    compression_level: int,
    jpeg_quality: Optional[int],
    png_quality: Optional[str],
    wmv_lossless: bool,
    video_mode: Optional[str] = None,
    profile: Optional[str] = None,
    explicit_options: Optional[List[str]] = None,
    tool_threads: int = 1,
    lossy: bool,
    convert_container: bool,
    keep_if_larger: bool,
    min_savings: Optional[float],
    max_extract_bytes: Optional[int] = None,
    max_extract_ratio: Optional[float] = None,
    pdf_profile: Optional[str] = None,
    pdf_linearize: bool = False,
    ole_recompress: bool = False,
    ole_embedded_recompress: bool = False,
    ole_deduplicate_images: bool = False,
    keep_meta: bool = False,
    r_compression: str = "preserve",
    checkpoint_compatibility: str = "preserve-mmap",
    experimental_formats: bool = False,
    sqlite_offline: bool = False,
    exclude_member: Optional[List[str]] = None,
    allow_category: Optional[List[str]] = None,
    skip_category: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
    format_max_decoded_bytes: int = 536870912,
    format_max_memory_bytes: int = 268435456,
    format_max_scratch_bytes: int = 2147483648,
    format_max_nodes: int = 100000,
    format_max_depth: int = 16,
    format_timeout: float = 120.0,
    overwrite: bool = False,
    backup: bool = False,
    backup_dir: Optional[str] = None,
) -> RepackOptions:
    options = RepackOptions(
        debug=debug,
        tool_threads=tool_threads,
        ultra=ultra,
        dryrun=dryrun,
        deep_walking=deep,
        quiet=quiet or _verbose_level == 0,
        pack_images=not no_images,
        pack_archives=not no_archives,
        compression_level=compression_level,
        jpeg_quality=jpeg_quality,
        png_quality=png_quality,
        pdf_profile=pdf_profile,
        pdf_linearize=pdf_linearize,
        ole_recompress=ole_recompress,
        ole_embedded_recompress=ole_embedded_recompress,
        ole_deduplicate_images=ole_deduplicate_images,
        wmv_lossless=wmv_lossless,
        video_mode=video_mode,
        profile=profile,
        lossy=lossy,
        convert_container=convert_container,
        keep_if_larger=keep_if_larger,
        min_savings=min_savings,
        max_extract_bytes=max_extract_bytes,
        max_extract_ratio=max_extract_ratio,
        keep_meta=keep_meta,
        r_compression=r_compression,
        checkpoint_compatibility=checkpoint_compatibility,
        experimental_formats=experimental_formats,
        sqlite_offline=sqlite_offline,
        exclude_members=exclude_member or [],
        allow_categories=allow_category,
        skip_categories=skip_category or [],
        max_depth=max_depth,
        format_max_decoded_bytes=format_max_decoded_bytes,
        format_max_memory_bytes=format_max_memory_bytes,
        format_max_scratch_bytes=format_max_scratch_bytes,
        format_max_nodes=format_max_nodes,
        format_max_depth=format_max_depth,
        format_timeout=format_timeout,
        overwrite=overwrite,
        backup=backup,
        backup_dir=backup_dir,
    )

    if profile:
        from .profiles import options_for_profile
        aliases = {'deep': 'deep_walking', 'no_images': 'pack_images',
                   'no_archives': 'pack_archives', 'allow_grow': 'keep_if_larger',
                   'exclude_member': 'exclude_members', 'allow_category': 'allow_categories',
                   'skip_category': 'skip_categories', 'file_timeout': 'format_timeout',
                   'max_temp_bytes': 'format_max_scratch_bytes'}
        values = options.to_dict()
        overrides = {aliases.get(key, key): values[aliases.get(key, key)]
                     for key in (explicit_options or []) if aliases.get(key, key) in values}
        options = options_for_profile(profile, **overrides)
    return options


def _parse_max_extract(value: Optional[str]):
    """Return (max_extract_bytes, max_extract_ratio) from --max-extract-size."""
    if value is None:
        return None, None
    size = parse_size(value)
    if size == 0:
        return 0, 0.0
    return size, None


def _validated_options_or_exit(
    *,
    min_size: Optional[str],
    max_size: Optional[str],
    max_extract_size: Optional[str],
    progress_interval: int,
    **settings: Any,
) -> Tuple[RepackOptions, Optional[int], Optional[int]]:
    try:
        minimum = parse_size(min_size) if min_size is not None else None
        maximum = parse_size(max_size) if max_size is not None else None
        validate_size_bounds(minimum, maximum)
        validate_progress_interval(progress_interval)
        max_bytes, max_ratio = _parse_max_extract(max_extract_size)
        options = _build_options(
            **settings,
            max_extract_bytes=max_bytes,
            max_extract_ratio=max_ratio,
        )
        return options, minimum, maximum
    except ValueError as exc:
        typer.echo(f"[ERROR] {exc}", err=True)
        raise typer.Exit(1)


def _want_progress(progress_flag: Optional[bool]) -> bool:
    """Progress is off for quiet/json/csv. Otherwise honor the flag, else TTY."""
    if _verbose_level == 0 or _output_format is not None:
        return False
    if progress_flag is False:
        return False
    if progress_flag is True:
        return True
    return stderr_is_tty()


@app.command()
def repack(
    ctx: typer.Context,
    filename: str = typer.Argument(..., help="Path to the file to repack"),
    ultra: bool = typer.Option(
        False,
        "--ultra",
        help="Stronger lossless passes (Parquet zstd 22, zopflipng, mp3packer -z)",
    ),
    dryrun: bool = typer.Option(False, "--dryrun", help="Do not modify files"),
    deep: bool = typer.Option(
        True, "--deep/--no-deep", help="Process nested archives and qualified OLE children"
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Quiet mode"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose mode"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    no_images: bool = typer.Option(
        False, "--no-images", help="Skip image, video, and audio optimization"
    ),
    no_archives: bool = typer.Option(False, "--no-archives", help="Skip nested archives"),
    min_savings: Optional[float] = typer.Option(
        None, "--min-savings", help="Min savings % to keep result"
    ),
    min_size: Optional[str] = typer.Option(None, "--min-size", help="Minimum file size (e.g. 1MB)"),
    max_size: Optional[str] = typer.Option(
        None, "--max-size", help="Maximum file size (e.g. 100MB)"
    ),
    backup: bool = typer.Option(False, "--backup", help="Create backup before processing"),
    backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Directory for backups"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Write result here"),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow replacing an existing output/conversion target",
    ),
    compression_level: int = typer.Option(9, "--compression-level", help="Compression 1-9"),
    jpeg_quality: Optional[int] = typer.Option(
        None, "--jpeg-quality", help="JPEG quality 1-100 (implies lossy)"
    ),
    png_quality: Optional[str] = typer.Option(
        None, "--png-quality", help="PNG quality high|medium|low (lossy)"
    ),
    pdf_profile: Optional[str] = typer.Option(
        None,
        "--pdf-profile",
        help="Ghostscript PDF profile: screen, ebook, printer, prepress, "
        "default (implies lossy; --lossy defaults to ebook)",
    ),
    pdf_linearize: bool = typer.Option(
        False,
        "--pdf-linearize",
        help="Require a linearized PDF (may increase size)",
    ),
    ole_recompress: bool = typer.Option(
        False,
        "--ole-recompress",
        help="Losslessly recompress qualified OfficeArt pictures, PPT wrappers and HWP streams",
    ),
    ole_embedded_recompress: bool = typer.Option(
        False,
        "--ole-embedded-recompress",
        help="Optimize qualified embedded OLE child files losslessly",
    ),
    ole_deduplicate_images: bool = typer.Option(
        False,
        "--ole-deduplicate-images",
        help="Merge identical images in qualified shared OLE stores",
    ),
    wmv_lossless: bool = typer.Option(False, "--wmv-lossless", help="Lossless video alias"),
    video_mode: Optional[str] = typer.Option(None, "--video-mode", help="remux|lossless|lossy"),
    profile: Optional[str] = typer.Option(None, "--profile", help="fast|balanced|maximum|preserve"),
    file_timeout: Optional[float] = typer.Option(None, "--file-timeout", help="Root deadline"),
    max_temp_bytes: Optional[int] = typer.Option(None, "--max-temp-bytes", help="Root scratch cap"),
    tool_threads: int = typer.Option(1, "--tool-threads", help="Threads per encoder"),
    lossy: bool = typer.Option(False, "--lossy", help="Allow lossy JPEG/PNG/PDF tools"),
    convert_container: bool = typer.Option(
        True,
        "--convert-container/--no-convert-container",
        help="Convert WMV/AVI/ASF to MP4 and plain WARC to .warc.gz (default: True)",
    ),
    allow_grow: bool = typer.Option(False, "--allow-grow", help="Keep result even if larger"),
    keep_meta: bool = typer.Option(
        False,
        "--keep-meta",
        help="Keep all JPEG/PNG metadata; presentation metadata is always retained",
    ),
    max_extract_size: Optional[str] = typer.Option(
        None,
        "--max-extract-size",
        help="Abort archive extract above this size (0 disables, default 8GB)",
    ),
    r_compression: str = typer.Option(
        "preserve",
        "--r-compression",
        help="preserve|gzip|bzip2|xz R envelope",
    ),
    checkpoint_compatibility: str = typer.Option(
        "preserve-mmap",
        "--checkpoint-compatibility",
        help="preserve-mmap|load-only; load-only disables mmap",
    ),
    experimental_formats: bool = typer.Option(
        False,
        "--experimental-formats",
        help="Enable pending MAT/ZSAV reader profiles",
    ),
    exclude_member: Optional[List[str]] = typer.Option(
        None, "--exclude-member", help="Repeatable POSIX member glob (*, **, ?) per archive root",
    ),
    allow_category: Optional[List[str]] = typer.Option(None, "--allow-category"),
    skip_category: Optional[List[str]] = typer.Option(None, "--skip-category"),
    max_depth: Optional[int] = typer.Option(
        None, "--max-depth", help="Optimization depth; root is 0",
    ),
    sqlite_offline: bool = typer.Option(
        False, "--sqlite-offline", help="Assert SQLite users are closed for in-place processing",
    ),
    format_max_decoded_bytes: int = typer.Option(
        536870912,
        "--format-max-decoded-bytes",
        help="Cumulative decoded bytes for preserving formats, including WARC",
    ),
    format_max_memory_bytes: int = typer.Option(
        268435456,
        "--format-max-memory-bytes",
        help="Worker RSS/buffer ceiling in bytes for preserving formats",
    ),
    format_max_scratch_bytes: int = typer.Option(
        2147483648,
        "--format-max-scratch-bytes",
        help="Cumulative scratch bytes for preserving formats, including WARC",
    ),
    format_max_depth: int = typer.Option(16, "--format-max-depth",
                                       help="Root security nesting limit"),
    format_max_nodes: int = typer.Option(
        100000,
        "--format-max-nodes",
        help="Cumulative graph/record ceiling for preserving formats",
    ),
    format_timeout: float = typer.Option(
        120.0,
        "--format-timeout",
        help="Preserving format operation deadline in seconds",
    ),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    csv: bool = typer.Option(False, "--csv", help="CSV output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write log to file"),
    report: Optional[str] = typer.Option(None, "--report", help="Local audit report destination"),
    report_format: Optional[str] = typer.Option(None, "--report-format", help="json|jsonl"),
    report_paths: str = typer.Option('absolute', "--report-paths",
                                     help="absolute|relative|redacted"),
    stats: bool = typer.Option(False, "--stats", help="Show detailed statistics"),
    progress: Optional[bool] = typer.Option(
        None,
        "--progress/--no-progress",
        help="Show a progress bar (default: on for a TTY; rich if installed)",
    ),
    progress_interval: int = typer.Option(
        10, "--progress-interval", help="Progress every N files if rich is missing"
    ),
):
    """Repack a single file for higher compression."""
    _set_verbosity(quiet, verbose, debug)
    _set_output_format(json, csv)

    if not exists(filename):
        typer.echo(f"[ERROR] File '{filename}' does not exist.", err=True)
        raise typer.Exit(1)
    if not isfile(filename):
        typer.echo(f"[ERROR] '{filename}' is not a file.", err=True)
        raise typer.Exit(1)

    options, min_size_bytes, max_size_bytes = _validated_options_or_exit(
        min_size=min_size,
        max_size=max_size,
        max_extract_size=max_extract_size,
        progress_interval=progress_interval,
        ultra=ultra,
        dryrun=dryrun,
        deep=deep,
        quiet=quiet,
        debug=debug,
        no_images=no_images,
        no_archives=no_archives,
        compression_level=compression_level,
        jpeg_quality=jpeg_quality,
        png_quality=png_quality,
        wmv_lossless=wmv_lossless,
        video_mode=video_mode,
        profile=profile,
        explicit_options=[key for key in ctx.params
                          if getattr(ctx.get_parameter_source(key), 'name', '') == 'COMMANDLINE'],
        tool_threads=tool_threads,
        lossy=lossy,
        convert_container=convert_container,
        keep_if_larger=not allow_grow,
        min_savings=min_savings,
        pdf_profile=pdf_profile,
        pdf_linearize=pdf_linearize,
        ole_recompress=ole_recompress,
        ole_embedded_recompress=ole_embedded_recompress,
        ole_deduplicate_images=ole_deduplicate_images,
        keep_meta=keep_meta,
        r_compression=r_compression,
        checkpoint_compatibility=checkpoint_compatibility,
        experimental_formats=experimental_formats,
        sqlite_offline=sqlite_offline,
        exclude_member=exclude_member,
        allow_category=allow_category,
        skip_category=skip_category,
        max_depth=max_depth,
        format_max_decoded_bytes=format_max_decoded_bytes,
        format_max_memory_bytes=format_max_memory_bytes,
        format_max_scratch_bytes=(max_temp_bytes if max_temp_bytes is not None
                                  else format_max_scratch_bytes),
        format_max_nodes=format_max_nodes,
        format_max_depth=format_max_depth,
        format_timeout=file_timeout if file_timeout is not None else format_timeout,
        overwrite=overwrite,
        backup=backup,
        backup_dir=backup_dir,
    )
    outfile = join(output_dir, basename(filename)) if output_dir else None
    if report:
        global _active_report
        try:
            plan = prepare_destination_plan(filename, outfile, options.to_dict(), check=False)
            if any(same_file(report, path) for path in plan.paths) or (
                log_file and same_file(report, log_file)
            ):
                raise ValueError('Report conflicts with source, destination, backup or log')
            _active_report = AuditReport(report, root=os.path.dirname(os.path.abspath(filename)),
                                         format=report_format, paths=report_paths,
                                         options=options.to_dict())
        except (OSError, ValueError) as exc:
            typer.echo('[ERROR] Report preflight failed: ' + str(exc), err=True)
            raise typer.Exit(1)
    should, reason = should_process_file(filename, min_size=min_size_bytes, max_size=max_size_bytes)
    if not should:
        _emit_terminal(RepackOutcome(filename, filename, 'skipped',
                                     reason_code='filtered', reason=reason))
        raise typer.Exit(1 if _report_failed else 0)

    outfile = join(output_dir, basename(filename)) if output_dir else None
    try:
        plan = prepare_destination_plan(filename, outfile, options.to_dict())
        if log_file and any(same_file(log_file, path) for path in plan.paths):
            raise ValueError("Log file conflicts with source, output or backup")
        _setup_log(log_file, debug, verbose)
    except (OSError, ValueError) as exc:
        _emit_terminal(RepackOutcome(filename, outfile or filename, 'failed',
                                     reason_code='preflight_failed', reason=str(exc)))
        raise typer.Exit(1)

    start_time = time.time()
    dr = FileRepacker()
    show_progress = _want_progress(progress)
    try:
        with ProgressReporter(
            show_progress,
            interval=progress_interval,
            description=f"Repacking {basename(filename)}",
        ) as bar:
            results = dr.repack_zip_file(
                filename,
                outfile=outfile,
                def_options=options,
                on_progress=bar.hook if show_progress else None,
            )
    except (OSError, ValueError) as exc:
        _emit_terminal(RepackOutcome(filename, outfile or filename, 'failed',
                                     reason_code='operation_error', reason=str(exc)))
        raise typer.Exit(1)
    except KeyboardInterrupt:
        _emit_terminal(RepackOutcome(filename, outfile or filename, 'cancelled',
                                     reason_code='interrupted', reason='User interrupted'))
        raise typer.Exit(130)
    elapsed_time = time.time() - start_time

    _emit_repack_report(results, filename, dryrun, stats, elapsed_time)


def _emit_repack_report(
    results: RepackSummary, filename: str, dryrun: bool, stats: bool, elapsed_time: float,
) -> None:
    assert results.outcome is not None
    output_data = {
        **results.outcome.to_dict(),
        "schema_version": 1,
        "file": filename,
        "members": [item.to_dict() for item in results.member_outcomes],
        "output_file": results.filepath,
        "original_size": results.total_insize,
        "final_size": results.total_outsize,
        "savings_percent": results.total_savings_pct,
        "savings_bytes": results.total_savings_bytes,
        "files_processed": len(results.results),
        "elapsed_time": elapsed_time,
        "files": [
            {
                "file": r.filepath,
                "original_size": r.insize,
                "final_size": r.outsize,
                "savings_percent": r.savings_pct,
                "savings_bytes": r.savings_bytes,
                "reason": r.reason,
                "reason_code": r.reason_code,
                "status": r.status,
                "source": r.source,
                "member": r.member,
                "published": r.published,
                "details": r.details,
            }
            for r in results.results
        ],
    }
    _finish_single_audit(output_data)
    if stats:
        output_data["stats"] = [results.inner_count, results.inner_insize, results.inner_outsize]

    if _output_format == "json":
        output_json(output_data)
    elif _output_format == "csv":
        output_csv({"files": results.results or [results.outcome.to_dict()]})
    else:
        delta = results.total_insize - results.total_outsize
        verb = (
            (
                "would shrink"
                if delta > 0
                else "would grow"
                if delta < 0
                else "would remain unchanged"
            )
            if dryrun
            else ("shrunk" if delta > 0 else "grew" if delta < 0 else "unchanged")
        )
        prefix = "[DRYRUN] " if dryrun else ""
        if _report_failed:
            echo_verbose('[ERROR] Command failed: audit report could not be written.',
                         level=0, err=True)
        elif results.outcome.status in ('replaced', 'unchanged', 'predicted'):
            echo_verbose(
                f"[SUCCESS] {prefix}File {filename} {verb} {results.total_insize} -> "
                f"{results.total_outsize} ({results.total_savings_pct:.2f}%)",
                level=1,
            )
        else:
            _echo_outcome(results.outcome)
        if results.results:
            echo_verbose("File results:", level=1)
            for fdata in results.results:
                status = fdata.status or results.outcome.status
                echo_verbose(
                    f"- {_status_label(status)} ({status}) {fdata.filepath}: "
                    f"{fdata.insize} -> {fdata.outsize} "
                    f"({fdata.savings_pct:.2f}%)",
                    level=1,
                )
                _echo_diagnostics(fdata.reason, fdata.details, status)
        if stats:
            echo_verbose("\nStatistics:", level=1)
            echo_verbose(f"  Processing time: {elapsed_time:.2f}s", level=1)
            echo_verbose(f"  Files processed: {len(results.results)}", level=1)

    if _report_failed or results.outcome.status in ('failed', 'unsupported'):
        raise typer.Exit(1)
    if results.outcome.status == 'cancelled':
        raise typer.Exit(130)


def _collect_bulk_files(
    directory: str, skip_dirs: set, skip_zip: bool, *, excluded: Iterable[str] = (),
) -> Iterator[str]:
    excluded_paths = {os.path.realpath(path) for path in excluded if path}
    for root, dirs, files in walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs and
                         not os.path.islink(join(root, d)) and
                         os.path.realpath(join(root, d)) not in excluded_paths)
        for file in sorted(files):
            full = join(root, file)
            if (os.path.realpath(full) in excluded_paths or os.path.islink(full) or
                file.endswith(('.bak', '.filerepack-lock'))):
                continue
            if is_supported_filename(file, peek_path=full):
                ext = file.rsplit(".", 1)[-1].lower() if "." in file else ""
                if not (skip_zip and ext == "zip"):
                    yield full


class _BulkAcc:
    def __init__(self, dryrun: bool, continue_on_error: bool):
        self.dryrun = dryrun
        self.continue_on_error = continue_on_error
        self.processed = self.failed = self.skipped = 0
        self.original_size = self.final_size = 0
        self.results = ResultSpool()
        self.audit: Optional[AuditReport] = None
        self.sink_error = False
        self.manifest: Optional[ResumeManifest] = None
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.abort = self.interrupted = False
        self.scan_complete = False
        self.fatal_error: Optional[str] = None
        self.counts: Dict[str, int] = {}
        self.resource_reservations: Dict[str, int] = {}

    def consume(self, result: Optional[JobResult], filepath: str) -> None:
        if not result:
            result = {"status": "failed", "file": filepath,
                      "reason_code": "missing_result", "reason": "Worker returned no result"}
        job = self.jobs.pop(filepath, None)
        if job and job.get('_resume_invalidated'):
            result.setdefault('details', {})['resume_invalidation'] = job['_resume_invalidated']
        if self.manifest:
            try:
                self.manifest.record(dict(result), job)
            except (OSError, ValueError) as exc:
                typer.echo('[ERROR] Manifest checkpoint failed: ' + str(exc), err=True)
                self.sink_error = self.abort = True
        status = result.get("status", "failed")
        self.counts[status] = self.counts.get(status, 0) + 1
        try:
            self.results.append(dict(result))
        except OSError as exc:
            self.results.preserve_drained(dict(result))
            if not self.sink_error:
                typer.echo('[ERROR] Result spool failed: ' + str(exc), err=True)
            self.sink_error = self.abort = True
        if self.audit:
            try:
                self.audit.item(dict(result))
            except (OSError, ValueError) as exc:
                typer.echo('[ERROR] Report write failed: ' + str(exc), err=True)
                self.sink_error = self.abort = True
        self.original_size += result.get("original_size", 0)
        self.final_size += result.get("final_size", result.get("original_size", 0))
        if status in ("replaced", "unchanged", "predicted"):
            self.processed += 1
            echo_verbose(f"  [SUCCESS] ({status}) {filepath}: "
                         f"{result.get('original_size', 0)} -> "
                         f"{result.get('final_size', 0)}", level=1)
            _echo_diagnostics(result.get("reason", ""), result.get("details", {}), status)
        elif status in ("skipped", "cancelled"):
            self.skipped += 1
            cancelled = status == 'cancelled'
            echo_verbose(f"  {_status_label(status)} {filepath}: {result.get('reason', '')}",
                         level=0 if cancelled else 1, err=cancelled)
        else:
            self.failed += 1
            echo_verbose(f"  [ERROR] ({status}) {filepath}: "
                         f"{result.get('reason', result.get('error', 'Failed'))}",
                         level=0, err=True)
            self.abort = self.abort or not self.continue_on_error


def _reserved_job(
    filepath: str, job_base: Dict[str, Any], reserved: set, acc: _BulkAcc,
) -> Tuple[Optional[Dict[str, Any]], Optional[JobResult]]:
    outfile = (join(job_base['output_dir'], os.path.relpath(filepath, job_base['base_directory']))
               if job_base.get('output_dir') else None)
    try:
        should, reason = should_process_file(
            filepath, min_size=job_base.get('min_size_bytes'),
            max_size=job_base.get('max_size_bytes'), include_exts=job_base.get('include_exts'),
            exclude_exts=job_base.get('exclude_exts'),
        )
        if not should:
            reserved.add(identity(filepath))
            size = os.path.getsize(filepath)
            return None, {'status': 'skipped', 'file': filepath, 'reason': reason,
                          'reason_code': 'filtered', 'original_size': size, 'final_size': size,
                          'published': False}
        from .jobs import _job_options
        plan = prepare_destination_plan(filepath, outfile,
                                        _job_options(cast(JobRequest, job_base)).to_dict(),
                                        check=False)
        identities = {os.path.realpath(path).casefold() for path in plan.paths}
        if identities & reserved:
            return None, {'status': 'failed', 'file': filepath, 'reason_code': 'conflict',
                          'reason': 'Source, destination or backup conflicts with another input'}
        reserved.update(identities)
        job = {**job_base, 'filepath': filepath, '_backup_path': plan.backup}
        if acc.manifest:
            reused = acc.manifest.prepare(job)
            if reused:
                return None, cast(JobResult, reused)
            acc.jobs[filepath] = job
        return job, None
    except (OSError, ValueError) as exc:
        return None, {'status': 'failed', 'file': filepath, 'reason_code': 'preflight_failed',
                      'reason': str(exc)}


def _submit_bulk_job(pool: Any, job: Dict[str, Any], filepath: str,
                     acc: _BulkAcc, pending: Dict[Any, str]) -> None:
    try:
        pending[pool.submit(process_file_job, job)] = filepath
    except Exception as exc:
        acc.consume({'status': 'failed', 'file': filepath, 'reason_code': 'dispatch_failed',
                     'reason': str(exc)}, filepath)
        acc.abort = True


def _run_bulk_jobs(
    all_files: Iterable[str], job_base: Dict[str, Any], job_count: int, acc: _BulkAcc,
    progress: bool, progress_interval: int,
) -> None:
    show_bar = bool(progress) and _verbose_level > 0 and _output_format is None
    iterator = iter(all_files)
    reserved: set = {identity(path) for path in acc.audit.protected_paths} if acc.audit else set()
    if acc.manifest:
        reserved.update(identity(path) for path in acc.manifest.protected_paths)
    with ProgressReporter(show_bar, interval=progress_interval, description="Repacking",
                          echo=lambda msg: echo_verbose(msg, level=1, err=True)) as bar:
        if job_count == 1:
            _run_serial_jobs(iterator, job_base, reserved, acc, bar)
            return
        with Manager() as manager:
            cancel = manager.Event()
            base = {**job_base, '_cancel_event': cancel}
            with ProcessPoolExecutor(max_workers=job_count) as pool:
                pending: Dict[Any, str] = {}
                while pending or not (acc.scan_complete or acc.abort):
                    try:
                        while (not acc.abort and not acc.scan_complete and
                               len(pending) < 2 * job_count):
                            try:
                                filepath = next(iterator)
                            except StopIteration:
                                acc.scan_complete = True
                                break
                            job, conflict = _reserved_job(filepath, base, reserved, acc)
                            if conflict:
                                acc.consume(conflict, filepath)
                            elif job:
                                _submit_bulk_job(pool, job, filepath, acc, pending)
                        if acc.abort:
                            cancel.set()
                            for future in pending:
                                future.cancel()
                        if not pending:
                            continue
                        done, _ = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                        for future in done:
                            filepath = pending.pop(future)
                            try:
                                result = (future.result() if not future.cancelled() else
                                          {'status': 'cancelled', 'file': filepath,
                                           'reason_code': 'cancelled',
                                           'reason': 'Cancelled before dispatch'})
                            except Exception as exc:
                                result = {'status': 'failed', 'file': filepath, 'reason': str(exc),
                                          'reason_code': 'worker_error'}
                            acc.consume(cast(JobResult, result), filepath)
                            bar.update(len(acc.results), name=filepath)
                    except KeyboardInterrupt:
                        acc.interrupted = acc.abort = True
                        cancel.set()
                    except Exception as exc:
                        acc.fatal_error = str(exc)
                        acc.abort = True
                        cancel.set()


def _run_serial_jobs(
    iterator: Iterator[str], job_base: Dict[str, Any], reserved: set,
    acc: _BulkAcc, bar: ProgressReporter,
) -> None:
    filepath = ''
    try:
        for filepath in iterator:
            job, conflict = _reserved_job(filepath, job_base, reserved, acc)
            acc.consume(conflict or process_file_job(job or {}), filepath)
            bar.update(len(acc.results), name=filepath)
            if acc.abort:
                return
        acc.scan_complete = True
    except KeyboardInterrupt:
        acc.interrupted = acc.abort = True
        if filepath:
            acc.consume({'status': 'cancelled', 'file': filepath,
                         'reason_code': 'interrupted', 'reason': 'User interrupted'}, filepath)
    except Exception as exc:
        acc.fatal_error = str(exc)
        acc.abort = True


def _emit_bulk_summary(acc: _BulkAcc, dryrun: bool, stats: bool, elapsed: float) -> None:
    saved = acc.original_size - acc.final_size
    percent = (saved * 100.0) / acc.original_size if acc.original_size else 0.0
    output_data = {
        "schema_version": 1,
        "summary": {
            "resource_reservations": acc.resource_reservations,
            "counts": acc.counts,
            "scan_complete": acc.scan_complete,
            "fatal_error": acc.fatal_error,
            "known_inputs": len(acc.results),
            "files_processed": acc.processed,
            "files_failed": acc.failed,
            "files_skipped": acc.skipped,
            "total_original_size": acc.original_size,
            "total_final_size": acc.final_size,
            "total_saved": saved,
            "actual_saved": sum(row.get('savings_bytes', 0) for row in acc.results
                                if row.get('status') == 'replaced' and row.get('published')),
            "predicted_saved": sum(row.get('savings_bytes', 0) for row in acc.results
                                   if row.get('status') == 'predicted'),
            "percent_saved": percent,
            "elapsed_time": elapsed,
        },
        "files": acc.results,
    }
    if _output_format == "json":
        typer.echo('{"schema_version":1,"summary":' + json.dumps(output_data['summary']) +
                   ',"files":[', nl=False)
        first = True
        for row in acc.results:
            typer.echo(('' if first else ',') + json.dumps(row), nl=False)
            first = False
        typer.echo(']}')
        return
    if _output_format == "csv":
        output_csv({"files": acc.results})
        return
    echo_verbose("\nSummary:", level=1)
    if acc.sink_error or acc.fatal_error:
        reason = acc.fatal_error or 'report or checkpoint output failed'
        echo_verbose('[ERROR] Bulk processing failed: ' + reason, level=0, err=True)
    elif acc.interrupted:
        echo_verbose('[CANCELLED] Bulk processing interrupted.', level=0, err=True)
    elif acc.failed:
        verb = 'completed with errors' if acc.scan_complete else 'stopped after an error'
        echo_verbose(f'[ERROR] Bulk processing {verb}.', level=0, err=True)
    else:
        prefix = '[DRYRUN] ' if dryrun else ''
        echo_verbose(f'[SUCCESS] {prefix}Bulk processing completed.', level=1)
    echo_verbose(f"  Files processed successfully: {acc.processed}", level=1)
    echo_verbose(f"  Files skipped: {acc.skipped}", level=1)
    echo_verbose(f"  Files failed: {acc.failed}", level=1)
    if acc.processed > 0:
        echo_verbose(f"  Original total size: {format_size(acc.original_size)}", level=1)
        echo_verbose(f"  Final total size: {format_size(acc.final_size)}", level=1)
        saved_label = "Space that would be saved" if dryrun else "Space saved"
        dry_tag = " [DRYRUN]" if dryrun else ""
        echo_verbose(
            f"  {saved_label}: {format_size(saved)} ({percent:.2f}%){dry_tag}",
            level=1,
        )
    if stats:
        echo_verbose("\nDetailed Statistics:", level=1)
        echo_verbose(f"  Processing time: {elapsed:.2f}s", level=1)
        if acc.processed > 0:
            echo_verbose(f"  Average time per file: {elapsed / acc.processed:.2f}s", level=1)
        if elapsed > 0:
            echo_verbose(
                f"  Processing rate: {acc.processed / elapsed:.2f} files/sec",
                level=1,
            )


@app.command("repack-store")
def repack_store_command(
    source: str = typer.Argument(..., help="Complete offline local Zarr v2 store"),
    output_dir: str = typer.Option(..., "--output-dir", help="Distinct output parent directory"),
    codec_policy: str = typer.Option(
        "preserve", "--codec-policy", help="preserve|compatible-upgrade (Blosc zstd)"
    ),
    dryrun: bool = typer.Option(False, "--dryrun", help="Inspect without encoding or staging"),
    min_savings: Optional[float] = typer.Option(None, "--min-savings"),
    format_max_decoded_bytes: int = typer.Option(536870912, "--format-max-decoded-bytes"),
    format_max_memory_bytes: int = typer.Option(268435456, "--format-max-memory-bytes"),
    format_max_scratch_bytes: int = typer.Option(2147483648, "--format-max-scratch-bytes"),
    format_max_nodes: int = typer.Option(100000, "--format-max-nodes"),
    format_timeout: float = typer.Option(120.0, "--format-timeout"),
    json: bool = typer.Option(False, "--json", help="JSON outcome with codec decisions"),
):
    """Publish a smaller complete Zarr store atomically without replacing existing output."""
    from .zarr_store import repack_store

    try:
        outcome = repack_store(
            source,
            output_dir,
            {
                "zarr_codec_policy": codec_policy,
                "dryrun": dryrun,
                "min_savings": min_savings,
                "format_max_decoded_bytes": format_max_decoded_bytes,
                "format_max_memory_bytes": format_max_memory_bytes,
                "format_max_scratch_bytes": format_max_scratch_bytes,
                "format_max_nodes": format_max_nodes,
                "format_timeout": format_timeout,
            },
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"[ERROR] {exc}", err=True)
        raise typer.Exit(1)
    if json:
        output_json(outcome.to_dict())
    else:
        typer.echo(
            f"{outcome.reason}: {outcome.input_bytes} -> {outcome.output_bytes} "
            f"({outcome.destination})"
        )


@app.command("inspect-dcp")
def inspect_dcp_command(
    source: str = typer.Argument(..., help="Flat local PyTorch DCP checkpoint directory"),
    format_max_nodes: int = typer.Option(100000, "--format-max-nodes"),
    format_timeout: float = typer.Option(120.0, "--format-timeout"),
    json: bool = typer.Option(False, "--json", help="JSON inventory"),
):
    """Inventory a DCP directory without loading its pickle metadata."""
    from .distributed_checkpoint import inspect_distributed_checkpoint

    try:
        outcome = inspect_distributed_checkpoint(
            source,
            {"format_max_nodes": format_max_nodes, "format_timeout": format_timeout},
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"[ERROR] {exc}", err=True)
        raise typer.Exit(1)
    if json:
        output_json(outcome)
    else:
        typer.echo(
            f"inspection-only: {outcome['shard_count']} shards, "
            f"{outcome['input_bytes']} bytes; completeness not verified"
        )
def _prepare_bulk_log(
    log_file: Optional[str], output_dir: Optional[str], directory: str,
    options: RepackOptions, discover: Callable[[], Iterator[str]], debug: bool, verbose: bool,
) -> None:
    if log_file:
        try:
            for filepath in discover():
                outfile = (
                    join(output_dir, os.path.relpath(filepath, directory)) if output_dir else None
                )
                plan = prepare_destination_plan(filepath, outfile, options.to_dict(), check=False)
                if any(same_file(log_file, path) for path in plan.paths):
                    raise ValueError("Log file conflicts with source, output or backup")
            _setup_log(log_file, debug, verbose)
        except (OSError, ValueError) as exc:
            typer.echo(f"[ERROR] {exc}", err=True)
            raise typer.Exit(1)
    else:
        _setup_log(None, debug, verbose)


def _finish_bulk_audit(acc: _BulkAcc) -> None:
    if acc.audit:
        try:
            acc.audit.finish({'complete': not acc.abort, 'aborted': acc.abort,
                              'scan_complete': acc.scan_complete, 'counts': acc.counts,
                              'items': len(acc.results)})
        except (OSError, ValueError) as exc:
            typer.echo('[ERROR] Report finalization failed: ' + str(exc), err=True)
            acc.sink_error = True


def _prepare_bulk_manifest(
    manifest: Optional[str], resume: bool, dryrun: bool, directory: str,
    output_dir: Optional[str], log_file: Optional[str], report: Optional[str],
    options: RepackOptions, discover: Callable[[], Iterator[str]],
    selection: Optional[Dict[str, Any]] = None,
) -> Optional[ResumeManifest]:
    if resume and not manifest:
        typer.echo('[ERROR] --resume requires --manifest', err=True)
        raise typer.Exit(1)
    if not manifest:
        return None
    try:
        for filepath in discover():
            target = join(output_dir, os.path.relpath(filepath, directory)) if output_dir else None
            plan = prepare_destination_plan(filepath, target, options.to_dict(), check=False)
            if any(same_file(manifest, path) for path in plan.paths):
                raise ValueError('Manifest conflicts with source, output or backup')
        if any(path and same_file(manifest, path) for path in (log_file, report)):
            raise ValueError('Manifest conflicts with report or log')
        fingerprint = execution_fingerprint({**options.to_dict(), 'bulk_selection': selection},
                                             directory, output_dir)
        return ResumeManifest(manifest, root=directory, fingerprint=fingerprint,
                               resume=resume, dryrun=dryrun)
    except (OSError, ValueError) as exc:
        typer.echo('[ERROR] Manifest preflight failed: ' + str(exc), err=True)
        raise typer.Exit(1)


def _prepare_bulk_audit(
    report: Optional[str], report_format: Optional[str], report_paths: str,
    directory: str, output_dir: Optional[str], log_file: Optional[str],
    options: RepackOptions, discover: Callable[[], Iterator[str]],
) -> Optional[AuditReport]:
    if report:
        try:
            for filepath in discover():
                target = (join(output_dir, os.path.relpath(filepath, directory))
                          if output_dir else None)
                plan = prepare_destination_plan(filepath, target, options.to_dict(), check=False)
                if any(same_file(report, path) for path in plan.paths):
                    raise ValueError('Report conflicts with source, destination or backup')
            if log_file and same_file(report, log_file):
                raise ValueError('Report conflicts with log')
            audit = AuditReport(report, root=directory, format=report_format, paths=report_paths,
                                options=options.to_dict())
            return audit
        except (OSError, ValueError) as exc:
            typer.echo('[ERROR] Report preflight failed: ' + str(exc), err=True)
            raise typer.Exit(1)
    return None


def _prepare_bulk_outputs(
    state: Optional[ResumeManifest], excluded: list, report: Optional[str],
    report_format: Optional[str], report_paths: str, directory: str,
    output_dir: Optional[str], log_file: Optional[str], options: RepackOptions,
    discover: Callable[[], Iterator[str]], debug: bool, verbose: bool,
) -> Optional[AuditReport]:
    audit = None
    try:
        audit = _prepare_bulk_audit(report, report_format, report_paths, directory,
                                    output_dir, log_file, options, discover)
        if audit:
            excluded.extend(audit.protected_paths)
        _prepare_bulk_log(log_file, output_dir, directory, options, discover, debug, verbose)
        return audit
    except BaseException:
        if state:
            state.close()
        if audit:
            try:
                audit.finish({'complete': False, 'aborted': True, 'items': 0,
                              'reason_code': 'preflight_failed'})
            except (OSError, ValueError):
                pass
        raise


def _bulk_slots_or_exit(jobs: int, options: RepackOptions, memory: int,
                        scratch: int, cpu: Optional[int]) -> Any:
    from .resource_slots import reserve_slots
    try:
        return reserve_slots(jobs, options, memory, scratch, cpu)
    except ValueError as exc:
        typer.echo('[ERROR] Resource reservation failed: ' + str(exc), err=True)
        raise typer.Exit(1)


@app.command()
def bulk(
    ctx: typer.Context,
    directory: str = typer.Argument(..., help="Directory to scan recursively"),
    skip_zip: bool = typer.Option(True, "--skip-zip/--no-skip-zip", help="Skip .zip files"),
    ultra: bool = typer.Option(
        False,
        "--ultra",
        help="Stronger lossless passes (Parquet zstd 22, zopflipng, mp3packer -z)",
    ),
    dryrun: bool = typer.Option(False, "--dryrun", help="Do not modify files"),
    deep: bool = typer.Option(
        True, "--deep/--no-deep", help="Process nested archives and qualified OLE children"
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Quiet mode"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose mode"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    no_images: bool = typer.Option(
        False, "--no-images", help="Skip image, video, and audio optimization"
    ),
    no_archives: bool = typer.Option(False, "--no-archives", help="Skip nested archives"),
    min_savings: Optional[float] = typer.Option(
        None, "--min-savings", help="Min savings % to keep result"
    ),
    min_size: Optional[str] = typer.Option(None, "--min-size", help="Minimum file size"),
    max_size: Optional[str] = typer.Option(None, "--max-size", help="Maximum file size"),
    include_ext: Optional[str] = typer.Option(None, "--include-ext", help="Extensions to include"),
    exclude_ext: Optional[str] = typer.Option(None, "--exclude-ext", help="Extensions to exclude"),
    exclude_dir: Optional[str] = typer.Option(
        None, "--exclude-dir", help="Extra directory names to skip (comma-separated)"
    ),
    backup: bool = typer.Option(False, "--backup", help="Create backup before processing"),
    backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Directory for backups"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Write results here"),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow replacing existing output/conversion targets",
    ),
    compression_level: int = typer.Option(9, "--compression-level", help="Compression 1-9"),
    jpeg_quality: Optional[int] = typer.Option(
        None, "--jpeg-quality", help="JPEG quality 1-100 (lossy)"
    ),
    png_quality: Optional[str] = typer.Option(
        None, "--png-quality", help="PNG quality high|medium|low (lossy)"
    ),
    pdf_profile: Optional[str] = typer.Option(
        None,
        "--pdf-profile",
        help="Ghostscript PDF profile: screen, ebook, printer, prepress, "
        "default (implies lossy; --lossy defaults to ebook)",
    ),
    pdf_linearize: bool = typer.Option(
        False,
        "--pdf-linearize",
        help="Require a linearized PDF (may increase size)",
    ),
    ole_recompress: bool = typer.Option(
        False,
        "--ole-recompress",
        help="Losslessly recompress qualified OfficeArt pictures, PPT wrappers and HWP streams",
    ),
    ole_embedded_recompress: bool = typer.Option(
        False,
        "--ole-embedded-recompress",
        help="Optimize qualified embedded OLE child files losslessly",
    ),
    ole_deduplicate_images: bool = typer.Option(
        False,
        "--ole-deduplicate-images",
        help="Merge identical images in qualified shared OLE stores",
    ),
    wmv_lossless: bool = typer.Option(False, "--wmv-lossless", help="Lossless video alias"),
    video_mode: Optional[str] = typer.Option(None, "--video-mode", help="remux|lossless|lossy"),
    profile: Optional[str] = typer.Option(None, "--profile", help="fast|balanced|maximum|preserve"),
    file_timeout: Optional[float] = typer.Option(None, "--file-timeout", help="Root deadline"),
    max_temp_bytes: Optional[int] = typer.Option(None, "--max-temp-bytes", help="Root scratch cap"),
    tool_threads: int = typer.Option(1, "--tool-threads", help="Threads per encoder"),
    lossy: bool = typer.Option(False, "--lossy", help="Allow lossy JPEG/PNG/PDF tools"),
    convert_container: bool = typer.Option(
        True,
        "--convert-container/--no-convert-container",
        help="Convert WMV/AVI/ASF to MP4 and plain WARC to .warc.gz (default: True)",
    ),
    allow_grow: bool = typer.Option(False, "--allow-grow", help="Keep result even if larger"),
    keep_meta: bool = typer.Option(
        False,
        "--keep-meta",
        help="Keep all JPEG/PNG metadata; presentation metadata is always retained",
    ),
    max_extract_size: Optional[str] = typer.Option(
        None,
        "--max-extract-size",
        help="Abort archive extract above this size (0 disables, default 8GB)",
    ),
    jobs: str = typer.Option("1", "--jobs", help="Parallel jobs (N or 'auto')"),
    bulk_max_memory_bytes: int = typer.Option(2147483648, '--bulk-max-memory-bytes'),
    bulk_max_scratch_bytes: int = typer.Option(8589934592, '--bulk-max-scratch-bytes'),
    bulk_max_cpu_threads: Optional[int] = typer.Option(None, '--bulk-max-cpu-threads'),
    continue_on_error: bool = typer.Option(
        False, "--continue-on-error", help="Do not stop on errors"
    ),
    progress: bool = typer.Option(
        False,
        "--progress",
        help="Show a progress bar (rich if installed, else every N files)",
    ),
    progress_interval: int = typer.Option(10, "--progress-interval", help="Progress every N files"),
    r_compression: str = typer.Option(
        "preserve",
        "--r-compression",
        help="preserve|gzip|bzip2|xz R envelope",
    ),
    checkpoint_compatibility: str = typer.Option(
        "preserve-mmap",
        "--checkpoint-compatibility",
        help="preserve-mmap|load-only; load-only disables mmap",
    ),
    experimental_formats: bool = typer.Option(
        False,
        "--experimental-formats",
        help="Enable pending MAT/ZSAV reader profiles",
    ),
    exclude_member: Optional[List[str]] = typer.Option(
        None, "--exclude-member", help="Repeatable POSIX member glob (*, **, ?) per archive root",
    ),
    allow_category: Optional[List[str]] = typer.Option(None, "--allow-category"),
    skip_category: Optional[List[str]] = typer.Option(None, "--skip-category"),
    max_depth: Optional[int] = typer.Option(
        None, "--max-depth", help="Optimization depth; root is 0",
    ),
    sqlite_offline: bool = typer.Option(
        False, "--sqlite-offline", help="Assert SQLite users are closed for in-place processing",
    ),
    format_max_decoded_bytes: int = typer.Option(
        536870912,
        "--format-max-decoded-bytes",
        help="Cumulative decoded bytes for preserving formats, including WARC",
    ),
    format_max_memory_bytes: int = typer.Option(
        268435456,
        "--format-max-memory-bytes",
        help="Worker RSS/buffer ceiling in bytes for preserving formats",
    ),
    format_max_scratch_bytes: int = typer.Option(
        2147483648,
        "--format-max-scratch-bytes",
        help="Cumulative scratch bytes for preserving formats, including WARC",
    ),
    format_max_depth: int = typer.Option(16, "--format-max-depth",
                                       help="Root security nesting limit"),
    format_max_nodes: int = typer.Option(
        100000,
        "--format-max-nodes",
        help="Cumulative graph/record ceiling for preserving formats",
    ),
    format_timeout: float = typer.Option(
        120.0,
        "--format-timeout",
        help="Preserving format operation deadline in seconds",
    ),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    csv: bool = typer.Option(False, "--csv", help="CSV output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write log to file"),
    manifest: Optional[str] = typer.Option(None, '--manifest', help='Completion checkpoint'),
    resume: bool = typer.Option(False, '--resume', help='Reuse content-verified completion'),
    report: Optional[str] = typer.Option(None, "--report", help="Local audit report destination"),
    report_format: Optional[str] = typer.Option(None, "--report-format", help="json|jsonl"),
    report_paths: str = typer.Option('absolute', "--report-paths",
                                     help="absolute|relative|redacted"),
    stats: bool = typer.Option(False, "--stats", help="Show detailed statistics"),
):
    """Recursively repack all supported files in a directory."""
    _set_verbosity(quiet, verbose, debug)
    _set_output_format(json, csv)

    if not exists(directory):
        typer.echo(f"[ERROR] Directory '{directory}' does not exist.", err=True)
        raise typer.Exit(1)
    if not os.path.isdir(directory):
        typer.echo(f"[ERROR] '{directory}' is not a directory.", err=True)
        raise typer.Exit(1)

    try:
        job_count = parse_jobs(jobs)
    except ValueError as exc:
        typer.echo(f"[ERROR] {exc}", err=True)
        raise typer.Exit(1)

    options, min_size_bytes, max_size_bytes = _validated_options_or_exit(
        min_size=min_size,
        max_size=max_size,
        max_extract_size=max_extract_size,
        progress_interval=progress_interval,
        ultra=ultra,
        dryrun=dryrun,
        deep=deep,
        quiet=quiet,
        debug=debug,
        no_images=no_images,
        no_archives=no_archives,
        compression_level=compression_level,
        jpeg_quality=jpeg_quality,
        png_quality=png_quality,
        wmv_lossless=wmv_lossless,
        video_mode=video_mode,
        profile=profile,
        explicit_options=[key for key in ctx.params
                          if getattr(ctx.get_parameter_source(key), 'name', '') == 'COMMANDLINE'],
        tool_threads=tool_threads,
        lossy=lossy,
        convert_container=convert_container,
        keep_if_larger=not allow_grow,
        min_savings=min_savings,
        pdf_profile=pdf_profile,
        pdf_linearize=pdf_linearize,
        ole_recompress=ole_recompress,
        ole_embedded_recompress=ole_embedded_recompress,
        ole_deduplicate_images=ole_deduplicate_images,
        keep_meta=keep_meta,
        r_compression=r_compression,
        checkpoint_compatibility=checkpoint_compatibility,
        experimental_formats=experimental_formats,
        sqlite_offline=sqlite_offline,
        exclude_member=exclude_member,
        allow_category=allow_category,
        skip_category=skip_category,
        max_depth=max_depth,
        format_max_decoded_bytes=format_max_decoded_bytes,
        format_max_memory_bytes=format_max_memory_bytes,
        format_max_scratch_bytes=(max_temp_bytes if max_temp_bytes is not None
                                  else format_max_scratch_bytes),
        format_max_nodes=format_max_nodes,
        format_max_depth=format_max_depth,
        format_timeout=file_timeout if file_timeout is not None else format_timeout,
        overwrite=overwrite,
        backup=backup,
        backup_dir=backup_dir,
    )
    slots = _bulk_slots_or_exit(job_count, options, bulk_max_memory_bytes,
                                bulk_max_scratch_bytes, bulk_max_cpu_threads)
    job_count = slots.granted
    include_exts = parse_extensions(include_ext) if include_ext else None
    exclude_exts = parse_extensions(exclude_ext) if exclude_ext else None
    skip_dirs = set(DEFAULT_EXCLUDE_DIRS) | parse_dir_names(exclude_dir)
    if dryrun:
        echo_verbose("[DRYRUN MODE] Files will not be modified.", level=1)

    echo_verbose(f"Scanning directory: {directory}", level=1)
    excluded = [path for path in (output_dir, backup_dir, manifest, report)
                if path and os.path.realpath(path) != os.path.realpath(directory)]
    def discover() -> Iterator[str]:
        return _collect_bulk_files(directory, skip_dirs, skip_zip, excluded=excluded)
    state = _prepare_bulk_manifest(manifest, resume, dryrun, directory, output_dir,
                                   log_file, report, options, discover,
                                   {'include': include_exts, 'exclude': exclude_exts,
                                    'min_size': min_size_bytes, 'max_size': max_size_bytes,
                                    'skip_dirs': sorted(skip_dirs), 'skip_zip': skip_zip})
    if state:
        excluded.extend(state.protected_paths)
    audit = _prepare_bulk_outputs(state, excluded, report, report_format, report_paths,
                                  directory, output_dir, log_file, options, discover,
                                  debug, verbose)
    all_files = discover()
    if log_file:
        excluded.append(log_file)
    echo_verbose("Discovering inputs incrementally", level=1)
    if job_count > 1:
        echo_verbose(f"Using {job_count} parallel jobs", level=1)

    job_base = {
        "base_directory": directory,
        "ultra": ultra,
        "dryrun": dryrun,
        "deep": deep,
        "debug": debug,
        "no_images": no_images,
        "no_archives": no_archives,
        "min_savings": min_savings,
        "min_size_bytes": min_size_bytes,
        "max_size_bytes": max_size_bytes,
        "include_exts": include_exts,
        "exclude_exts": exclude_exts,
        "backup": backup,
        "backup_dir": backup_dir,
        "output_dir": output_dir,
        "overwrite": overwrite,
        "compression_level": compression_level,
        "jpeg_quality": jpeg_quality,
        "png_quality": png_quality,
        "pdf_profile": options.pdf_profile,
        "pdf_linearize": options.pdf_linearize,
        "ole_recompress": options.ole_recompress,
        "ole_embedded_recompress": options.ole_embedded_recompress,
        "ole_deduplicate_images": options.ole_deduplicate_images,
        "wmv_lossless": wmv_lossless,
        "lossy": lossy,
        "convert_container": convert_container,
        "keep_if_larger": not allow_grow,
        "keep_meta": keep_meta,
        "r_compression": options.r_compression,
        "checkpoint_compatibility": options.checkpoint_compatibility,
        "experimental_formats": options.experimental_formats,
        "sqlite_offline": options.sqlite_offline,
        "exclude_members": options.exclude_members,
        "allow_categories": options.allow_categories,
        "skip_categories": options.skip_categories,
        "max_depth": options.max_depth,
        "format_max_decoded_bytes": options.format_max_decoded_bytes,
        "format_max_memory_bytes": options.format_max_memory_bytes,
        "format_max_scratch_bytes": options.format_max_scratch_bytes,
        "format_max_nodes": options.format_max_nodes,
        "format_max_depth": options.format_max_depth,
        "format_timeout": options.format_timeout,
        "max_extract_bytes": options.max_extract_bytes,
        "max_extract_ratio": options.max_extract_ratio,
    }
    effective = options.to_dict()
    job_base.update({key: value for key, value in effective.items()
                     if key in job_base or key in ('profile', 'profile_version', 'tool_threads',
                                                  'video_mode')})
    job_base.update(deep=options.deep_walking, no_images=not options.pack_images,
                    no_archives=not options.pack_archives)
    acc = _BulkAcc(dryrun, continue_on_error)
    acc.resource_reservations = slots.to_dict()
    acc.audit = audit
    acc.manifest = state
    start_time = time.time()
    try:
        _run_bulk_jobs(all_files, job_base, job_count, acc, progress, progress_interval)
        _finish_bulk_audit(acc)
        _emit_bulk_summary(acc, dryrun, stats, time.time() - start_time)
    finally:
        if audit and not audit.closed:
            acc.abort = True
            _finish_bulk_audit(acc)
        acc.results.close()
        if state:
            state.close()
    if acc.sink_error or acc.fatal_error:
        raise typer.Exit(1)

    if acc.interrupted:
        raise typer.Exit(130)
    if acc.failed and not continue_on_error:
        raise typer.Exit(1)
    if acc.failed:
        raise typer.Exit(2)


@app.command('inspect')
def inspect_command(
    path: str = typer.Argument(...),
    json_flag: bool = typer.Option(False, '--json'),
    output_dir: Optional[str] = typer.Option(None, '--output-dir'),
    overwrite: bool = typer.Option(False, '--overwrite'),
    backup: bool = typer.Option(False, '--backup'),
    backup_dir: Optional[str] = typer.Option(None, '--backup-dir'),
    profile: Optional[str] = typer.Option(None, '--profile'),
    sqlite_offline: bool = typer.Option(False, '--sqlite-offline'),
) -> None:
    """Read-only eligibility planning; directory JSON is a JSONL item stream."""
    from .inspection import inspect_file
    from .profiles import options_for_profile
    if not exists(path):
        typer.echo('[ERROR] path does not exist', err=True)
        raise typer.Exit(1)
    overrides: Dict[str, Any] = dict(overwrite=overwrite, backup=backup, backup_dir=backup_dir,
                                     sqlite_offline=sqlite_offline)
    try:
        options = (options_for_profile(profile, **overrides) if profile else
                   RepackOptions(**overrides))
        directory = os.path.isdir(path)
        files = (_collect_bulk_files(path, set(DEFAULT_EXCLUDE_DIRS), False,
                                     excluded=[output_dir] if output_dir else ())
                 if directory else iter((path,)))
        count, blocked = 0, 0
        for filename in files:
            relative = os.path.relpath(filename, path) if directory else basename(filename)
            target = join(output_dir, relative) if output_dir else None
            item = inspect_file(filename, target, options)
            count += 1
            blocked += int(item.eligibility == 'blocked')
            if json_flag:
                if directory:
                    typer.echo(json.dumps(item.to_dict(), ensure_ascii=False))
                else:
                    output_json(item.to_dict())
            else:
                typer.echo(f'{item.source}: {item.format or "unknown"} — {item.eligibility}')
                for reason in item.blockers:
                    typer.echo('  ' + reason)
        if directory:
            summary = {'schema_version': 1, 'record_type': 'summary', 'items': count,
                       'blocked': blocked, 'scan_complete': True}
            if json_flag:
                typer.echo(json.dumps(summary))
            else:
                typer.echo(f'Inspected {count}; blocked {blocked}')
    except KeyboardInterrupt:
        if json_flag:
            typer.echo(json.dumps({'schema_version': 1, 'record_type': 'summary',
                                   'scan_complete': False}))
        raise typer.Exit(130)
    except (OSError, ValueError) as exc:
        typer.echo('[ERROR] Inspection failed: ' + str(exc), err=True)
        raise typer.Exit(1)


@app.command()
def doctor(json_flag: bool = typer.Option(False, '--json'),
           formats: bool = typer.Option(False, '--formats')):
    """Show available tools and OS-specific commands to install missing ones."""
    rows = doctor_rows()
    if json_flag:
        from .capabilities import format_capabilities
        output_json({'schema_version': 1, 'tools': rows,
                     'formats': [item.to_dict() for item in format_capabilities()]})
        if any(row['status'].startswith('missing (required)') for row in rows):
            raise typer.Exit(1)
        return
    if formats:
        from .capabilities import format_capabilities
        for item in format_capabilities():
            state = ('inspection-only' if item.inspection_only else
                     'experimental' if item.experimental else
                     'unavailable' if not item.writer or item.missing else 'available')
            typer.echo(f'{item.key}: {state}; validator={item.validator}; '
                       f'missing={", ".join(item.missing) or "none"}')
        if any(row['status'].startswith('missing (required)') for row in rows):
            raise typer.Exit(1)
        return
    tool_w = max(4, max((len(row["tool"]) for row in rows), default=4))
    status_w = max(6, max((len(row["status"]) for row in rows), default=6))
    path_w = max(4, max((len(row["path"] or "-") for row in rows), default=4))
    path_w = min(path_w, 48)
    typer.echo(f"{'tool':<{tool_w}}  {'status':<{status_w}}  {'path':<{path_w}}  purpose")
    missing_required = False
    missing_keys = []
    for row in rows:
        path = row["path"] or "-"
        if len(path) > path_w:
            path = path[: max(1, path_w - 3)] + "..."
        typer.echo(
            f"{row['tool']:<{tool_w}}  {row['status']:<{status_w}}  "
            f"{path:<{path_w}}  {row['purpose']}"
        )
        if not row["path"]:
            missing_keys.append(row["tool"])
        if row["status"].startswith("missing (required)"):
            missing_required = True
    hints = install_instructions(missing_keys)
    if hints:
        typer.echo("")
        typer.echo(hints, nl=False)
    if missing_required:
        raise typer.Exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
