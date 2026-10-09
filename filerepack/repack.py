#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import time
from os.path import exists, isfile, join
from os import listdir, walk
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Union

from .archives import ArchiveRepacker
from .archives import _notify as _notify
from .archives import _extract_limits as _extract_limits
from .archives import _szip_listed_size as _szip_listed_size
from .archives import _planned_extract_size as _planned_extract_size
from .archives import _extract_over_limit as _extract_over_limit
from .archives import _archive_arguments as _archive_arguments
from .archives import _listed_archive as _listed_archive
from .archives import _decode_tar_payload as _decode_tar_payload
from .archives import _source_archive as _source_archive
from .dispatch import PackerSpec as PackerSpec, _PACKERS as _PACKERS
from .dispatch import dispatch_packer as _dispatch_packer
from .streams import _pack_stream_codec as _pack_stream_codec
from .streams import _pack_pipe_codec as _pack_pipe_codec
from .streams import _compress_file as _compress_file
from .streams import pack_gzip as pack_gzip
from .streams import pack_xz as pack_xz
from .streams import pack_bz2 as pack_bz2
from .streams import pack_zstd as pack_zstd
from .streams import pack_brotli as pack_brotli
from .images import pack_avif as pack_avif
from .images import pack_heic as pack_heic
from .images import pack_gif as pack_gif
from .images import pack_webp as pack_webp
from .images import pack_svg as pack_svg
from .images import pack_tif as pack_tif
from .images import pack_jpg as pack_jpg
from .images import _jpegtran_inplace as _jpegtran_inplace
from .images import _pngquant_lossy as _pngquant_lossy
from .images import _png_lossless_candidates as _png_lossless_candidates
from .images import pack_png as pack_png
from .media import pack_flac as pack_flac
from .media import _encode_video as _encode_video
from .media import _pack_video as _pack_video
from .media import _pack_video_reserved as _pack_video_reserved
from .media import pack_wmv as pack_wmv
from .media import pack_mp4 as pack_mp4
from .media import pack_avi as pack_avi
from .media import pack_asf as pack_asf
from .media import pack_mkv as pack_mkv
from .media import pack_webm as pack_webm
from .documents import jpeg_quality_to_qfactor as jpeg_quality_to_qfactor
from .documents import build_gs_pdf_cmd as build_gs_pdf_cmd
from .documents import _maybe_walk_pdf_images as _maybe_walk_pdf_images
from .documents import _qpdf_linearize as _qpdf_linearize
from .documents import _gs_pdf as _gs_pdf
from .documents import pack_pdf as pack_pdf
from .data import pack_parquet as pack_parquet
from .nib import pack_nib as pack_nib
from .car import pack_car as pack_car
from .warc import pack_warc as pack_warc
from .candidates import remove_quietly as _remove_quietly
from .candidates import commit_output as _commit_output  # noqa: F401
from .candidates import commit_kwargs as _commit_kwargs  # noqa: F401
from .candidates import calc_savings as _calc_savings  # noqa: F401
from .candidates import make_temp as _make_temp  # noqa: F401
from .commands import run_command as _run_command  # noqa: F401
from .commands import run_to_file as _run_to_file  # noqa: F401
from .commands import expand_globs
from .destinations import (
    DestinationPlan, PathReservation, backup_destination, copy_verified, digest,
    normalize_path, same_file,
)
from .formats import FileKind, identify_filename
from .models import PackResult, ProgressHook, RepackOptions, RepackSummary
from .outcomes import Diagnostic, RepackOutcome, diagnostic_scope, refusal
from .selection import depth_enabled, excluded_member
from .tools import resolve_tool
from .transactions import (
    FileSnapshot, candidate_scope,
)
from .validation import validate_options
from .validation import normalize_pdf_profile as normalize_pdf_profile

TEMP_PATH = tempfile.gettempdir()
_COPY_BUF = 1024 * 1024
_expand_globs = expand_globs  # Compatibility for existing helper imports.


OptionsInput = Union[RepackOptions, Mapping[str, Any]]


def _is_scientific(kind: Optional[FileKind]) -> bool:
    return kind is not None and (kind.packer or kind.key) in {
        'r-serialization', 'mat', 'checkpoint', 'spss', 'h5', 'hdf5', 'hdf',
        'nc', 'nc4', 'tif', 'tiff', 'nib', 'car', 'safetensors', 'gguf', 'onnx',
    }


def _retains_rejected_source(kind: Optional[FileKind]) -> bool:
    return _is_scientific(kind) or bool(kind and (kind.packer or kind.key) == 'warc')


def _normalize_options(def_options: Optional[OptionsInput]) -> Dict[str, Any]:
    options = {
        'debug': False, 'pack_images': True, 'repack_archive': True,
        'pack_archives': True, 'deep_walking': True, 'log': False,
        'quiet': False, 'ultra': False, 'dryrun': False,
        'keep_if_larger': True, 'lossy': False, 'convert_container': True,
        'min_savings': None, 'compression_level': 9,
        'pdf_profile': None, 'jpeg_quality': None,
        'keep_meta': False,
        'overwrite': False, 'backup': False, 'backup_dir': None,
    }
    if isinstance(def_options, RepackOptions):
        options.update(def_options.to_dict())
    elif def_options:
        from .profiles import resolve_profile
        options.update(resolve_profile(def_options.get('profile'), dict(def_options)))
    return validate_options(options)


def prepare_destination_plan(
    filename: str, outfile: Optional[str], options: Dict[str, Any],
    *, check: bool = True, peek: bool = True,
) -> DestinationPlan:
    """Read-only preflight shared with the CLI before opening a log file."""
    source = normalize_path(filename)
    output = normalize_path(outfile or filename)
    if same_file(source, output):
        output = source
    kind = identify_filename(filename, peek_path=source if peek else None)
    converted = None
    if kind and kind.key in ('wmv', 'avi', 'asf', '3gp', 'ts', 'mts', 'm2ts') and (
        options.get('convert_container', True) and options.get('pack_images', True)
    ):
        converted = os.path.splitext(output)[0] + '.mp4'
    elif kind and kind.family == 'rar' and not resolve_tool('rar'):
        converted = os.path.splitext(output)[0] + '.7z'
    elif kind and kind.key == 'warc' and options.get('convert_container', True):
        converted = output if output.lower().endswith('.gz') else output + '.gz'
    if converted == output:
        converted = None
    backup = (
        options.get('_backup_path', backup_destination(source, options.get('backup_dir')))
        if options.get('backup') else None
    )
    plan = DestinationPlan(source, output, converted, backup, options.get('overwrite', False))
    if check:
        plan.validate()
    return plan


def _empty_summary(filepath: str, size: int) -> RepackSummary:
    return RepackSummary(
        filepath=filepath, total_insize=size, total_outsize=size,
    )


def _refused_stage(summary: RepackSummary, diagnostics: list) -> bool:
    return (any(result.status in ('failed', 'unsupported', 'skipped', 'cancelled')
                for result in summary.results) or
            any(note.status in ('failed', 'cancelled') or note.reason_code == 'resource_limit'
                for note in diagnostics))


def _accepted_stage(summary: RepackSummary, kind: Optional[FileKind],
                    work: str, original_digest: str) -> bool:
    if kind and kind.is_archive:
        return summary.filepath != work or digest(summary.filepath) != original_digest
    return bool(summary.results and summary.results[0].replaced)


def _work_options(
    plan: DestinationPlan, kind: Optional[FileKind], options: Dict[str, Any],
) -> Dict[str, Any]:
    result = {**options, 'dryrun': False, 'backup': False,
              'backup_dir': None, 'overwrite': False}
    if kind and (kind.packer or kind.key) in ('sqlite', 'sqlite3', 'gpkg', 'mbtiles'):
        result['sqlite_offline'] = True  # Only the private verified snapshot is rewritten.
    if kind and (kind.packer or kind.key) == 'warc':
        result['_warc_index_source'] = (
            plan.source if plan.output == plan.source else plan.converted or plan.output
        )
    return result


def _stage_source(plan: DestinationPlan, kind: Optional[FileKind], work: str) -> str:
    if _is_sqlite(kind):
        from .data import copy_sqlite_snapshot
        copy_sqlite_snapshot(plan.source, work)
        return digest(work)
    return copy_verified(plan.source, work)


def _is_sqlite(kind: Optional[FileKind]) -> bool:
    return bool(kind and (kind.packer or kind.key) in ('sqlite', 'sqlite3', 'gpkg', 'mbtiles'))


def _finalize_members(summary: RepackSummary, options: Dict[str, Any]) -> None:
    assert summary.outcome is not None
    for member in summary.member_outcomes:
        member.source = summary.outcome.source + '!/' + (member.member or '')
        member.destination = summary.outcome.destination + '!/' + (member.member or '')
        staged = member.status
        member.details = {**member.details, 'staged_status': staged,
                          'staged_final_size': member.final_size}
        member.published = summary.outcome.published and staged == 'replaced'
        if options['dryrun'] and staged in ('replaced', 'unchanged'):
            member.status = 'predicted'
        elif staged == 'replaced' and not summary.outcome.published:
            member.status = 'unchanged'
            member.final_size = member.original_size
            member.reason_code = 'outer_not_published'


class FileRepacker(ArchiveRepacker):
    """Document and file repacker."""

    def __init__(self, quiet: bool = False, temppath: Optional[str] = None):
        self.quiet = quiet
        self.temppath = temppath if temppath else TEMP_PATH

    def pack_images(
        self, mediapath: str, recursive: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[RepackSummary]:
        options = _normalize_options(options)
        if not exists(mediapath):
            return None
        summary = RepackSummary(filepath=mediapath)
        if not recursive:
            names = [f for f in listdir(mediapath) if isfile(join(mediapath, f))]
            files_to_process = [(join(mediapath, f), f) for f in names]
        else:
            files_to_process = []
            for root, dirs, files in walk(mediapath):
                for f in files:
                    files_to_process.append((join(root, f), f))
        for fn, name in files_to_process:
            kind = identify_filename(name, peek_path=fn)
            if kind is None or kind.is_archive:
                continue
            file_summary = self.repack_zip_file(fn, def_options=options)
            if file_summary.results:
                res = file_summary.results[0]
                summary.results.append(res)
                summary.inner_count += 1
                summary.inner_insize += res.insize
                summary.inner_outsize += res.outsize
        summary.total_insize = summary.inner_insize
        summary.total_outsize = summary.inner_outsize
        return summary

    def repack_zip_file(
        self, filename: str, outfile: Optional[str] = None,
        def_options: Optional[OptionsInput] = None, *,
        on_progress: Optional[ProgressHook] = None,
    ) -> RepackSummary:
        from .format_support import format_scope, FormatLimit, OperationCancelled
        from .evidence import evidence_scope
        options = _normalize_options(def_options)
        started = time.monotonic()
        with format_scope(options):
            with diagnostic_scope() as diagnostics, evidence_scope() as evidence:
                try:
                    summary = self._repack_zip_file(
                        filename, outfile, options, on_progress=on_progress,
                    )
                except FormatLimit as exc:
                    source = normalize_path(filename)
                    size = os.path.getsize(source)
                    summary = _empty_summary(source, size)
                    cancelled = isinstance(exc, OperationCancelled)
                    summary.outcome = RepackOutcome(
                        source, source, 'cancelled' if cancelled else 'skipped', size, size,
                        'cancelled' if cancelled else 'resource_limit', str(exc),
                    )
                    summary.results.append(PackResult(
                        source, size, size, 0.0, replaced=False, reason=str(exc),
                        status=summary.outcome.status, reason_code=summary.outcome.reason_code,
                    ))
            if summary.outcome is None:
                self._set_outcome(summary, filename, options, diagnostics)
            assert summary.outcome is not None
            summary.outcome.source = normalize_path(filename)
            summary.outcome.destination = summary.filepath
            summary.outcome.elapsed_seconds = time.monotonic() - started
            from .format_support import current_budget
            budget = current_budget()
            summary.outcome.details.update(
                evidence=list(evidence),
                profile=options.get('profile'), profile_version=options.get('profile_version'),
                effective_options={key: value for key, value in options.items()
                                   if not key.startswith('_')},
                resources={'decoded_bytes': budget.decoded, 'scratch_written_bytes': budget.written,
                           'peak_live_scratch_bytes': budget.peak_scratch} if budget else {},
            )
            summary.elapsed_seconds = summary.outcome.elapsed_seconds
            _finalize_members(summary, options)
            return summary

    @staticmethod
    def _set_outcome(
        summary: RepackSummary, filename: str, options: Dict[str, Any],
        diagnostics: list,
    ) -> None:
        source = normalize_path(filename)
        kind = identify_filename(filename, peek_path=summary.filepath)
        transformed = summary.transformed or summary.total_insize != summary.total_outsize
        result = summary.results[0] if summary.results and not (kind and kind.is_archive) else None
        if result is not None and result.status:
            decision = Diagnostic(result.status, result.reason_code, result.reason)
        elif transformed:
            decision = Diagnostic('replaced', '', '')
        elif result is not None:
            decision = refusal(result.reason)
        elif diagnostics:
            decision = diagnostics[-1]
        elif kind is None:
            decision = Diagnostic('unsupported', 'unknown_format', 'No supported format detected')
        elif not kind.is_archive:
            decision = Diagnostic('failed', 'encoder_no_result', 'Encoder returned no result')
        else:
            decision = Diagnostic('unchanged', 'no_benefit', 'No accepted outer archive candidate')
        if options['dryrun'] and decision.status in ('replaced', 'unchanged'):
            decision = Diagnostic('predicted', decision.reason_code, decision.message)
        published = summary.published and decision.status in ('replaced', 'unchanged')
        summary.outcome = RepackOutcome(
            source, summary.filepath, decision.status,
            summary.total_insize, summary.total_outsize,
            decision.reason_code, decision.message, published=published,
            details=result.details if result else {},
        )
        for item in summary.results:
            if kind and kind.is_archive:
                # Members are staged inside an owned extraction tree; publication
                # belongs to the outer operation, and its identity survives cleanup.
                item.published = published and item.replaced
                item.status = ('predicted' if options['dryrun'] else
                               'replaced' if item.published else 'unchanged')
                if item.member:
                    item.source = source + '!/' + item.member
                    item.filepath = item.source
            else:
                item.status = decision.status
                item.published = published
                item.source = source
                item.reason_code = decision.reason_code

    def _repack_zip_file(
        self, filename: str, outfile: Optional[str] = None,
        def_options: Optional[OptionsInput] = None, *,
        on_progress: Optional[ProgressHook] = None,
    ) -> RepackSummary:
        """Validate, reserve and stage before publishing to the effective destination."""
        options = _normalize_options(def_options)
        initial_kind = identify_filename(filename, peek_path=normalize_path(filename))
        inspection_only = initial_kind and (initial_kind.packer or initial_kind.key) in {
            'safetensors', 'gguf', 'onnx',
        }
        source_snapshot = (None if inspection_only else
                           FileSnapshot.capture(normalize_path(filename)))
        plan = prepare_destination_plan(filename, outfile, options, check=False)
        kind = identify_filename(filename, peek_path=plan.source)
        if kind is None:
            _notify(on_progress, 'standalone', name=plan.source)
            size = os.path.getsize(plan.source)
            summary = _empty_summary(plan.source, size)
            summary.outcome = RepackOutcome(plan.source, plan.source, 'unsupported', size, size,
                                           'unknown_format', 'No qualified writer for this format')
            return summary
        if kind.family == 'cab':
            size = os.path.getsize(plan.source)
            summary = _empty_summary(plan.source, size)
            summary.outcome = RepackOutcome(plan.source, plan.source, 'unsupported', size, size,
                                           'no_cab_writer', 'No qualified CAB writer is available')
            return summary
        if kind and kind.packer == 'tracev3':
            from .tracev3 import destination_refusal
            reason = destination_refusal(plan.source, plan.output, plan.backup)
            if reason:
                size = os.path.getsize(plan.source)
                summary = _empty_summary(plan.source, size)
                summary.outcome = RepackOutcome(plan.source, plan.source, 'skipped', size, size,
                                               'active_log_store', reason)
                return summary
        if kind and (kind.packer or kind.key) in ('sqlite', 'sqlite3', 'gpkg', 'mbtiles'):
            from .data import sqlite_eligibility
            reason = sqlite_eligibility(plan.source, plan.output, options)
            if reason:
                size = os.path.getsize(plan.source)
                summary = _empty_summary(plan.source, size)
                summary.outcome = RepackOutcome(
                    plan.source, plan.source, 'skipped', size, size,
                    'sqlite_offline_required', reason,
                )
                return summary
        if kind and (kind.packer or kind.key) in {'safetensors', 'gguf', 'onnx'}:
            # These profiles only inspect bounded headers. Avoid hashing and
            # copying multi-gigabyte payloads when no writer is registered.
            size = os.path.getsize(plan.source)
            summary = self._process_work(plan.source, kind, options, size, on_progress)
            summary.filepath = plan.source
            for result in summary.results:
                result.filepath = plan.source
                result.replaced = False
            return summary
        assert source_snapshot is not None
        with PathReservation(plan.paths, dryrun=options['dryrun'],
                             source_snapshot=source_snapshot) as reservation:
            plan.validate()
            kind = identify_filename(filename, peek_path=plan.source)
            if options['dryrun'] and _is_scientific(kind):
                summary = self._process_work(plan.source, kind, options,
                                             os.path.getsize(plan.source), on_progress)
                reservation.require_source_unchanged()
                summary.filepath = plan.output
                return summary
            if plan.backup and not options['dryrun']:
                reservation.publish_copy(plan.source, plan.backup)
            return self._stage_request(plan, kind, options, reservation, on_progress)

    def _stage_request(
        self, plan: DestinationPlan, kind: Optional[FileKind], options: Dict[str, Any],
        reservation: PathReservation, on_progress: Optional[ProgressHook],
    ) -> RepackSummary:
        f_insize = os.path.getsize(plan.source)
        if _retains_rejected_source(kind):
            from .format_support import format_scope, FormatLimit, unchanged
            with format_scope(options) as budget:
                try:
                    budget.consume(written=f_insize)
                except FormatLimit as exc:
                    reservation.require_source_unchanged()
                    result = unchanged(plan.source, str(exc))
                    return RepackSummary(filepath=plan.source, results=[result],
                                         total_insize=f_insize, total_outsize=f_insize)
        # Encoders can rename/delete only this private copy, including on outer dry-run.
        os.makedirs(self.temppath, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='filerepack-work-', dir=self.temppath) as workspace:
            from .format_support import own_scratch
            own_scratch(workspace)
            work = os.path.join(workspace, os.path.basename(plan.source))
            original_digest = _stage_source(plan, kind, work)
            f_insize = os.path.getsize(work)
            work_options = _work_options(plan, kind, options)
            def progress(
                event: str, *, current: int = 0, total: int = 0, name: str = '',
            ) -> None:
                if on_progress is not None:
                    on_progress(event, current=current, total=total,
                                name=plan.source if name == work else name)

            with diagnostic_scope() as diagnostics:
                summary = self._process_work(
                    work, kind, work_options, f_insize,
                    progress if on_progress is not None else None,
                )
            candidate = summary.filepath
            accepted = _accepted_stage(summary, kind, work, original_digest)
            effective = plan.output
            if accepted and candidate != work:
                effective = plan.converted or plan.output
                if os.path.splitext(candidate)[1].lower() != os.path.splitext(effective)[1].lower():
                    raise ValueError(
                        'Conversion route changed after preflight; publication refused',
                    )
            if not accepted:
                if summary.outcome is None and _refused_stage(summary, diagnostics):
                    self._set_outcome(summary, plan.source, options, diagnostics)
                # A WAL snapshot contains committed pages absent from the main
                # source file. Publish that snapshot even when VACUUM has no gain.
                candidate = work if _is_sqlite(kind) else plan.source
                summary.total_outsize = f_insize
                refused = bool(summary.outcome and summary.outcome.status in (
                    'failed', 'unsupported', 'cancelled', 'skipped',
                ))
                if _retains_rejected_source(kind) or refused:
                    reservation.require_source_unchanged()
                    summary.filepath = plan.source
                    for result in summary.results:
                        result.filepath = plan.source
                        result.replaced = False
                    return summary
            reservation.require_source_unchanged()
            if not options['dryrun'] and (accepted or effective != plan.source):
                from .format_support import check_cancelled
                check_cancelled()
                reservation.publish_copy(
                    candidate, effective,
                    overwrite=effective == plan.source or options['overwrite'],
                )
                if effective != plan.source and plan.output == plan.source and accepted:
                    reservation.require_source_unchanged()
                    _remove_quietly(plan.source)
            summary.filepath = effective
            summary.transformed = accepted
            summary.published = not options['dryrun'] and (
                accepted or effective != plan.source
            )
            if not (kind and kind.is_archive):
                for result in summary.results:
                    result.filepath = effective
                    result.replaced = not options['dryrun'] and accepted
            return summary

    def _process_work(
        self, filename: str, kind: Optional[FileKind], options: Dict[str, Any],
        f_insize: int, on_progress: Optional[ProgressHook],
    ) -> RepackSummary:
        from .format_support import current_budget
        budget = current_budget()
        if budget:
            budget.depth(options.get('_optimization_depth', 0))
        if kind is None:
            _notify(on_progress, 'standalone', name=filename)
            return _empty_summary(filename, f_insize)

        if kind.is_archive:
            with candidate_scope(filename):
                return self._repack_container(
                    filename, filename, f_insize, kind.key, options,
                    family=kind.family, on_progress=on_progress,
                )

        packer_key = kind.packer or kind.key
        _notify(on_progress, 'standalone', name=filename)
        with diagnostic_scope() as diagnostics:
            standalone = _dispatch_packer(packer_key, filename, options)
        if standalone is not None or packer_key in _PACKERS:
            summary = RepackSummary(filepath=filename, total_insize=f_insize)
            if standalone is None:
                summary.total_outsize = f_insize
                decision = next((item for item in reversed(diagnostics)
                                 if item.status == 'cancelled'), next(
                                (item for item in reversed(diagnostics)
                                 if item.status == 'failed'),
                                diagnostics[-1] if diagnostics else Diagnostic(
                                    'failed', 'encoder_no_result', 'Encoder returned no result',
                                )))
                summary.outcome = RepackOutcome(
                    filename, filename, decision.status, f_insize, f_insize,
                    decision.reason_code, decision.message,
                )
                return summary
            summary.total_outsize = standalone.outsize
            summary.filepath = standalone.filepath
            summary.results.append(standalone)
            return summary

        return _empty_summary(filename, f_insize)

    def repack(
        self, filename: str, outfile: Optional[str] = None,
        options: Optional[OptionsInput] = None, *,
        on_progress: Optional[ProgressHook] = None,
    ) -> RepackSummary:
        """Library-facing alias for repack_zip_file."""
        return self.repack_zip_file(
            filename, outfile=outfile, def_options=options,
            on_progress=on_progress,
        )


    def _deep_walk(
        self, fpath: str, options: Dict[str, Any], summary: RepackSummary,
        on_progress: Optional[ProgressHook] = None,
    ) -> None:
        items = []
        for root, dirs, files in os.walk(fpath):
            for name in files:
                fullname = os.path.join(root, name)
                relative = os.path.relpath(fullname, fpath).replace(os.sep, '/')
                if relative in options.get('_protected_members', ()):
                    continue
                kind = identify_filename(name, peek_path=fullname)
                if kind is None:
                    continue
                if kind.is_archive and not options.get('pack_archives', True):
                    continue
                if excluded_member(relative, options) or not depth_enabled(
                    options.get('_optimization_depth', 0) + 1, options,
                ):
                    size = os.path.getsize(fullname)
                    summary.member_outcomes.append(RepackOutcome(
                        relative, relative, 'skipped', size, size, 'member_selection',
                        'Member excluded by pattern or optimization depth', member=relative,
                    ))
                    continue
                items.append((fullname, name, kind))
        _notify(on_progress, 'files', current=0, total=len(items))
        for i, (fullname, name, kind) in enumerate(items, 1):
            before = len(summary.results)
            before_members = len(summary.member_outcomes)
            self._process_walk_item(
                fullname, kind, {**options, '_optimization_depth':
                                options.get('_optimization_depth', 0) + 1}, summary,
            )
            relative = os.path.relpath(fullname, fpath).replace(os.sep, '/')
            for member in summary.member_outcomes[before_members:]:
                member.member = relative + '!/' + (member.member or '')
            for result in summary.results[before:]:
                result.member = os.path.relpath(fullname, fpath).replace(os.sep, '/')
                result.source = result.member
                status = result.status or ('replaced' if result.replaced else
                                           refusal(result.reason).status)
                summary.member_outcomes.append(RepackOutcome(
                    result.member, result.member, status, result.insize, result.outsize,
                    result.reason_code, result.reason, member=result.member,
                    details=result.details,
                ))
            _notify(on_progress, 'file', current=i, total=len(items), name=name)

    def _process_walk_item(
        self, fullname: str, kind: FileKind, options: Dict[str, Any],
        summary: RepackSummary,
    ) -> None:
        if kind.is_archive:
            nested = self.repack_zip_file(fullname, fullname, options)
            summary.member_outcomes.extend(nested.member_outcomes)
            if nested.total_insize:
                summary.results.append(PackResult(
                    fullname, nested.total_insize, nested.total_outsize,
                    nested.total_savings_pct,
                    replaced=bool(nested.outcome and nested.outcome.status == 'replaced'),
                    status=nested.outcome.status if nested.outcome else None,
                    reason=nested.outcome.reason if nested.outcome else '',
                    reason_code=nested.outcome.reason_code if nested.outcome else '',
                ))
                summary.inner_count += 1
                summary.inner_insize += nested.total_insize
                summary.inner_outsize += nested.total_outsize
            return
        res = _dispatch_packer(kind.packer or kind.key, fullname,
                               {**options, '_nested_member': True})
        if res is not None:
            summary.results.append(res)
            summary.inner_count += 1
            summary.inner_insize += res.insize
            summary.inner_outsize += res.outsize


def pack_file_simple(
    filepath: str,
    pack_fn: Callable[..., Optional[Union[PackResult, Tuple[str, int, int, float]]]],
    **kwargs: Any,
) -> Optional[PackResult]:
    result = pack_fn(filepath, **kwargs)
    if result is None:
        return None
    if isinstance(result, PackResult):
        return result
    return PackResult(
        filepath=result[0], insize=result[1], outsize=result[2],
        savings_pct=result[3],
    )
