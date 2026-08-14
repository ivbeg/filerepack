# -*- coding: utf-8 -*-

"""Picklable bulk worker used by ProcessPoolExecutor."""

import os
from typing import Any, Dict

from .models import RepackOptions
from .repack import FileRepacker
from .utils import create_backup, should_process_file


def process_file_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Process one file and return a result dictionary. No stdout."""
    filepath = job['filepath']
    try:
        should, reason = should_process_file(
            filepath,
            min_size=job.get('min_size_bytes'),
            max_size=job.get('max_size_bytes'),
            include_exts=job.get('include_exts'),
            exclude_exts=job.get('exclude_exts'),
        )
        if not should:
            return {'status': 'skipped', 'file': filepath, 'reason': reason}

        if job.get('backup') and not job.get('dryrun'):
            create_backup(filepath, job.get('backup_dir'))

        output_filepath = filepath
        output_dir = job.get('output_dir')
        base_directory = job.get('base_directory') or os.path.dirname(filepath)
        if output_dir and not job.get('dryrun'):
            from shutil import copy2
            os.makedirs(output_dir, exist_ok=True)
            rel_path = os.path.relpath(filepath, base_directory)
            output_filepath = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(output_filepath) or '.', exist_ok=True)
            if output_filepath != filepath:
                copy2(filepath, output_filepath)

        options = RepackOptions(
            debug=bool(job.get('debug')),
            ultra=bool(job.get('ultra')),
            dryrun=bool(job.get('dryrun')),
            deep_walking=bool(job.get('deep', True)),
            quiet=True,
            pack_images=not job.get('no_images', False),
            pack_archives=not job.get('no_archives', False),
            compression_level=int(job.get('compression_level', 9)),
            jpeg_quality=job.get('jpeg_quality'),
            png_quality=job.get('png_quality'),
            wmv_lossless=bool(job.get('wmv_lossless')),
            lossy=bool(job.get('lossy')),
            convert_container=bool(job.get('convert_container', True)),
            keep_if_larger=bool(job.get('keep_if_larger', True)),
            min_savings=job.get('min_savings'),
            max_extract_bytes=job.get('max_extract_bytes'),
            max_extract_ratio=job.get('max_extract_ratio'),
        )

        target = output_filepath if output_filepath != filepath else filepath
        outfile = output_filepath if output_filepath != filepath else None
        results = FileRepacker(quiet=True).repack_zip_file(
            target, outfile=outfile, def_options=options
        )
        if results is None:
            return {'status': 'failed', 'file': filepath, 'error': 'No results'}

        original_size = results.total_insize
        final_size = results.total_outsize
        savings = results.total_savings_pct

        return {
            'status': 'processed',
            'file': filepath,
            'original_size': original_size,
            'final_size': final_size,
            'savings_percent': savings,
            'savings_bytes': original_size - final_size,
        }
    except Exception as exc:
        return {'status': 'failed', 'file': filepath, 'error': str(exc)}
