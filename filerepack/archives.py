"""Archive extraction, member verification and writing through shared candidates."""

import gzip
import bz2
import lzma
import logging
import os
import tempfile
import tarfile
import zipfile
from os.path import abspath
from typing import Any, Callable, ContextManager, Dict, List, Literal, Optional, Tuple

from .archive_manifest import (
    ArchiveManifest, ArchivePreservationError, intended_manifest, listed_manifest,
    match_metadata, match_payloads, read_tar_manifest, read_zip_manifest,
    restore_zip_metadata, tree_manifest, write_tar,
)
from .candidates import make_temp as _make_temp, remove_quietly as _remove_quietly
from .candidates import make_temp_dir
from .candidates import commit_output as _commit_output, COPY_BUF as _COPY_BUF
from .commands import run_command as _run_command, run_to_file as _run_to_file
from .commands import capture_command
from .consts import DEFAULT_MAX_EXTRACT_BYTES, DEFAULT_MAX_EXTRACT_RATIO, ZIP_SENSITIVE_EXTS
from .destinations import DestinationPlan, PathReservation, normalize_path
from .formats import identify_filename
from .models import ProgressHook, RepackSummary
from .package_policy import inspect_package, verify_package
from .streams import BinaryReader, _compress_file
from .tools import resolve_szip, resolve_tool
from .utils import dir_total_size, extract_exceeds_limit, zip_uncompressed_size

def _notify(
    hook: Optional[ProgressHook],
    event: str,
    *,
    current: int = 0,
    total: int = 0,
    name: str = "",
) -> None:
    if hook is None:
        return
    hook(event, current=current, total=total, name=name)

def _extract_limits(options: Dict[str, Any]) -> Tuple[int, float]:
    max_bytes = options.get('max_extract_bytes')
    if max_bytes is None:
        max_bytes = DEFAULT_MAX_EXTRACT_BYTES
    ratio = options.get('max_extract_ratio')
    if ratio is None:
        ratio = DEFAULT_MAX_EXTRACT_RATIO
    return int(max_bytes), float(ratio)

def _szip_listed_size(
    szip: str, filename: str, options: Dict[str, Any],
) -> Optional[int]:
    result = capture_command(
        [szip, 'l', '-slt', '-spd', '--', abspath(filename)],
        debug=options.get('debug', False),
    )
    if result is None or result.returncode != 0 or not result.stdout:
        return None
    total = 0
    found = False
    for line in result.stdout.splitlines():
        if line.startswith('Size = '):
            try:
                total += int(line.split('=', 1)[1].strip() or '0')
                found = True
            except ValueError:
                continue
    return total if found else None

def _planned_extract_size(
    filename: str, szip: Optional[str], options: Dict[str, Any],
) -> Optional[int]:
    zipped = zip_uncompressed_size(filename)
    if zipped is not None:
        return zipped
    if szip:
        return _szip_listed_size(szip, filename, options)
    return None

def _extract_over_limit(
    uncompressed: Optional[int], original: int, options: Dict[str, Any],
    filename: str,
) -> bool:
    max_bytes, ratio = _extract_limits(options)
    if not extract_exceeds_limit(uncompressed, original, max_bytes, ratio):
        return False
    logging.warning(
        'skipping extract of %s: uncompressed size %s exceeds limit',
        filename, uncompressed,
    )
    from .outcomes import record
    record('skipped', 'resource_limit', 'Archive extraction exceeds configured limits')
    return True

def _archive_arguments(fpath: str) -> List[str]:
    # Prefix names even after a tool's end-of-options marker; '@' and '-' must
    # never become listfiles/options and literal wildcards need tool switches.
    return ['./' + name for name in sorted(os.listdir(fpath))]

def _listed_archive(
    filename: str, options: Dict[str, Any], family: Optional[str] = None,
) -> ArchiveManifest:
    szip = resolve_szip()
    if szip is None:
        raise ArchivePreservationError('7zz/7z unavailable for member verification')
    result = _run_command(
        [szip, 'l', '-slt', '-spd', '--', abspath(filename)],
        debug=options.get('debug', False),
    )
    if result is None:
        raise ArchivePreservationError('cannot enumerate archive members')
    header, separator, members = result.stdout.partition('\n----------\n')
    if not separator:
        raise ArchivePreservationError('unrecognized archive listing structure')
    properties = dict(line.split(' = ', 1) for line in header.splitlines() if ' = ' in line)
    types = {'7z': {'7z'}, 'rar': {'Rar', 'Rar5'}, 'cab': {'Cab'}, 'wim': {'Wim'}}
    if family and properties.get('Type') not in types.get(family, set()):
        raise ArchivePreservationError('archive type does not match the declared family')
    if 'Comment' in properties or any(
        properties.get(key, '0') != '0' for key in ('Offset', 'Tail Size', 'Boot Index')
    ):
        raise ArchivePreservationError('unsupported archive wrapper/comment metadata')
    return listed_manifest(members)

def _decode_tar_payload(filename: str, output: str, outer: str,
                        options: Dict[str, Any]) -> bool:
    readers: Dict[str, Callable[[str, Literal['rb']], ContextManager[BinaryReader]]] = {
        'gz': gzip.open, 'bz2': bz2.open, 'xz': lzma.open, 'lzma': lzma.open,
    }
    reader = readers.get(outer)
    if reader is not None:
        with reader(filename, 'rb') as source, open(output, 'wb') as target:
            size = 0
            for data in iter(lambda: source.read(_COPY_BUF), b''):
                size += len(data)
                if _extract_over_limit(size, os.path.getsize(filename), options, filename):
                    return False
                target.write(data)
        return True
    tools = {'zst': 'zstd', 'br': 'brotli', 'lz4': 'lz4', 'lz': 'lzip',
             'lzo': 'lzop', 'z': 'compress'}
    tool = resolve_tool(tools.get(outer, ''))
    if not tool or not _run_to_file([tool, '-d', '-c'], output,
                                   options.get('debug', False), stdin_path=filename):
        return False
    return not _extract_over_limit(os.path.getsize(output), os.path.getsize(filename),
                                  options, filename)

def _source_archive(filename: str, family: str,
                    options: Dict[str, Any]) -> ArchiveManifest:
    if family == 'zip':
        return read_zip_manifest(filename)
    if family.startswith('tar'):
        return read_tar_manifest(filename)
    return _listed_archive(filename, options, family)


class ArchiveRepacker:
    """Archive implementation; orchestration supplies the nested-file callback."""

    temppath: str

    def _deep_walk(
        self, fpath: str, options: Dict[str, Any], summary: RepackSummary,
        on_progress: Optional[ProgressHook] = None,
    ) -> None:
        raise NotImplementedError

    def _repack_container(
        self, filename: str, dest: str, f_insize: int,
        filetype: str, options: Dict[str, Any], family: Optional[str] = None,
        on_progress: Optional[ProgressHook] = None,
    ) -> RepackSummary:
        if family in ('cpio', 'cpio.bz2'):
            from .cpio import repack_cpio

            return repack_cpio(
                self, filename, dest, f_insize, family, options, on_progress,
            )
        if family is None:
            kind = identify_filename(filename, peek_path=filename)
            family = kind.family if kind else 'zip'
        summary = RepackSummary(filepath=filename, total_insize=f_insize)
        summary.total_outsize = f_insize
        fpath = make_temp_dir(prefix='filerepack-archive-', directory=self.temppath)
        tar_payload: Optional[str] = None
        try:
            _notify(on_progress, 'extract', name=filename)
            planned = _planned_extract_size(filename, resolve_szip(), options)
            if _extract_over_limit(planned, f_insize, options, filename):
                return summary
            extract_source = filename
            if family.startswith('tar.'):
                tar_payload = _make_temp('.tar')
                if not _decode_tar_payload(filename, tar_payload, family.split('.', 1)[1], options):
                    return summary
                extract_source = tar_payload
            source = _source_archive(extract_source, family, options)
            package = inspect_package(filename, filetype) if family == 'zip' else None
            if _extract_over_limit(source.size, f_insize, options, filename):
                return summary
            if family == 'rar':
                extracted = self._extract_rar(filename, fpath, options)
            else:
                extracted = self._extract_7z(extract_source, fpath, options)
            if not extracted:
                return summary
            extracted_manifest = tree_manifest(fpath)
            match_payloads(source, extracted_manifest, implicit_directories=True)
            from .format_support import current_budget
            budget = current_budget()
            if budget:
                budget.consume(decoded=extracted_manifest.size,
                               nodes=len(extracted_manifest.members))
            # 7z/RAR/etc. listings provide CRCs; bind the verified extracted
            # bytes to strong hashes before any nested transformation.
            source = intended_manifest(
                source, fpath,
                (os.path.join(fpath, member.path) for member in source.members),
            )
            timestamps = {
                member.path: os.stat(os.path.join(fpath, member.path))
                for member in source.members if member.path
            }

            # RubyGems checksums cover its nested gz/tar payloads. Outer tar
            # rewriting is permitted, but nested edits need package policy.
            if options.get('deep_walking', True) and filetype != 'gem':
                # Inner files live in a throwaway extract dir. Replace them even
                # on dryrun so the rewritten archive size matches a real run.
                # The outer _commit_output still honors dryrun.
                walk_options = {
                    **options, '_protected_members': package.controls if package else (),
                }
                if options.get('dryrun'):
                    walk_options['dryrun'] = False
                self._deep_walk(
                    fpath, walk_options, summary, on_progress=on_progress,
                )

            expected = intended_manifest(
                source, fpath, (result.filepath for result in summary.results if result.replaced),
            )
            for name, before in timestamps.items():
                path = os.path.join(fpath, *name.split('/'))
                os.chmod(path, before.st_mode & 0o7777)
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            write_options = {**options, '_archive_manifest': expected, '_package_policy': package}

            _notify(on_progress, 'write', name=filename)
            self._write_by_family(
                family, fpath, dest, filename, write_options, summary, f_insize, filetype
            )
            return summary
        except (OSError, ValueError, EOFError, tarfile.TarError,
                zipfile.BadZipFile, lzma.LZMAError, NotImplementedError) as exc:
            from .outcomes import record
            from .format_support import FormatLimit
            record('skipped' if isinstance(exc, FormatLimit) else 'failed',
                   'resource_limit' if isinstance(exc, FormatLimit) else
                   'archive_preservation_failed', str(exc))
            logging.warning('archive preservation skipped %s: %s', filename, exc)
            return summary
        finally:
            _remove_quietly(fpath)
            _remove_quietly(tar_payload)

    def _write_by_family(
        self, family: str, fpath: str, dest: str, filename: str,
        options: Dict[str, Any], summary: RepackSummary, f_insize: int,
        filetype: str,
    ) -> None:
        if family == 'rar':
            self._repack_rar(fpath, dest, filename, options, summary, f_insize)
            return
        if family.startswith('tar') and family != 'tar':
            outer = family.split('.', 1)[1]
            self._write_tar_bundle(fpath, dest, options, summary, f_insize, outer)
            return
        archive_type = family if family in ('zip', '7z', 'tar', 'cab', 'wim') else 'zip'
        self._write_archive(
            fpath, dest, options, summary, f_insize, archive_type, filetype
        )

    def _extract_7z(
        self, filename: str, fpath: str, options: Dict[str, Any]
    ) -> bool:
        szip = resolve_szip()
        if szip is None:
            logging.warning('7zz/7z not found; cannot extract %s', filename)
            return False
        original = os.path.getsize(filename)
        planned = _planned_extract_size(filename, szip, options)
        if _extract_over_limit(planned, original, options, filename):
            return False
        os.makedirs(fpath, exist_ok=True)
        cmd = [szip, 'x', '-y', '-spd', f'-o{fpath}', '--', abspath(filename)]
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False),
        )
        if result is None:
            return False
        if planned is None:
            extracted = dir_total_size(fpath)
            if _extract_over_limit(extracted, original, options, filename):
                return False
        return True

    def _extract_rar(
        self, filename: str, fpath: str, options: Dict[str, Any]
    ) -> bool:
        os.makedirs(fpath, exist_ok=True)
        unrar_path = resolve_tool('unrar')
        if unrar_path:
            cmd = [unrar_path, 'x', '-y', abspath(filename)]
            result = _run_command(
                cmd, quiet=options.get('quiet', False),
                debug=options.get('debug', False), cwd=fpath,
            )
            if result is None:
                return False
            extracted = dir_total_size(fpath)
            original = os.path.getsize(filename)
            return not _extract_over_limit(
                extracted, original, options, filename
            )
        if not options.get('quiet', False):
            logging.warning('unrar not found, using 7zz/7z for RAR extraction')
        return self._extract_7z(filename, fpath, options)

    def _write_archive(
        self, fpath: str, dest: str, options: Dict[str, Any],
        summary: RepackSummary, f_insize: int, archive_type: str,
        source_ext: str = '',
    ) -> None:
        if archive_type == 'zip' and source_ext in ZIP_SENSITIVE_EXTS:
            if self._write_infozip(fpath, dest, options, summary, f_insize):
                return
        szip = resolve_szip()
        if szip is None:
            summary.total_outsize = f_insize
            return
        suffix_map = {
            'zip': '.zip', '7z': '.7z', 'tar': '.tar', 'cab': '.cab', 'wim': '.wim',
        }
        verify_map = {
            'zip': 'zip', '7z': '7z', 'tar': 'tar', 'cab': 'cab', 'wim': 'wim',
        }
        suffix = suffix_map.get(archive_type, '.zip')
        temp_out = _make_temp(suffix)
        _remove_quietly(temp_out)
        level = options.get('compression_level', 9)
        if archive_type == 'tar':
            try:
                write_tar(temp_out, fpath, options['_archive_manifest'])
            except Exception:
                _remove_quietly(temp_out)
                raise
        else:
            cmd = [
                szip, f'-t{archive_type}', '-y', f'-mx{level}',
                f'-mmt{options.get("tool_threads", 1)}', '-spd',
                'a', temp_out, '--', *_archive_arguments(fpath),
            ]
            result = _run_command(
                cmd, quiet=options.get('quiet', False),
                debug=options.get('debug', False), cwd=fpath,
            )
            if result is None:
                _remove_quietly(temp_out)
                summary.total_outsize = f_insize
                return
        if not self._verify_archive_candidate(temp_out, archive_type, options):
            _remove_quietly(temp_out)
            summary.total_outsize = f_insize
            return
        verify = verify_map.get(archive_type, 'zip')
        packed = _commit_output(
            temp_out, dest, f_insize, verify=verify,
            reservation=options.get('_publication_reservation'),
            overwrite=options.get('overwrite', False),
            dryrun=options.get('dryrun', False),
            keep_if_larger=options.get('keep_if_larger', True),
            min_savings=options.get('min_savings'),
        )
        if packed is None:
            summary.total_outsize = f_insize
            return
        summary.total_outsize = packed.outsize
        if packed.replaced:
            summary.filepath = dest

    def _write_tar_bundle(
        self, fpath: str, dest: str, options: Dict[str, Any],
        summary: RepackSummary, f_insize: int, outer: str,
    ) -> None:
        """Write an uncompressed tar, then wrap it in gz/xz/bz2/zst/..."""
        tar_temp = _make_temp('.tar')
        suffix = {
            'gz': '.gz', 'bz2': '.bz2', 'xz': '.xz', 'zst': '.zst',
            'br': '.br', 'lz4': '.lz4', 'lz': '.lz', 'lzo': '.lzo',
            'lzma': '.lzma', 'z': '.Z',
        }.get(outer, '.gz')
        verify = {
            'gz': 'gz', 'bz2': 'bz2', 'xz': 'xz', 'zst': 'zst', 'br': 'br',
            'lz4': 'lz4', 'lz': 'lz', 'lzo': 'lzo', 'lzma': 'lzma', 'z': 'z',
        }.get(outer)
        out_temp: Optional[str] = None
        try:
            out_temp = _make_temp(suffix)
            write_tar(tar_temp, fpath, options['_archive_manifest'])
            if not _compress_file(tar_temp, out_temp, outer, options.get('debug', False)):
                summary.total_outsize = f_insize
                return
            # Verify what was actually encoded, not just the intermediate tar.
            if not _decode_tar_payload(out_temp, tar_temp, outer,
                                       {**options, 'max_extract_ratio': 0}):
                summary.total_outsize = f_insize
                return
            match_metadata(options['_archive_manifest'], read_tar_manifest(tar_temp))
            packed = _commit_output(
                out_temp, dest, f_insize, verify=verify,
                dryrun=options.get('dryrun', False),
                keep_if_larger=options.get('keep_if_larger', True),
                min_savings=options.get('min_savings'),
            )
            summary.total_outsize = packed.outsize if packed else f_insize
        finally:
            _remove_quietly(tar_temp)
            _remove_quietly(out_temp)

    def _write_infozip(
        self, fpath: str, dest: str, options: Dict[str, Any],
        summary: RepackSummary, f_insize: int,
    ) -> bool:
        """Rewrite OOXML with Info-ZIP when available. False = try 7zz."""
        zip_tool = resolve_tool('zip')
        if zip_tool is None:
            return False
        temp_out = _make_temp('.zip')
        _remove_quietly(temp_out)
        level = min(9, max(1, int(options.get('compression_level', 9))))
        cmd = [zip_tool, '-r', f'-{level}', '-X', '-nw', temp_out,
               '--', *_archive_arguments(fpath)]
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
            _remove_quietly(temp_out)
            return False
        if not self._verify_archive_candidate(temp_out, 'zip', options):
            _remove_quietly(temp_out)
            return False
        packed = _commit_output(
            temp_out, dest, f_insize, verify='zip',
            dryrun=options.get('dryrun', False),
            keep_if_larger=options.get('keep_if_larger', True),
            min_savings=options.get('min_savings'),
        )
        if packed is None:
            return False
        summary.total_outsize = packed.outsize
        return True

    def _repack_rar(
        self, fpath: str, dest: str, filename: str,
        options: Dict[str, Any], summary: RepackSummary, f_insize: int,
    ) -> None:
        rar_path = resolve_tool('rar')
        if not rar_path:
            if not options.get('quiet', False):
                logging.warning('rar tool not found. Recompressing as 7z.')
            dest_7z = dest.rsplit('.', 1)[0] + '.7z'
            plan = DestinationPlan(
                normalize_path(filename), normalize_path(dest_7z),
                overwrite=options.get('overwrite', False),
            )
            plan.validate()
            with PathReservation(plan.paths, dryrun=options.get('dryrun', False)) as reservation:
                plan.validate()
                self._write_archive(
                    fpath, dest_7z, {**options, '_publication_reservation': reservation},
                    summary, f_insize, '7z', 'rar',
                )
            if (
                summary.filepath == dest_7z
                and not options.get('dryrun', False)
                and dest_7z != filename
                and os.path.exists(dest_7z)
            ):
                _remove_quietly(filename)
            return

        temp_out = _make_temp('.rar')
        _remove_quietly(temp_out)
        level = options.get('compression_level', 9)
        if level <= 2:
            rar_level = '-m3'
        elif level <= 4:
            rar_level = '-m4'
        else:
            rar_level = '-m5'
        arguments = _archive_arguments(fpath)
        if any('*' in name or '?' in name for name in arguments):
            logging.warning('RAR writer cannot select literal wildcard names; archive unchanged')
            summary.total_outsize = f_insize
            return
        cmd = [rar_path, 'a', '-r', rar_level, '-y', temp_out, *arguments]
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
            _remove_quietly(temp_out)
            summary.total_outsize = f_insize
            return
        if not self._verify_archive_candidate(temp_out, 'rar', options):
            _remove_quietly(temp_out)
            summary.total_outsize = f_insize
            return
        packed = _commit_output(
            temp_out, dest, f_insize, verify='rar',
            dryrun=options.get('dryrun', False),
            keep_if_larger=options.get('keep_if_larger', True),
            min_savings=options.get('min_savings'),
        )
        if packed is None:
            summary.total_outsize = f_insize
            return
        summary.total_outsize = packed.outsize

    def _verify_archive_candidate(
        self, filename: str, family: str, options: Dict[str, Any],
    ) -> bool:
        expected = options['_archive_manifest']
        try:
            if family == 'zip':
                package = options.get('_package_policy')
                restore_zip_metadata(
                    filename, expected, options.get('compression_level', 9),
                    stored_members=('mimetype',)
                    if package and package.kind in ('odf', 'epub') else (),
                )
                if package:
                    verify_package(filename, package)
                actual = read_zip_manifest(filename)
            elif family == 'tar':
                actual = read_tar_manifest(filename)
            else:
                actual = _listed_archive(filename, options, family)
                with tempfile.TemporaryDirectory(dir=self.temppath) as extracted:
                    if not self._extract_7z(filename, extracted,
                                            {**options, 'max_extract_ratio': 0}):
                        return False
                    match_payloads(actual, tree_manifest(extracted), implicit_directories=True)
                    actual = intended_manifest(
                        actual, extracted,
                        (os.path.join(extracted, member.path) for member in actual.members),
                    )
            match_metadata(expected, actual)
            return True
        except (OSError, ValueError, EOFError, tarfile.TarError,
                zipfile.BadZipFile, NotImplementedError) as exc:
            logging.warning('archive candidate rejected: %s', exc)
            return False
