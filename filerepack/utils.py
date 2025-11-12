#!/usr/bin/env python
#-*- coding: utf-8 -*-

import os
import re
import json
import csv
import datetime
from typing import Optional, List, Dict, Any


def parse_size(size_str: str) -> int:
    """
    Parse human-readable size string to bytes.
    Examples: '1MB', '500KB', '2GB', '1000'
    """
    if not size_str:
        return 0
    
    # Remove whitespace and convert to uppercase
    size_str = size_str.strip().upper()
    
    # Extract number and unit
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
    if not match:
        # Try to parse as plain number
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
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


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
            # Remove leading dot if present
            if ext.startswith('.'):
                ext = ext[1:]
            extensions.append(ext)
    
    return extensions


def should_process_file(
    filepath: str,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    include_exts: Optional[List[str]] = None,
    exclude_exts: Optional[List[str]] = None,
    min_savings: Optional[float] = None,
    current_savings: Optional[float] = None
):
    """
    Determine if a file should be processed based on filters.
    Returns (should_process, reason_if_skipped)
    """
    # Check extension filters
    ext = os.path.splitext(filepath)[1][1:].lower() if '.' in filepath else ''
    
    if include_exts and ext not in include_exts:
        return False, f"Extension '{ext}' not in include list"
    
    if exclude_exts and ext in exclude_exts:
        return False, f"Extension '{ext}' in exclude list"
    
    # Check size filters
    try:
        file_size = os.path.getsize(filepath)
    except OSError:
        return False, "Cannot read file size"
    
    if min_size and file_size < min_size:
        return False, f"File size {file_size} < min_size {min_size}"
    
    if max_size and file_size > max_size:
        return False, f"File size {file_size} > max_size {max_size}"
    
    # Check minimum savings (if we already know the savings)
    if min_savings is not None and current_savings is not None:
        if current_savings < min_savings:
            return False, f"Savings {current_savings:.2f}% < min_savings {min_savings}%"
    
    return True, ""


def create_backup(filepath: str, backup_dir: Optional[str] = None) -> Optional[str]:
    """
    Create a backup of a file.
    Returns path to backup file, or None if failed.
    """
    try:
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, os.path.basename(filepath))
        else:
            # Create backup in same directory with .bak extension
            backup_path = filepath + '.bak'
        
        from shutil import copy2
        copy2(filepath, backup_path)
        return backup_path
    except Exception as e:
        return None


def output_json(results: Dict[str, Any], output_file: Optional[str] = None):
    """Output results in JSON format."""
    json_str = json.dumps(results, indent=2, default=str)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(json_str)
    else:
        print(json_str)


def output_csv(results: Dict[str, Any], output_file: Optional[str] = None):
    """Output results in CSV format."""
    import sys
    
    if 'files' not in results or not results['files']:
        return
    
    fieldnames = ['file', 'original_size', 'final_size', 'savings_percent', 'savings_bytes']
    
    writer = csv.DictWriter(sys.stdout if not output_file else open(output_file, 'w'), fieldnames=fieldnames)
    writer.writeheader()
    
    for file_data in results['files']:
        if len(file_data) >= 4:
            writer.writerow({
                'file': file_data[0],
                'original_size': file_data[1],
                'final_size': file_data[2],
                'savings_percent': f"{file_data[3]:.2f}",
                'savings_bytes': file_data[1] - file_data[2] if len(file_data) > 2 else 0
            })
    
    if output_file:
        writer.writer.writer.close()


def setup_logging(log_file: Optional[str] = None, level: str = 'INFO'):
    """Setup logging configuration."""
    import logging
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

