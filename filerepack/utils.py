#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import json
import logging
import os
import re
from decimal import Decimal
import sys
import zipfile
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_EXCLUDE_DIRS = {
    '.git', '.hg', '.svn', '.tox', '.venv', 'venv',
    'node_modules', '__pycache__', '.mypy_cache', '.pytest_cache',
}


def parse_size(size_str: Optional[str]) -> int:
    """
    Parse human-readable size string to bytes.
    Examples: '1MB', '500KB', '2GB', '1000'
    """
    if not size_str:
        return 0

    size_str = size_str.strip().upper()

    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*([KMGT]?B?)', size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")

    number = Decimal(match.group(1))
    unit = match.group(2).removesuffix('B')

    multipliers = {
        '': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
    }

    return int(number * multipliers[unit])


def format_size(size: int) -> str:
    """Format bytes to human-readable size string."""
    value = float(size)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if value < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def parse_extensions(ext_str: Optional[str]) -> List[str]:
    """
    Parse comma-separated extension list.
    Returns list of extensions (without dots, lowercase).
    """
    if not ext_str:
        return []

    extensions = []
    for ext in ext_str.split(','):
        ext = ext.strip().lower()
        if ext:
            if ext.startswith('.'):
                ext = ext[1:]
            extensions.append(ext)

    return extensions


def parse_dir_names(dir_str: Optional[str]) -> Set[str]:
    """Parse comma-separated directory names to exclude."""
    if not dir_str:
        return set()
    names = set()
    for part in dir_str.split(','):
        name = part.strip().strip('/\\')
        if name:
            names.add(name)
    return names


def should_process_file(
    filepath: str,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    include_exts: Optional[List[str]] = None,
    exclude_exts: Optional[List[str]] = None,
    min_savings: Optional[float] = None,
    current_savings: Optional[float] = None
) -> Tuple[bool, str]:
    """
    Determine if a file should be processed based on filters.
    Returns (should_process, reason_if_skipped)
    """
    from .formats import excluded_by_ext_filter, filename_exts, matches_ext_filter

    ext = os.path.splitext(filepath)[1][1:].lower() if '.' in filepath else ''
    keys = filename_exts(filepath)

    if include_exts and not matches_ext_filter(filepath, include_exts):
        return False, f"Extension '{ext or ','.join(keys)}' not in include list"

    if exclude_exts and excluded_by_ext_filter(filepath, exclude_exts):
        return False, f"Extension '{ext or ','.join(keys)}' in exclude list"

    try:
        file_size = os.path.getsize(filepath)
    except OSError:
        return False, "Cannot read file size"

    if min_size and file_size < min_size:
        return False, f"File size {file_size} < min_size {min_size}"

    if max_size and file_size > max_size:
        return False, f"File size {file_size} > max_size {max_size}"

    if min_savings is not None and current_savings is not None:
        if current_savings < min_savings:
            return False, (
                f"Savings {current_savings:.2f}% < min_savings {min_savings}%"
            )

    return True, ""


def create_backup(filepath: str, backup_dir: Optional[str] = None) -> Optional[str]:
    """
    Create a backup of a file.
    Returns path to backup file, or None if failed.
    """
    try:
        from .destinations import (
            DestinationPlan, PathReservation, backup_destination, normalize_path,
        )
        source = normalize_path(filepath)
        backup_path = backup_destination(source, backup_dir)
        plan = DestinationPlan(source, source, backup=backup_path)
        plan.validate()
        with PathReservation(plan.paths) as reservation:
            plan.validate()
            reservation.publish_copy(source, backup_path)
        return backup_path
    except OSError as exc:
        logging.warning('backup failed for %s: %s', filepath, exc)
        return None


def output_json(results: Dict[str, Any], output_file: Optional[str] = None) -> None:
    """Output results in JSON format."""
    json_str = json.dumps(results, indent=2, default=str)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
    else:
        print(json_str)


def _csv_row(file_data: Any) -> Optional[Dict[str, Any]]:
    if isinstance(file_data, dict):
        original = file_data.get('original_size', file_data.get('insize', 0))
        final = file_data.get('final_size', file_data.get('outsize', 0))
        savings = file_data.get(
            'savings_percent', file_data.get('savings_pct', 0.0)
        )
        return {
            'file': file_data.get('file', file_data.get('filepath', '')),
            'original_size': original,
            'final_size': final,
            'savings_percent': f"{float(savings or 0):.2f}",
            'savings_bytes': int(original or 0) - int(final or 0),
            'status': file_data.get('status', ''),
            'reason_code': file_data.get('reason_code', ''),
            'reason': file_data.get('reason', file_data.get('error', '')),
            'output_file': file_data.get('output_file', ''),
            'published': file_data.get('published', False),
        }
    if hasattr(file_data, 'filepath'):
        return {
            'file': file_data.filepath,
            'original_size': file_data.insize,
            'final_size': file_data.outsize,
            'savings_percent': f"{file_data.savings_pct:.2f}",
            'savings_bytes': file_data.savings_bytes,
            'status': file_data.status or '',
            'reason_code': file_data.reason_code,
            'reason': file_data.reason,
            'output_file': file_data.filepath,
            'published': file_data.published,
        }
    if isinstance(file_data, (list, tuple)) and len(file_data) >= 4:
        return {
            'file': file_data[0],
            'original_size': file_data[1],
            'final_size': file_data[2],
            'savings_percent': f"{file_data[3]:.2f}",
            'savings_bytes': file_data[1] - file_data[2],
        }
    return None


def output_csv(results: Dict[str, Any], output_file: Optional[str] = None) -> None:
    """Output results in CSV format. Accepts dict, PackResult, or list rows."""
    fieldnames = [
        'file', 'original_size', 'final_size', 'savings_percent', 'savings_bytes',
        'status', 'reason_code', 'reason', 'output_file', 'published',
    ]

    def _write(handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for file_data in results.get('files', []):
            row = _csv_row(file_data)
            if row:
                writer.writerow(row)

    if output_file:
        with open(output_file, 'w', encoding='utf-8', newline='') as fh:
            _write(fh)
    else:
        _write(sys.stdout)


def setup_logging(log_file: Optional[str] = None, level: str = 'INFO') -> None:
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers: List[logging.Handler] = []
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    reset_logging()
    root = logging.getLogger()
    root.setLevel(log_level)
    for handler in handlers:
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        setattr(handler, '_filerepack_owned', True)
        root.addHandler(handler)


def reset_logging() -> None:
    """Close only handlers owned by an earlier CLI invocation."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, '_filerepack_owned', False):
            root.removeHandler(handler)
            handler.close()


def verify_output(path: str, kind: str, *, source_path: Optional[str] = None) -> bool:
    """Compatibility adapter for structural validation; DICOM also compares the source."""
    from .verification import validate_output
    return validate_output(path, kind, source_path=source_path).ok


def parse_jobs(jobs_value: str) -> int:
    """Parse --jobs value ('auto' or a positive integer)."""
    text = str(jobs_value).strip().lower()
    if text == 'auto':
        return os.cpu_count() or 1
    try:
        value = int(text)
        if value < 1:
            raise ValueError()
        return value
    except ValueError:
        raise ValueError(f"Invalid --jobs value: {jobs_value}")


def dir_total_size(path: str) -> int:
    """Sum file sizes under path. Missing files are skipped."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def zip_uncompressed_size(path: str) -> Optional[int]:
    """Sum uncompressed sizes from a ZIP central directory, if path is a ZIP."""
    if not zipfile.is_zipfile(path):
        return None
    try:
        with zipfile.ZipFile(path) as zf:
            return sum(info.file_size for info in zf.infolist())
    except (zipfile.BadZipFile, OSError):
        return None


def extract_exceeds_limit(
    uncompressed: Optional[int],
    original: int,
    max_bytes: int,
    ratio: float,
) -> bool:
    """Return True if an extract looks like a zip bomb or exceeds the cap."""
    if uncompressed is None:
        return False
    if max_bytes > 0 and uncompressed > max_bytes:
        return True
    if ratio > 0 and original > 0 and uncompressed > original * ratio:
        return True
    return False
