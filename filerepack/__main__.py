#!/usr/bin/env python
#-*- coding: utf-8 -*-

import os
import sys
import json
import time
from os.path import isfile, join, exists, dirname, basename
from os import walk
from typing import Optional, List
import typer
from .repack import FileRepacker
from .consts import SUPPORTED_EXTS
from .utils import (
    parse_size, format_size, parse_extensions, should_process_file,
    create_backup, output_json, output_csv, setup_logging
)

app = typer.Typer()

# Global variables for output format
_output_format = None
_output_file = None
_log_file = None
_verbose_level = 1  # 0=quiet, 1=normal, 2=verbose, 3=debug


def echo_verbose(message: str, level: int = 1, err: bool = False):
    """Echo message based on verbosity level."""
    if _verbose_level >= level:
        typer.echo(message, err=err)


@app.command()
def repack(
    filename: str = typer.Argument(..., help="Path to the file to repack"),
    ultra: bool = typer.Option(False, "--ultra", help="Use ultra compression level for parquet files (slower but better compression)"),
    dryrun: bool = typer.Option(False, "--dryrun", help="Calculate space savings without modifying files"),
    deep: bool = typer.Option(True, "--deep/--no-deep", help="Look deeper into archive files like zip or 7z files (default: True)"),
    quiet: bool = typer.Option(False, "--quiet", help="Quiet mode - minimal output"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose mode - detailed output"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode - maximum verbosity"),
    no_images: bool = typer.Option(False, "--no-images", help="Skip image optimization"),
    no_archives: bool = typer.Option(False, "--no-archives", help="Skip nested archive processing"),
    min_savings: Optional[float] = typer.Option(None, "--min-savings", help="Minimum savings percentage to process file (e.g., 5.0 for 5%%)"),
    min_size: Optional[str] = typer.Option(None, "--min-size", help="Minimum file size to process (e.g., '1MB')"),
    max_size: Optional[str] = typer.Option(None, "--max-size", help="Maximum file size to process (e.g., '100MB')"),
    backup: bool = typer.Option(False, "--backup", help="Create backup before processing"),
    backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Directory for backups"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for processed files"),
    compression_level: int = typer.Option(9, "--compression-level", help="Compression level 1-9 (1=fast, 9=best, default: 9)"),
    jpeg_quality: Optional[int] = typer.Option(None, "--jpeg-quality", help="JPEG quality 1-100 (default: 85)"),
    png_quality: Optional[str] = typer.Option(None, "--png-quality", help="PNG quality: high, medium, or low (default: high)"),
    wmv_lossless: bool = typer.Option(False, "--wmv-lossless", help="Use lossless compression for WMV files (default: lossy high-quality)"),
    json: bool = typer.Option(False, "--json", help="Output results in JSON format"),
    csv: bool = typer.Option(False, "--csv", help="Output results in CSV format"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write log to file"),
    stats: bool = typer.Option(False, "--stats", help="Show detailed statistics")
):
    """
    Repacks a single file for higher compression.
    """
    global _output_format, _output_file, _log_file, _verbose_level
    
    # Set verbosity level
    if quiet:
        _verbose_level = 0
    elif debug:
        _verbose_level = 3
    elif verbose:
        _verbose_level = 2
    else:
        _verbose_level = 1
    
    # Setup logging
    if log_file:
        _log_file = log_file
        log_level = 'DEBUG' if debug else 'INFO' if verbose else 'WARNING'
        setup_logging(log_file, log_level)
    
    # Set output format
    if json:
        _output_format = 'json'
    elif csv:
        _output_format = 'csv'
    
    if not exists(filename):
        typer.echo(f"Error: File '{filename}' does not exist.", err=True)
        raise typer.Exit(1)
    
    if not isfile(filename):
        typer.echo(f"Error: '{filename}' is not a file.", err=True)
        raise typer.Exit(1)
    
    # Parse size filters
    min_size_bytes = parse_size(min_size) if min_size else None
    max_size_bytes = parse_size(max_size) if max_size else None
    
    # Check if file should be processed
    should_process, reason = should_process_file(
        filename, min_size=min_size_bytes, max_size=max_size_bytes
    )
    if not should_process:
        echo_verbose(f"Skipping {filename}: {reason}", level=1)
        raise typer.Exit(0)
    
    # Create backup if requested
    backup_path = None
    if backup and not dryrun:
        backup_path = create_backup(filename, backup_dir)
        if backup_path:
            echo_verbose(f"Created backup: {backup_path}", level=2)
        else:
            echo_verbose("Warning: Failed to create backup", level=1, err=True)
    
    # Determine output file
    output_filepath = filename
    if output_dir and not dryrun:
        os.makedirs(output_dir, exist_ok=True)
        output_filepath = join(output_dir, basename(filename))
        if output_filepath != filename:
            from shutil import copy2
            copy2(filename, output_filepath)
            echo_verbose(f"Copied to output directory: {output_filepath}", level=2)
    
    # Build options
    options = {
        'debug': debug,
        'ultra': ultra,
        'dryrun': dryrun,
        'deep_walking': deep,
        'quiet': quiet or _verbose_level == 0,
        'pack_images': not no_images,
        'pack_archives': not no_archives,
        'compression_level': compression_level,
        'jpeg_quality': jpeg_quality,
        'png_quality': png_quality,
        'wmv_lossless': wmv_lossless
    }
    
    start_time = time.time()
    dr = FileRepacker()
    results = dr.repack_zip_file(output_filepath if output_filepath != filename else filename, 
                                outfile=output_filepath if output_filepath != filename else None,
                                def_options=options)
    
    if not results:
        typer.echo(f"Error: Failed to process {filename}", err=True)
        raise typer.Exit(1)
    
    # Check minimum savings
    if min_savings is not None and results.get('final'):
        savings = results['final'][2]
        if savings < min_savings:
            echo_verbose(f"Skipping {filename}: savings {savings:.2f}% < {min_savings}%", level=1)
            # Restore original if we modified it
            if output_filepath != filename and exists(output_filepath):
                os.remove(output_filepath)
            raise typer.Exit(0)
    
    elapsed_time = time.time() - start_time
    
    # Prepare output
    output_data = {
        'file': filename,
        'original_size': results['final'][0],
        'final_size': results['final'][1],
        'savings_percent': results['final'][2],
        'savings_bytes': results['final'][0] - results['final'][1],
        'files_processed': len(results.get('files', [])),
        'elapsed_time': elapsed_time
    }
    
    if stats:
        output_data['detailed_files'] = results.get('files', [])
        output_data['stats'] = results.get('stats', [0, 0, 0])
    
    # Output based on format
    if _output_format == 'json':
        output_json(output_data, _output_file)
    elif _output_format == 'csv':
        # For CSV, output file details
        csv_data = {'files': results.get('files', [])}
        output_csv(csv_data, _output_file)
    else:
        # Human-readable output
        if dryrun:
            echo_verbose(f"[DRYRUN] File {filename} would shrink {results['final'][0]} -> {results['final'][1]} ({results['final'][2]:.2f}%)", level=1)
        else:
            echo_verbose(f"File {filename} shrinked {results['final'][0]} -> {results['final'][1]} ({results['final'][2]:.2f}%)", level=1)
        
        if len(results['files']) > 0:
            echo_verbose('Files recompressed:', level=1)
            for fdata in results['files']:
                echo_verbose(f"- {fdata[0]}: {fdata[1]} -> {fdata[2]} ({fdata[3]:.2f}%)", level=1)
        
        if stats:
            echo_verbose(f"\nStatistics:", level=1)
            echo_verbose(f"  Processing time: {elapsed_time:.2f}s", level=1)
            echo_verbose(f"  Files processed: {len(results['files'])}", level=1)


@app.command()
def bulk(
    directory: str = typer.Argument(..., help="Directory path to recursively repack all supported files"),
    skip_zip: bool = typer.Option(True, "--skip-zip/--no-skip-zip", help="Skip files with .zip extension (default: True)"),
    ultra: bool = typer.Option(False, "--ultra", help="Use ultra compression level for parquet files (slower but better compression)"),
    dryrun: bool = typer.Option(False, "--dryrun", help="Calculate space savings without modifying files"),
    deep: bool = typer.Option(True, "--deep/--no-deep", help="Look deeper into archive files like zip or 7z files (default: True)"),
    quiet: bool = typer.Option(False, "--quiet", help="Quiet mode - minimal output"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose mode - detailed output"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode - maximum verbosity"),
    no_images: bool = typer.Option(False, "--no-images", help="Skip image optimization"),
    no_archives: bool = typer.Option(False, "--no-archives", help="Skip nested archive processing"),
    min_savings: Optional[float] = typer.Option(None, "--min-savings", help="Minimum savings percentage to process file (e.g., 5.0 for 5%%)"),
    min_size: Optional[str] = typer.Option(None, "--min-size", help="Minimum file size to process (e.g., '1MB')"),
    max_size: Optional[str] = typer.Option(None, "--max-size", help="Maximum file size to process (e.g., '100MB')"),
    include_ext: Optional[str] = typer.Option(None, "--include-ext", help="Comma-separated list of extensions to include (e.g., 'docx,xlsx,pptx')"),
    exclude_ext: Optional[str] = typer.Option(None, "--exclude-ext", help="Comma-separated list of extensions to exclude"),
    backup: bool = typer.Option(False, "--backup", help="Create backup before processing"),
    backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Directory for backups"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for processed files"),
    compression_level: int = typer.Option(9, "--compression-level", help="Compression level 1-9 (1=fast, 9=best, default: 9)"),
    jpeg_quality: Optional[int] = typer.Option(None, "--jpeg-quality", help="JPEG quality 1-100 (default: 85)"),
    png_quality: Optional[str] = typer.Option(None, "--png-quality", help="PNG quality: high, medium, or low (default: high)"),
    wmv_lossless: bool = typer.Option(False, "--wmv-lossless", help="Use lossless compression for WMV files (default: lossy high-quality)"),
    jobs: int = typer.Option(1, "--jobs", help="Number of parallel jobs (default: 1, use 'auto' for CPU count)"),
    continue_on_error: bool = typer.Option(False, "--continue-on-error", help="Continue processing after errors"),
    progress: bool = typer.Option(False, "--progress", help="Show progress indicator"),
    progress_interval: int = typer.Option(10, "--progress-interval", help="Update progress every N files"),
    json: bool = typer.Option(False, "--json", help="Output results in JSON format"),
    csv: bool = typer.Option(False, "--csv", help="Output results in CSV format"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Write log to file"),
    stats: bool = typer.Option(False, "--stats", help="Show detailed statistics")
):
    """
    Recursively repacks all supported files in the selected directory.
    """
    global _output_format, _output_file, _log_file, _verbose_level
    
    # Set verbosity level
    if quiet:
        _verbose_level = 0
    elif debug:
        _verbose_level = 3
    elif verbose:
        _verbose_level = 2
    else:
        _verbose_level = 1
    
    # Setup logging
    if log_file:
        _log_file = log_file
        log_level = 'DEBUG' if debug else 'INFO' if verbose else 'WARNING'
        setup_logging(log_file, log_level)
    
    # Set output format
    if json:
        _output_format = 'json'
    elif csv:
        _output_format = 'csv'
    
    if not exists(directory):
        typer.echo(f"Error: Directory '{directory}' does not exist.", err=True)
        raise typer.Exit(1)
    
    if not os.path.isdir(directory):
        typer.echo(f"Error: '{directory}' is not a directory.", err=True)
        raise typer.Exit(1)
    
    # Parse filters
    min_size_bytes = parse_size(min_size) if min_size else None
    max_size_bytes = parse_size(max_size) if max_size else None
    include_exts = parse_extensions(include_ext) if include_ext else None
    exclude_exts = parse_extensions(exclude_ext) if exclude_ext else None
    
    # Handle jobs
    if isinstance(jobs, str) and jobs.lower() == 'auto':
        try:
            import multiprocessing
            jobs = multiprocessing.cpu_count()
        except:
            jobs = 1
    
    if dryrun:
        echo_verbose("[DRYRUN MODE] Files will not be modified.", level=1)
    
    dr = FileRepacker()
    files_processed = 0
    files_failed = 0
    files_skipped = 0
    total_original_size = 0
    total_final_size = 0
    all_results = []
    start_time = time.time()
    
    # Collect all files first
    all_files = []
    echo_verbose(f"Scanning directory: {directory}", level=1)
    
    for root, dirs, files in walk(directory):
        for file in files:
            ext = file.rsplit('.', 1)[-1].lower() if '.' in file else ''
            if ext in SUPPORTED_EXTS:
                # Skip .zip files if skip_zip is True
                if skip_zip and ext == 'zip':
                    continue
                
                filepath = join(root, file)
                all_files.append(filepath)
    
    total_files = len(all_files)
    echo_verbose(f"Found {total_files} files to process", level=1)
    
    # Process files (sequential for now - parallel processing requires thread-safe FileRepacker)
    # Note: FileRepacker uses os.chdir which is not thread-safe, so parallel processing is disabled
    if jobs > 1:
        echo_verbose(f"Note: Parallel processing (--jobs) is not yet supported. Processing sequentially.", level=1)
    
    # Sequential processing
    for i, filepath in enumerate(all_files, 1):
        result = process_single_file(
            filepath, directory, dr, ultra, dryrun, deep, quiet, no_images, no_archives,
            min_savings, min_size_bytes, max_size_bytes, include_exts, exclude_exts,
            backup, backup_dir, output_dir, compression_level, jpeg_quality, png_quality, wmv_lossless
        )
        
        if result:
            if result['status'] == 'processed':
                files_processed += 1
                total_original_size += result['original_size']
                total_final_size += result['final_size']
                all_results.append(result)
            elif result['status'] == 'skipped':
                files_skipped += 1
            else:
                files_failed += 1
                if not continue_on_error:
                    echo_verbose(f"  ✗ {filepath}: {result.get('error', 'Failed')}", level=1, err=True)
                    continue
        else:
            files_failed += 1
            if not continue_on_error:
                echo_verbose(f"  ✗ {filepath}: Failed to repack", level=1, err=True)
                continue
        
        if progress and i % progress_interval == 0:
            echo_verbose(f"Progress: {i}/{total_files} files processed", level=1)
    
    elapsed_time = time.time() - start_time
    
    # Calculate space gains
    total_saved = total_original_size - total_final_size
    if total_original_size > 0:
        percent_saved = (total_saved * 100.0) / total_original_size
    else:
        percent_saved = 0.0
    
    # Prepare output
    output_data = {
        'summary': {
            'files_processed': files_processed,
            'files_failed': files_failed,
            'files_skipped': files_skipped,
            'total_original_size': total_original_size,
            'total_final_size': total_final_size,
            'total_saved': total_saved,
            'percent_saved': percent_saved,
            'elapsed_time': elapsed_time
        },
        'files': all_results
    }
    
    # Output based on format
    if _output_format == 'json':
        output_json(output_data, _output_file)
    elif _output_format == 'csv':
        # Flatten for CSV
        csv_data = {'files': [r for r in all_results if r.get('status') == 'processed']}
        output_csv(csv_data, _output_file)
    else:
        # Human-readable output
        echo_verbose(f"\nSummary:", level=1)
        echo_verbose(f"  Files processed successfully: {files_processed}", level=1)
        echo_verbose(f"  Files skipped: {files_skipped}", level=1)
        echo_verbose(f"  Files failed: {files_failed}", level=1)
        if files_processed > 0:
            echo_verbose(f"  Original total size: {format_size(total_original_size)}", level=1)
            echo_verbose(f"  Final total size: {format_size(total_final_size)}", level=1)
            if dryrun:
                echo_verbose(f"  Space that would be saved: {format_size(total_saved)} ({percent_saved:.2f}%) [DRYRUN]", level=1)
            else:
                echo_verbose(f"  Space saved: {format_size(total_saved)} ({percent_saved:.2f}%)", level=1)
        
        if stats:
            echo_verbose(f"\nDetailed Statistics:", level=1)
            echo_verbose(f"  Processing time: {elapsed_time:.2f}s", level=1)
            echo_verbose(f"  Average time per file: {elapsed_time / files_processed:.2f}s" if files_processed > 0 else "  Average time per file: N/A", level=1)
            echo_verbose(f"  Processing rate: {files_processed / elapsed_time:.2f} files/sec" if elapsed_time > 0 else "  Processing rate: N/A", level=1)


def process_single_file(
    filepath, base_directory, dr, ultra, dryrun, deep, quiet, no_images, no_archives,
    min_savings, min_size_bytes, max_size_bytes, include_exts, exclude_exts,
    backup, backup_dir, output_dir, compression_level, jpeg_quality, png_quality, wmv_lossless
):
    """Process a single file and return result dictionary."""
    try:
        # Check if file should be processed
        should_process, reason = should_process_file(
            filepath, min_size=min_size_bytes, max_size=max_size_bytes,
            include_exts=include_exts, exclude_exts=exclude_exts
        )
        if not should_process:
            return {'status': 'skipped', 'file': filepath, 'reason': reason}
        
        echo_verbose(f"Processing: {filepath}", level=2)
        
        # Create backup if requested
        backup_path = None
        if backup and not dryrun:
            backup_path = create_backup(filepath, backup_dir)
        
        # Determine output file
        output_filepath = filepath
        if output_dir and not dryrun:
            os.makedirs(output_dir, exist_ok=True)
            # Preserve directory structure
            rel_path = os.path.relpath(filepath, base_directory if os.path.isdir(base_directory) else os.path.dirname(base_directory))
            output_filepath = join(output_dir, rel_path)
            os.makedirs(dirname(output_filepath), exist_ok=True)
            if output_filepath != filepath:
                from shutil import copy2
                copy2(filepath, output_filepath)
        
        # Build options
        options = {
            'debug': False,
            'ultra': ultra,
            'dryrun': dryrun,
            'deep_walking': deep,
            'quiet': quiet,
            'pack_images': not no_images,
            'pack_archives': not no_archives,
            'compression_level': compression_level,
            'jpeg_quality': jpeg_quality,
            'png_quality': png_quality,
            'wmv_lossless': wmv_lossless
        }
        
        results = dr.repack_zip_file(
            output_filepath if output_filepath != filepath else filepath,
            outfile=output_filepath if output_filepath != filepath else None,
            def_options=options
        )
        
        if not results or 'final' not in results:
            return {'status': 'failed', 'file': filepath, 'error': 'No results returned'}
        
        original_size = results['final'][0]
        final_size = results['final'][1]
        savings = results['final'][2]
        
        # Check minimum savings
        if min_savings is not None and savings < min_savings:
            return {'status': 'skipped', 'file': filepath, 'reason': f'savings {savings:.2f}% < {min_savings}%'}
        
        if dryrun:
            echo_verbose(f"  ✓ {filepath}: {original_size} -> {final_size} ({savings:.2f}%) [DRYRUN]", level=1)
        else:
            echo_verbose(f"  ✓ {filepath}: {original_size} -> {final_size} ({savings:.2f}%)", level=1)
        
        return {
            'status': 'processed',
            'file': filepath,
            'original_size': original_size,
            'final_size': final_size,
            'savings_percent': savings,
            'savings_bytes': original_size - final_size
        }
    except Exception as e:
        return {'status': 'failed', 'file': filepath, 'error': str(e)}


def main():
    app()

if __name__ == "__main__":
    main()
