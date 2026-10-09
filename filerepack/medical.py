"""Medical packers using the shared candidate lifecycle."""

import logging
import os
from os.path import abspath
from typing import Any, Optional

from . import candidates as tx
from .commands import run_command as _run_command
from .models import PackResult
from .tools import resolve_tool
from .transactions import guard_packer


@guard_packer
def pack_dcm(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Lossless JPEG-LS recompress of uncompressed/RLE image DICOM.

    ``lossy`` in *commit* is ignored; DICOM is never lossy-encoded.
    """
    from .dicom import inspect_dicom
    from .dicom_verify import verification_ready
    logger = logging.getLogger(__name__)
    inspection = inspect_dicom(filepath)
    if not inspection.eligible:
        log = logger.warning if 'unavailable' in inspection.reason else logger.info
        log('DICOM skipped: %s', inspection.reason)
        return None
    verification = verification_ready(filepath)
    if not verification.eligible:
        logger.warning('DICOM skipped: %s', verification.reason)
        return None
    gdcm = resolve_tool('gdcmconv')
    dcmcjpls = resolve_tool('dcmcjpls')
    tool = gdcm or dcmcjpls
    if tool is None:
        return None
    insize = os.path.getsize(filepath)
    out_temp = tx.make_temp('.dcm')
    abs_in = abspath(filepath)
    if gdcm:
        cmd = [gdcm, '--jpegls', '--use-dict', abs_in, out_temp]
    else:
        cmd = [tool, abs_in, out_temp]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        logger.warning('DICOM encoder failed; source retained')
        tx.remove_quietly(out_temp)
        return None
    return tx.commit_output(
        out_temp, filepath, insize, verify='dcm', **tx.commit_kwargs(**commit)
    )
