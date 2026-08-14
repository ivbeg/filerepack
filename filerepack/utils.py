#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import json
import logging
import os
import re
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

    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
    if not match:
        try:
            return int(size_str)
        except ValueError:
            raise ValueError(f"Invalid size format: {size_str}")

    number = float(match.group(1))
    unit = match.group(2) or 'B'

    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
    }

    return int(number * multipliers.get(unit, 1))


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
        from shutil import copy2
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            base = os.path.basename(filepath)
            backup_path = os.path.join(backup_dir, base)
            if os.path.exists(backup_path):
                parent = os.path.basename(os.path.dirname(os.path.abspath(filepath)))
                stem, ext = os.path.splitext(base)
                backup_path = os.path.join(backup_dir, f"{parent}_{stem}{ext}")
                n = 1
                while os.path.exists(backup_path):
                    backup_path = os.path.join(
                        backup_dir, f"{parent}_{stem}_{n}{ext}"
                    )
                    n += 1
        else:
            backup_path = filepath + '.bak'

        copy2(filepath, backup_path)
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
        }
    if hasattr(file_data, 'filepath'):
        return {
            'file': file_data.filepath,
            'original_size': file_data.insize,
            'final_size': file_data.outsize,
            'savings_percent': f"{file_data.savings_pct:.2f}",
            'savings_bytes': file_data.savings_bytes,
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
    if 'files' not in results or not results['files']:
        return

    fieldnames = [
        'file', 'original_size', 'final_size', 'savings_percent', 'savings_bytes'
    ]

    def _write(handle) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for file_data in results['files']:
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

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers or None,
        force=True,
    )


_VERIFY_PREFIXES = {
    'pdf': b'%PDF',
    'gz': b'\x1f\x8b',
    'gzip': b'\x1f\x8b',
    'svgz': b'\x1f\x8b',
    'xz': b'\xfd7zXZ',
    'bz2': b'BZh',
    'zst': b'\x28\xb5\x2f\xfd',
    'zstd': b'\x28\xb5\x2f\xfd',
    'lz4': b'\x04\x22\x4d\x18',
    'lz': b'LZIP',
    'lzo': b'\x89LZO',
    'z': b'\x1f\x9d',
    'jpg': b'\xff\xd8',
    'jpeg': b'\xff\xd8',
    'png': b'\x89PNG',
    'gif': b'GIF8',
    'parquet': b'PAR1',
    'orc': b'ORC',
    'avro': b'Obj\x01',
    '7z': b'7z\xbc\xaf\x27\x1c',
    'flac': b'fLaC',
    'cab': b'MSCF',
    'wim': b'MSWIM',
    'woff': b'wOFF',
    'woff2': b'wOF2',
    'exr': b'\x76\x2f\x31\x01',
    'ico': b'\x00\x00\x01\x00',
    'icns': b'icns',
    'sqlite': b'SQLite format 3',
    'hdf5': b'\x89HDF\r\n\x1a\n',
    'h5': b'\x89HDF\r\n\x1a\n',
    'psd': b'8BPS',
    'ai': b'%PDF',
}


def _verify_special(path: str, kind: str, header: bytes) -> bool:
    checks = {
        'zip': lambda: zipfile.is_zipfile(path),
        'ooxml': lambda: zipfile.is_zipfile(path),
        'jar': lambda: zipfile.is_zipfile(path),
        'epub': lambda: zipfile.is_zipfile(path),
        'cbz': lambda: zipfile.is_zipfile(path),
        'tif': lambda: header[:2] in (b'II', b'MM'),
        'tiff': lambda: header[:2] in (b'II', b'MM'),
        'dng': lambda: header[:2] in (b'II', b'MM'),
        'webp': lambda: header[:4] == b'RIFF',
        'avif': lambda: b'ftyp' in header,
        'heic': lambda: b'ftyp' in header,
        'heif': lambda: b'ftyp' in header,
        'mkv': lambda: header.startswith(b'\x1a\x45\xdf\xa3'),
        'webm': lambda: header.startswith(b'\x1a\x45\xdf\xa3'),
        'svg': lambda: (
            b'<svg' in header.lower() or header.lower().lstrip().startswith(b'<')
        ),
        'mp4': lambda: b'ftyp' in header or os.path.getsize(path) > 32,
        'mov': lambda: b'ftyp' in header or os.path.getsize(path) > 32,
        'm4v': lambda: b'ftyp' in header or os.path.getsize(path) > 32,
        'm4a': lambda: b'ftyp' in header or os.path.getsize(path) > 32,
        '3gp': lambda: b'ftyp' in header or os.path.getsize(path) > 32,
        'video': lambda: b'ftyp' in header or os.path.getsize(path) > 32,
        'ts': lambda: header[:1] == b'\x47',
        'mts': lambda: header[:1] == b'\x47',
        'm2ts': lambda: header[:1] == b'\x47',
        'jxl': lambda: header.startswith(b'\xff\x0a') or b'JXL' in header,
        'jp2': lambda: _jp2_magic(header),
        'j2k': lambda: _jp2_magic(header),
        'jpf': lambda: _jp2_magic(header),
        'jpx': lambda: _jp2_magic(header),
        'tar': lambda: _tar_magic(path),
        'feather': lambda: _arrow_magic(header),
        'arrow': lambda: _arrow_magic(header),
        'ipc': lambda: _arrow_magic(header),
        'nc': lambda: header.startswith(b'CDF') or header.startswith(b'\x89HDF'),
        'nc4': lambda: header.startswith(b'CDF') or header.startswith(b'\x89HDF'),
        'netcdf': lambda: header.startswith(b'CDF') or header.startswith(b'\x89HDF'),
        'wv': lambda: os.path.getsize(path) > 16,
        'ape': lambda: os.path.getsize(path) > 16,
        'tta': lambda: os.path.getsize(path) > 16,
        'oga': lambda: os.path.getsize(path) > 16,
        'lzma': lambda: os.path.getsize(path) > 8,
        'mp3': lambda: _mp3_magic(header),
        'dcm': lambda: _dicm_magic(path),
        'dicom': lambda: _dicm_magic(path),
        'dic': lambda: _dicm_magic(path),
    }
    checker = checks.get(kind)
    if checker is None:
        return True
    return checker()


def _arrow_magic(header: bytes) -> bool:
    return header.startswith(b'ARROW1') or header.startswith(b'FEA1') or len(header) >= 8


def _jp2_magic(header: bytes) -> bool:
    return b'jP' in header or b'ftypjp' in header or header.startswith(b'\xff\x4f')


def _tar_magic(path: str) -> bool:
    try:
        with open(path, 'rb') as tfh:
            tfh.seek(257)
            return tfh.read(5) == b'ustar'
    except OSError:
        return False


def _dicm_magic(path: str) -> bool:
    from .dicom import has_dicm_magic
    return has_dicm_magic(path)


def _mp3_magic(header: bytes) -> bool:
    if header.startswith(b'ID3'):
        return True
    return len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0


def verify_output(path: str, kind: str) -> bool:
    """Return True if path looks like a valid file of the given kind."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return False
        with open(path, 'rb') as fh:
            header = fh.read(16)
    except OSError:
        return False
    prefix = _VERIFY_PREFIXES.get(kind)
    if prefix is not None:
        return header.startswith(prefix)
    return _verify_special(path, kind, header)


def parse_jobs(jobs_value: str) -> int:
    """Parse --jobs value ('auto' or a positive integer)."""
    if isinstance(jobs_value, int):
        return max(1, jobs_value)
    text = str(jobs_value).strip().lower()
    if text == 'auto':
        return os.cpu_count() or 1
    try:
        return max(1, int(text))
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
