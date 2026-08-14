#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from os.path import basename, exists, isfile, join
from os import walk
from typing import Any, Dict, List, Optional

import typer

from .formats import is_supported_filename
from .jobs import process_file_job
from .models import RepackOptions
from .progress import ProgressReporter, stderr_is_tty
from .repack import FileRepacker, normalize_pdf_profile
from .tools import doctor_rows, install_instructions
from .utils import (
    DEFAULT_EXCLUDE_DIRS, create_backup, format_size, output_csv, output_json,
    parse_dir_names, parse_extensions, parse_jobs, parse_size, setup_logging,
    should_process_file,
)

app = typer.Typer()

_output_format = None
_log_enabled = False
_verbose_level = 1  # 0=quiet, 1=normal, 2=verbose, 3=debug


def echo_verbose(message: str, level: int = 1, err: bool = False) -> None:
    """Echo message based on verbosity level; also write to the log file."""
    if _verbose_level >= level:
        typer.echo(message, err=err)
    if _log_enabled:
        logging.info(message) if level <= 2 else logging.debug(message)


def _set_verbosity(quiet: bool, verbose: bool, debug: bool) -> None:
    global _verbose_level
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
        typer.echo('Error: --json and --csv are mutually exclusive.', err=True)
        raise typer.Exit(1)
    if json_flag:
        _output_format = 'json'
    elif csv_flag:
        _output_format = 'csv'
    else:
        _output_format = None


def _setup_log(log_file: Optional[str], debug: bool, verbose: bool) -> None:
    global _log_enabled
    if log_file:
        _log_enabled = True
        log_level = 'DEBUG' if debug else 'INFO' if verbose else 'WARNING'
        setup_logging(log_file, log_level)


def _build_options(
    *, ultra: bool, dryrun: bool, deep: bool, quiet: bool, debug: bool,
    no_images: bool, no_archives: bool, compression_level: int,
    jpeg_quality: Optional[int], png_quality: Optional[str],
    wmv_lossless: bool, lossy: bool, convert_container: bool,
    keep_if_larger: bool, min_savings: Optional[float],
    max_extract_bytes: Optional[int] = None,
    max_extract_ratio: Optional[float] = None,
    pdf_profile: Optional[str] = None,
) -> RepackOptions:
    return RepackOptions(
        debug=debug,
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
        wmv_lossless=wmv_lossless,
        lossy=lossy,
        convert_container=convert_container,
        keep_if_larger=keep_if_larger,
        min_savings=min_savings,
        max_extract_bytes=max_extract_bytes,
        max_extract_ratio=max_extract_ratio,
    )


def _parse_max_extract(value: Optional[str]):
    """Return (max_extract_bytes, max_extract_ratio) from --max-extract-size."""
    if value is None:
        return None, None
    size = parse_size(value)
    if size == 0:
        return 0, 0.0
    return size, None


def _max_extract_or_exit(value: Optional[str]):
    try:
        return _parse_max_extract(value)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


def _pdf_profile_or_exit(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return normalize_pdf_profile(value)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
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
    filename: str = typer.Argument(..., help="Path to the file to repack"),
    ultra: bool = typer.Option(False, "--ultra", help="Ultra parquet compression"),
    dryrun: bool = typer.Option(False, "--dryrun", help="Do not modify files"),
    deep: bool = typer.Option(True, "--deep/--no-deep", help="Process nested archives"),
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
    min_size: Optional[str] = typer.Option(
        None, "--min-size", help="Minimum file size (e.g. 1MB)"
    ),
    max_size: Optional[str] = typer.Option(
        None, "--max-size", help="Maximum file size (e.g. 100MB)"
    ),
    backup: bool = typer.Option(False, "--backup", help="Create backup before processing"),
    backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Directory for backups"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Write result here"),
    compression_level: int = typer.Option(9, "--compression-level", help="Compression 1-9"),
    jpeg_quality: Optional[int] = typer.Option(
        None, "--jpeg-quality", help="JPEG quality 1-100 (implies lossy)"
    ),
    png_quality: Optional[str] = typer.Option(
        None, "--png-quality", help="PNG quality high|medium|low (lossy)"
    ),
    pdf_profile: Optional[str] = typer.Option(
        None, "--pdf-profile",
        help="Ghostscript PDF profile: screen, ebook, printer, prepress, "
             "default (implies lossy; --lossy defaults to ebook)",
    ),
    wmv_lossless: bool = typer.Option(False, "--wmv-lossless", help="Lossless video (CRF 0)"),
    lossy: bool = typer.Option(False, "--lossy", help="Allow lossy JPEG/PNG/PDF tools"),
    convert_container: bool = typer.Option(
        True, "--convert-container/--no-convert-container",
        help="Convert WMV/AVI/ASF to MP4 (default: True)",
    ),
    allow_grow: bool = typer.Option(False, "--allow-grow", help="Keep result even if larger"),
    max_extract_size: Optional[str] = typer.Option(
        None, "--max-extract-size",
        help="Abort archive extract above this size (0 disables, default 8GB)",
    ),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    csv: bool = typer.Option(False, "--csv", help="CSV output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write log to file"),
    stats: bool = typer.Option(False, "--stats", help="Show detailed statistics"),
    progress: Optional[bool] = typer.Option(
        None, "--progress/--no-progress",
        help="Show a progress bar (default: on for a TTY; rich if installed)",
    ),
    progress_interval: int = typer.Option(
        10, "--progress-interval", help="Progress every N files if rich is missing"
    ),
):
    """Repack a single file for higher compression."""
    _set_verbosity(quiet, verbose, debug)
    _setup_log(log_file, debug, verbose)
    _set_output_format(json, csv)

    if not exists(filename):
        typer.echo(f"Error: File '{filename}' does not exist.", err=True)
        raise typer.Exit(1)
    if not isfile(filename):
        typer.echo(f"Error: '{filename}' is not a file.", err=True)
        raise typer.Exit(1)

    min_size_bytes = parse_size(min_size) if min_size else None
    max_size_bytes = parse_size(max_size) if max_size else None
    should, reason = should_process_file(
        filename, min_size=min_size_bytes, max_size=max_size_bytes
    )
    if not should:
        echo_verbose(f"Skipping {filename}: {reason}", level=1)
        raise typer.Exit(0)

    if backup and not dryrun:
        backup_path = create_backup(filename, backup_dir)
        if backup_path:
            echo_verbose(f"Created backup: {backup_path}", level=2)
        else:
            echo_verbose("Warning: Failed to create backup", level=1, err=True)

    output_filepath = filename
    if output_dir and not dryrun:
        os.makedirs(output_dir, exist_ok=True)
        output_filepath = join(output_dir, basename(filename))
        if output_filepath != filename:
            from shutil import copy2
            copy2(filename, output_filepath)
            echo_verbose(f"Copied to output directory: {output_filepath}", level=2)

    max_extract_bytes, max_extract_ratio = _max_extract_or_exit(max_extract_size)
    pdf_profile = _pdf_profile_or_exit(pdf_profile)
    options = _build_options(
        ultra=ultra, dryrun=dryrun, deep=deep, quiet=quiet, debug=debug,
        no_images=no_images, no_archives=no_archives,
        compression_level=compression_level, jpeg_quality=jpeg_quality,
        png_quality=png_quality, wmv_lossless=wmv_lossless, lossy=lossy,
        convert_container=convert_container, keep_if_larger=not allow_grow,
        min_savings=min_savings, max_extract_bytes=max_extract_bytes,
        max_extract_ratio=max_extract_ratio, pdf_profile=pdf_profile,
    )

    start_time = time.time()
    dr = FileRepacker()
    target = output_filepath if output_filepath != filename else filename
    outfile = output_filepath if output_filepath != filename else None
    show_progress = _want_progress(progress)
    with ProgressReporter(
        show_progress,
        interval=progress_interval,
        description=f"Repacking {basename(filename)}",
    ) as bar:
        results = dr.repack_zip_file(
            target, outfile=outfile, def_options=options,
            on_progress=bar.hook if show_progress else None,
        )
    elapsed_time = time.time() - start_time

    output_data = {
        'file': filename,
        'original_size': results.total_insize,
        'final_size': results.total_outsize,
        'savings_percent': results.total_savings_pct,
        'savings_bytes': results.total_savings_bytes,
        'files_processed': len(results.results),
        'elapsed_time': elapsed_time,
        'files': [
            {
                'file': r.filepath,
                'original_size': r.insize,
                'final_size': r.outsize,
                'savings_percent': r.savings_pct,
                'savings_bytes': r.savings_bytes,
            }
            for r in results.results
        ],
    }
    if stats:
        output_data['stats'] = [
            results.inner_count, results.inner_insize, results.inner_outsize
        ]

    if _output_format == 'json':
        output_json(output_data)
    elif _output_format == 'csv':
        output_csv({'files': results.results})
    else:
        verb = "would shrink" if dryrun else "shrinked"
        prefix = "[DRYRUN] " if dryrun else ""
        echo_verbose(
            f"{prefix}File {filename} {verb} {results.total_insize} -> "
            f"{results.total_outsize} ({results.total_savings_pct:.2f}%)",
            level=1,
        )
        if results.results:
            echo_verbose('Files recompressed:', level=1)
            for fdata in results.results:
                echo_verbose(
                    f"- {fdata.filepath}: {fdata.insize} -> {fdata.outsize} "
                    f"({fdata.savings_pct:.2f}%)",
                    level=1,
                )
        if stats:
            echo_verbose("\nStatistics:", level=1)
            echo_verbose(f"  Processing time: {elapsed_time:.2f}s", level=1)
            echo_verbose(f"  Files processed: {len(results.results)}", level=1)


def _collect_bulk_files(directory: str, skip_dirs: set, skip_zip: bool) -> List[str]:
    found: List[str] = []
    for root, dirs, files in walk(directory):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            full = join(root, file)
            if is_supported_filename(file, peek_path=full):
                ext = file.rsplit('.', 1)[-1].lower() if '.' in file else ''
                if skip_zip and ext == 'zip':
                    continue
                found.append(full)
    return found


class _BulkAcc:
    def __init__(self, dryrun: bool, continue_on_error: bool):
        self.dryrun = dryrun
        self.continue_on_error = continue_on_error
        self.processed = 0
        self.failed = 0
        self.skipped = 0
        self.original_size = 0
        self.final_size = 0
        self.results: List[Dict[str, Any]] = []
        self.abort = False

    def consume(self, result: Optional[Dict[str, Any]], filepath: str) -> None:
        if not result:
            self.failed += 1
            echo_verbose(f"  x {filepath}: Failed to repack", level=1, err=True)
            self.abort = not self.continue_on_error
            return
        status = result.get('status')
        if status == 'processed':
            self.processed += 1
            self.original_size += result['original_size']
            self.final_size += result['final_size']
            self.results.append(result)
            tag = " [DRYRUN]" if self.dryrun else ""
            echo_verbose(
                f"  OK {filepath}: {result['original_size']} -> "
                f"{result['final_size']} ({result['savings_percent']:.2f}%){tag}",
                level=1,
            )
        elif status == 'skipped':
            self.skipped += 1
            echo_verbose(f"  skip {filepath}: {result.get('reason', '')}", level=2)
        else:
            self.failed += 1
            echo_verbose(
                f"  x {filepath}: {result.get('error', 'Failed')}",
                level=1, err=True,
            )
            self.abort = not self.continue_on_error


def _run_bulk_jobs(
    all_files: List[str], job_base: Dict[str, Any], job_count: int,
    acc: _BulkAcc, progress: bool, progress_interval: int,
) -> None:
    total = len(all_files)
    show_bar = bool(progress) and _verbose_level > 0 and _output_format is None
    with ProgressReporter(
        show_bar,
        interval=progress_interval,
        description="Repacking",
        echo=lambda msg: echo_verbose(msg, level=1),
    ) as bar:
        if show_bar:
            bar.set_stage("Repacking", total=total)
        if job_count > 1 and total > 1:
            with ProcessPoolExecutor(max_workers=job_count) as pool:
                future_map = {
                    pool.submit(
                        process_file_job, {**job_base, 'filepath': fp}
                    ): fp
                    for fp in all_files
                }
                done = 0
                for fut in as_completed(future_map):
                    fp = future_map[fut]
                    try:
                        acc.consume(fut.result(), fp)
                    except Exception as exc:
                        acc.consume(
                            {'status': 'failed', 'file': fp, 'error': str(exc)},
                            fp,
                        )
                    done += 1
                    bar.update(done, name=fp)
                    if acc.abort:
                        break
            return
        for i, filepath in enumerate(all_files, 1):
            acc.consume(
                process_file_job({**job_base, 'filepath': filepath}), filepath
            )
            bar.update(i, name=filepath)
            if acc.abort:
                break


def _emit_bulk_summary(acc: _BulkAcc, dryrun: bool, stats: bool, elapsed: float) -> None:
    saved = acc.original_size - acc.final_size
    percent = (saved * 100.0) / acc.original_size if acc.original_size else 0.0
    output_data = {
        'summary': {
            'files_processed': acc.processed,
            'files_failed': acc.failed,
            'files_skipped': acc.skipped,
            'total_original_size': acc.original_size,
            'total_final_size': acc.final_size,
            'total_saved': saved,
            'percent_saved': percent,
            'elapsed_time': elapsed,
        },
        'files': acc.results,
    }
    if _output_format == 'json':
        output_json(output_data)
        return
    if _output_format == 'csv':
        output_csv({'files': [r for r in acc.results if r.get('status') == 'processed']})
        return
    echo_verbose("\nSummary:", level=1)
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
            echo_verbose(
                f"  Average time per file: {elapsed / acc.processed:.2f}s", level=1
            )
        if elapsed > 0:
            echo_verbose(
                f"  Processing rate: {acc.processed / elapsed:.2f} files/sec",
                level=1,
            )


@app.command()
def bulk(
    directory: str = typer.Argument(..., help="Directory to scan recursively"),
    skip_zip: bool = typer.Option(
        True, "--skip-zip/--no-skip-zip", help="Skip .zip files"
    ),
    ultra: bool = typer.Option(False, "--ultra", help="Ultra parquet compression"),
    dryrun: bool = typer.Option(False, "--dryrun", help="Do not modify files"),
    deep: bool = typer.Option(True, "--deep/--no-deep", help="Process nested archives"),
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
    include_ext: Optional[str] = typer.Option(
        None, "--include-ext", help="Extensions to include"
    ),
    exclude_ext: Optional[str] = typer.Option(
        None, "--exclude-ext", help="Extensions to exclude"
    ),
    exclude_dir: Optional[str] = typer.Option(
        None, "--exclude-dir", help="Extra directory names to skip (comma-separated)"
    ),
    backup: bool = typer.Option(False, "--backup", help="Create backup before processing"),
    backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Directory for backups"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Write results here"),
    compression_level: int = typer.Option(9, "--compression-level", help="Compression 1-9"),
    jpeg_quality: Optional[int] = typer.Option(
        None, "--jpeg-quality", help="JPEG quality 1-100 (lossy)"
    ),
    png_quality: Optional[str] = typer.Option(
        None, "--png-quality", help="PNG quality high|medium|low (lossy)"
    ),
    pdf_profile: Optional[str] = typer.Option(
        None, "--pdf-profile",
        help="Ghostscript PDF profile: screen, ebook, printer, prepress, "
             "default (implies lossy; --lossy defaults to ebook)",
    ),
    wmv_lossless: bool = typer.Option(False, "--wmv-lossless", help="Lossless video (CRF 0)"),
    lossy: bool = typer.Option(False, "--lossy", help="Allow lossy JPEG/PNG/PDF tools"),
    convert_container: bool = typer.Option(
        True, "--convert-container/--no-convert-container",
        help="Convert WMV/AVI/ASF to MP4 (default: True)",
    ),
    allow_grow: bool = typer.Option(False, "--allow-grow", help="Keep result even if larger"),
    max_extract_size: Optional[str] = typer.Option(
        None, "--max-extract-size",
        help="Abort archive extract above this size (0 disables, default 8GB)",
    ),
    jobs: str = typer.Option("1", "--jobs", help="Parallel jobs (N or 'auto')"),
    continue_on_error: bool = typer.Option(
        False, "--continue-on-error", help="Do not stop on errors"
    ),
    progress: bool = typer.Option(
        False, "--progress",
        help="Show a progress bar (rich if installed, else every N files)",
    ),
    progress_interval: int = typer.Option(
        10, "--progress-interval", help="Progress every N files"
    ),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    csv: bool = typer.Option(False, "--csv", help="CSV output"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write log to file"),
    stats: bool = typer.Option(False, "--stats", help="Show detailed statistics"),
):
    """Recursively repack all supported files in a directory."""
    _set_verbosity(quiet, verbose, debug)
    _setup_log(log_file, debug, verbose)
    _set_output_format(json, csv)

    if not exists(directory):
        typer.echo(f"Error: Directory '{directory}' does not exist.", err=True)
        raise typer.Exit(1)
    if not os.path.isdir(directory):
        typer.echo(f"Error: '{directory}' is not a directory.", err=True)
        raise typer.Exit(1)

    try:
        job_count = parse_jobs(jobs)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    min_size_bytes = parse_size(min_size) if min_size else None
    max_size_bytes = parse_size(max_size) if max_size else None
    include_exts = parse_extensions(include_ext) if include_ext else None
    exclude_exts = parse_extensions(exclude_ext) if exclude_ext else None
    skip_dirs = set(DEFAULT_EXCLUDE_DIRS) | parse_dir_names(exclude_dir)
    max_extract_bytes, max_extract_ratio = _max_extract_or_exit(max_extract_size)
    pdf_profile = _pdf_profile_or_exit(pdf_profile)

    if dryrun:
        echo_verbose("[DRYRUN MODE] Files will not be modified.", level=1)

    echo_verbose(f"Scanning directory: {directory}", level=1)
    all_files = _collect_bulk_files(directory, skip_dirs, skip_zip)
    total_files = len(all_files)
    echo_verbose(f"Found {total_files} files to process", level=1)
    if job_count > 1:
        echo_verbose(f"Using {job_count} parallel jobs", level=1)

    job_base = {
        'base_directory': directory,
        'ultra': ultra,
        'dryrun': dryrun,
        'deep': deep,
        'debug': debug,
        'no_images': no_images,
        'no_archives': no_archives,
        'min_savings': min_savings,
        'min_size_bytes': min_size_bytes,
        'max_size_bytes': max_size_bytes,
        'include_exts': include_exts,
        'exclude_exts': exclude_exts,
        'backup': backup,
        'backup_dir': backup_dir,
        'output_dir': output_dir,
        'compression_level': compression_level,
        'jpeg_quality': jpeg_quality,
        'png_quality': png_quality,
        'pdf_profile': pdf_profile,
        'wmv_lossless': wmv_lossless,
        'lossy': lossy,
        'convert_container': convert_container,
        'keep_if_larger': not allow_grow,
        'max_extract_bytes': max_extract_bytes,
        'max_extract_ratio': max_extract_ratio,
    }
    acc = _BulkAcc(dryrun, continue_on_error)
    start_time = time.time()
    _run_bulk_jobs(
        all_files, job_base, job_count, acc, progress, progress_interval
    )
    _emit_bulk_summary(acc, dryrun, stats, time.time() - start_time)

    if acc.failed and not continue_on_error:
        raise typer.Exit(1)
    if acc.failed:
        raise typer.Exit(2)


@app.command()
def doctor():
    """Show available tools and OS-specific commands to install missing ones."""
    rows = doctor_rows()
    tool_w = max(4, max((len(row['tool']) for row in rows), default=4))
    status_w = max(6, max((len(row['status']) for row in rows), default=6))
    path_w = max(4, max((len(row['path'] or '-') for row in rows), default=4))
    path_w = min(path_w, 48)
    typer.echo(
        f"{'tool':<{tool_w}}  {'status':<{status_w}}  {'path':<{path_w}}  purpose"
    )
    missing_required = False
    missing_keys = []
    for row in rows:
        path = row['path'] or '-'
        if len(path) > path_w:
            path = path[: max(1, path_w - 3)] + '...'
        typer.echo(
            f"{row['tool']:<{tool_w}}  {row['status']:<{status_w}}  "
            f"{path:<{path_w}}  {row['purpose']}"
        )
        if not row['path']:
            missing_keys.append(row['tool'])
        if row['status'].startswith('missing (required)'):
            missing_required = True
    hints = install_instructions(missing_keys)
    if hints:
        typer.echo('')
        typer.echo(hints, nl=False)
    if missing_required:
        raise typer.Exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
