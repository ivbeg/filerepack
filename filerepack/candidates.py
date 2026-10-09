"""Shared candidate staging, verification, acceptance and publication."""

import os
import logging
import tempfile
from dataclasses import dataclass
from os.path import abspath
from shutil import rmtree
from typing import Optional, TypedDict, cast

from .destinations import PathReservation
from .models import PackResult
from .outcomes import record
from .transactions import FileSnapshot, check_inplace_source, publish_candidate, source_scope
from .transactions import make_temp as allocate_temp
from .transactions import make_temp_dir as allocate_temp_dir
from .transactions import own_sidecar as own_sidecar
from .utils import verify_output
from .verification import verify_preservation

TEMP_PATH = tempfile.gettempdir()
COPY_BUF = 1024 * 1024


@dataclass(frozen=True)
class VerifiedCandidate:
    """Exact file snapshots bound to a completed independent preservation check."""

    kind: str
    source: FileSnapshot
    candidate: FileSnapshot

    def require_matches(self, source: str, candidate: str, kind: str) -> None:
        if (kind != self.kind or abspath(source) != self.source.path
                or abspath(candidate) != self.candidate.path):
            raise ValueError('Verified candidate does not match this validation request')
        self.source.require_unchanged()
        self.candidate.require_unchanged()


class CommitArguments(TypedDict):
    dryrun: bool
    keep_if_larger: bool
    min_savings: Optional[float]


def calc_savings(insize: int, outsize: int) -> float:
    if insize > 0:
        return (insize - outsize) * 100.0 / insize
    return 0.0


def remove_quietly(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.isdir(path):
            rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def make_temp(suffix: str) -> str:
    return allocate_temp(suffix, directory=TEMP_PATH)


def make_temp_dir(prefix: str = 'filerepack-', *, directory: Optional[str] = None) -> str:
    return allocate_temp_dir(prefix, directory=directory if directory is not None else TEMP_PATH)


def commit_kwargs(**kwargs: object) -> CommitArguments:
    return {
        'dryrun': bool(kwargs.get('dryrun', False)),
        'keep_if_larger': bool(kwargs.get('keep_if_larger', True)),
        'min_savings': cast(Optional[float], kwargs.get('min_savings')),
    }


def _verify_candidate(
    candidate: str, original: str, destination: str, kind: str,
    lossless: bool, verified: Optional[VerifiedCandidate],
) -> bool:
    if verified is not None:
        verified.require_matches(original, candidate, kind)
        from .evidence import validation
        validation(kind, 'structure', True)
        if lossless:
            validation(kind, 'preservation', True)
        return True
    if kind in ('dcm', 'dicom', 'dic'):
        if not verify_output(candidate, kind, source_path=destination):
            record('failed', 'verification_failed', 'DICOM candidate verification failed')
            return False
    elif not verify_output(candidate, kind):
        record('failed', 'verification_failed', 'Candidate structural validation failed')
        return False
    if lossless and not verify_preservation(original, candidate, kind):
        record('failed', 'preservation_failed', 'Candidate preservation validation failed')
        return False
    return True


def commit_output(
    temp_path: str,
    dest_path: str,
    insize: int,
    *,
    dryrun: bool = False,
    keep_if_larger: bool = True,
    min_savings: Optional[float] = None,
    verify: Optional[str] = None,
    reservation: Optional[PathReservation] = None,
    overwrite: bool = False,
    rejected_path: Optional[str] = None,
    lossless: bool = False,
    reference_path: Optional[str] = None,
    verified: Optional[VerifiedCandidate] = None,
) -> Optional[PackResult]:
    """Replace dest with temp only after verification and size checks."""
    try:
        if not temp_path or not os.path.exists(temp_path):
            record('failed', 'missing_candidate', 'Encoder did not produce a candidate')
            return None
        if os.path.getsize(temp_path) == 0:
            record('failed', 'empty_candidate', 'Encoder produced an empty candidate')
            return None
        candidate_snapshot = FileSnapshot.capture(temp_path)
        if not verify:
            record('unsupported', 'missing_validator', 'Writer did not declare a validator')
            logging.warning('Candidate validation refused: writer did not declare a validator')
            return None
        scope = source_scope()
        original = reference_path or (scope.snapshot.path if scope else dest_path)
        if not _verify_candidate(temp_path, original, dest_path, verify, lossless, verified):
            return None

        outsize = os.path.getsize(temp_path)
        share = calc_savings(insize, outsize)
        reason = ''
        if keep_if_larger and outsize >= insize:
            reason = (f'No size reduction: verified candidate is {outsize} bytes '
                      f'(source: {insize} bytes)')
        elif min_savings is not None and share < min_savings:
            reason = (f'Candidate savings {share:.2f}% are below the required '
                      f'{min_savings:g}%')

        if dryrun:
            if reason:
                return PackResult(rejected_path or dest_path, insize, insize, 0.0,
                                  replaced=False, reason=reason)
            return PackResult(dest_path, insize, outsize, share, replaced=False,
                              reason='Dry-run: verified candidate; source retained')

        if reason:
            return PackResult(rejected_path or dest_path, insize, insize, 0.0,
                              replaced=False, reason=reason)

        dest_dir = os.path.dirname(abspath(dest_path)) or '.'
        os.makedirs(dest_dir, exist_ok=True)
        if reservation is not None:
            scope = source_scope()
            reservation.publish_copy(temp_path, dest_path, overwrite=overwrite,
                                     metadata=scope.snapshot.metadata if scope else None,
                                     candidate_snapshot=candidate_snapshot)
        else:
            check_inplace_source(dest_path)
            scope = source_scope()
            snapshot = scope.snapshot if scope else FileSnapshot.capture(dest_path)
            publish_candidate(temp_path, dest_path, metadata=snapshot.metadata,
                              guards=[snapshot], overwrite=True,
                              candidate_snapshot=candidate_snapshot)
        if scope is not None:
            scope.published = True
        return PackResult(dest_path, insize, outsize, share, replaced=True)
    finally:
        remove_quietly(temp_path)
