"""Documents packers using the shared candidate lifecycle."""

import logging
import os
from os.path import abspath
from typing import Any, Dict, List, Optional, Tuple

from . import candidates as tx
from .commands import run_command as _run_command
from .models import PackResult
from .tools import resolve_tool
from .transactions import guard_packer
from .consts import DEFAULT_LOSSY_PDF_PROFILE
from .validation import normalize_pdf_profile
from .pdf_verify import inspect_pdf, pdf_fingerprint
from .utils import verify_output


def jpeg_quality_to_qfactor(quality: int) -> float:
    """Map JPEG quality 1-100 to a Ghostscript Distiller QFactor."""
    q = max(1, min(100, int(quality)))
    return round(0.15 + (100 - q) * (2.25 / 99.0), 3)


def build_gs_pdf_cmd(
    gs_path: str,
    src: str,
    dest: str,
    profile: str = DEFAULT_LOSSY_PDF_PROFILE,
    jpeg_quality: Optional[int] = None,
) -> List[str]:
    """Ghostscript pdfwrite command for lossy PDF recompression."""
    cmd = [
        gs_path, '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
        f'-dPDFSETTINGS=/{profile}', '-dNOPAUSE', '-dQUIET', '-dBATCH',
        '-dAutoRotatePages=/None', f'-sOutputFile={dest}',
    ]
    if jpeg_quality is None:
        cmd.append(src)
        return cmd
    qfactor = jpeg_quality_to_qfactor(jpeg_quality)
    image_dict = (
        f'<</QFactor {qfactor} /Blend 1 /HSamples [2 1 1 2] '
        f'/VSamples [2 1 1 2]>>'
    )
    cmd.extend([
        '-dAutoFilterColorImages=false',
        '-dAutoFilterGrayImages=false',
        '-dColorImageFilter=/DCTEncode',
        '-dGrayImageFilter=/DCTEncode',
        '-c',
        (
            f'<</ColorACSImageDict {image_dict} '
            f'/GrayACSImageDict {image_dict} '
            f'/ColorImageDict {image_dict} '
            f'/GrayImageDict {image_dict}>> setdistillerparams'
        ),
        '-f', src,
    ])
    return cmd


def _maybe_walk_pdf_images(
    abs_in: str, debug: bool, quiet: bool, commit: Dict[str, Any],
) -> Tuple[str, Optional[str]]:
    """Lossless pikepdf image-stream walk. Returns (source, temp-or-None)."""
    if not commit.get('pack_images', True):
        return abs_in, None
    from .format_support import run_operation
    walked = tx.make_temp('.pdf')
    options = {
        **commit,
        'debug': debug, 'quiet': quiet, 'pack_images': True,
        'keep_meta': bool(commit.get('keep_meta', False)),
        'ultra': bool(commit.get('ultra', False)),
    }
    try:
        result = run_operation('pdf-native', 'rewrite', abs_in, walked, options)
    except (OSError, ValueError, ImportError) as exc:
        logging.warning('PDF image worker skipped: %s', exc)
        tx.remove_quietly(walked)
        return abs_in, None
    changed = result.get('changed', False)
    commit['_pdf_work'] = result.get('details', {})
    if changed:
        return walked, walked
    tx.remove_quietly(walked)
    return abs_in, None


def _qpdf_candidate(
    tool: str, source: str, linearize: bool, debug: bool, quiet: bool,
) -> Optional[str]:
    output = tx.make_temp('.pdf')
    command = [tool, '--object-streams=generate', '--compress-streams=y']
    if linearize:
        command.append('--linearize')
    command.extend([source, output])
    if _run_command(command, quiet=quiet, debug=debug) is not None:
        return output
    tx.remove_quietly(output)
    return None


def _valid_pdf_alternatives(alternatives: List[str], expected: object,
                            linearize: bool) -> List[str]:
    valid = []
    for candidate in alternatives:
        try:
            inspection = inspect_pdf(candidate)
            if (inspection.rewritable and (not linearize or inspection.linearized)
                    and pdf_fingerprint(candidate) == expected):
                valid.append(candidate)
        except Exception as exc:
            logging.warning('PDF candidate preservation check failed: %s', exc)
    return valid


def _qpdf_linearize(
    qpdf_path: Optional[str], walk_src: str, walked: Optional[str],
    filepath: str, insize: int, debug: bool, quiet: bool, ck: tx.CommitArguments,
    *, linearize: bool = False,
) -> Optional[PackResult]:
    alternatives = [walked] if walked else []
    try:
        if qpdf_path:
            # Retain both encodings: walking can help streams but hurt PDF layout.
            sources = [abspath(filepath), walk_src] if walked else [walk_src]
            for source in dict.fromkeys(sources):
                candidate = _qpdf_candidate(qpdf_path, source, linearize, debug, quiet)
                if candidate:
                    alternatives.append(candidate)
        if not alternatives:
            return None
        valid = _valid_pdf_alternatives(alternatives, pdf_fingerprint(filepath), linearize)
        if not valid:
            logging.warning('PDF candidates failed structure/preservation/linearization checks')
            return None
        best = min(valid, key=os.path.getsize)
        if (not linearize or inspect_pdf(filepath).linearized) and os.path.getsize(best) >= insize:
            return PackResult(filepath, insize, insize, 0.0, replaced=False)
        return tx.commit_output(best, filepath, insize, verify='pdf', lossless=True, **ck)
    except Exception as exc:
        logging.warning('PDF preservation verification unavailable/failed: %s', exc)
        return None
    finally:
        for candidate in alternatives:
            tx.remove_quietly(candidate)


def _gs_pdf(
    gs_path: Optional[str], abs_in: str, filepath: str, insize: int,
    gs_profile: str, jpeg_quality: Optional[int],
    debug: bool, quiet: bool, ck: tx.CommitArguments,
    *, linearize: bool = False, qpdf_path: Optional[str] = None,
) -> Optional[PackResult]:
    if not gs_path or (linearize and not qpdf_path):
        return None
    output = tx.make_temp('.pdf')
    linearized = None
    try:
        cmd = build_gs_pdf_cmd(gs_path, abs_in, output, profile=gs_profile,
                               jpeg_quality=jpeg_quality)
        if _run_command(cmd, quiet=quiet, debug=debug) is None:
            return None
        if not verify_output(output, 'pdf'):
            return None
        if linearize and qpdf_path:
            linearized = _qpdf_candidate(qpdf_path, output, True, debug, quiet)
            if not linearized or not _valid_pdf_alternatives(
                [linearized], pdf_fingerprint(output), True,
            ):
                return None
            # The qpdf step must preserve the explicitly lossy Ghostscript result.
            return tx.commit_output(linearized, filepath, insize, verify='pdf',
                                    lossless=True, reference_path=output, **ck)
        return tx.commit_output(output, filepath, insize, verify='pdf', **ck)
    finally:
        tx.remove_quietly(output)
        tx.remove_quietly(linearized)


@guard_packer
def pack_pdf(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, pdf_profile: Optional[str] = None,
    jpeg_quality: Optional[int] = None, **commit: Any,
) -> Optional[PackResult]:
    """Compress PDF. Default is lossless qpdf; Ghostscript is opt-in lossy."""
    insize = os.path.getsize(filepath)
    inspection = inspect_pdf(abspath(filepath))
    if not inspection.rewritable:
        logging.warning('PDF rewriting skipped: %s', inspection.reason)
        return None
    linearize = commit.get('pdf_linearize', False)
    if type(linearize) is not bool:
        raise ValueError('pdf_linearize must be a boolean')
    gs_path = resolve_tool('gs')
    qpdf_path = resolve_tool('qpdf')
    if gs_path is None and qpdf_path is None:
        if debug:
            logging.warning('Neither ghostscript nor qpdf is installed')
        return None

    try:
        profile = normalize_pdf_profile(pdf_profile)
    except ValueError:
        if debug:
            logging.warning('Unknown PDF profile %s', pdf_profile)
        return None

    abs_in = abspath(filepath)
    ck = tx.commit_kwargs(**commit)
    use_gs = bool(lossy or profile is not None or jpeg_quality is not None)
    gs_profile = profile or DEFAULT_LOSSY_PDF_PROFILE
    walk_src, walked = abs_in, None
    if not use_gs:
        walk_src, walked = _maybe_walk_pdf_images(abs_in, debug, quiet, commit)

    if use_gs:
        gs_result = _gs_pdf(
            gs_path, abs_in, filepath, insize, gs_profile, jpeg_quality,
            debug, quiet, ck, linearize=linearize, qpdf_path=qpdf_path,
        )
        if gs_result:
            return gs_result
    result = _qpdf_linearize(
        qpdf_path, walk_src, walked, filepath, insize, debug, quiet, ck,
        linearize=linearize,
    )
    if result is not None:
        result.details['pdf_images'] = commit.get('_pdf_work', {})
    return result


@guard_packer
def pack_ai(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, pdf_profile: Optional[str] = None,
    jpeg_quality: Optional[int] = None, **commit: Any,
) -> Optional[PackResult]:
    """Illustrator files that are PDF wrappers go through the PDF packer."""
    if not _is_pdf_header(filepath):
        return None
    return pack_pdf(
        filepath, debug=debug, quiet=quiet, lossy=lossy,
        pdf_profile=pdf_profile, jpeg_quality=jpeg_quality, **commit
    )


def _is_pdf_header(path: str) -> bool:
    try:
        with open(path, 'rb') as fh:
            head = fh.read(1024)
    except OSError:
        return False
    return head.lstrip().startswith(b'%PDF') or b'%PDF-' in head[:1024]
