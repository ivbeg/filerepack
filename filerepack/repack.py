#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import gzip
import logging
import lzma
import bz2
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from os.path import abspath, exists, isfile, join
from os import listdir, walk
from shutil import copyfile, copyfileobj, rmtree
from typing import Any, Callable, Dict, List, Optional, Tuple

from .consts import (
    ARCHIVE_EXTS, DEFAULT_JPEG_QUALITY, DEFAULT_MAX_EXTRACT_BYTES,
    DEFAULT_MAX_EXTRACT_RATIO, SUPPORTED_EXTS, ZIP_SENSITIVE_EXTS,
)
from .models import PackResult, RepackOptions, RepackSummary
from .tools import resolve_szip, resolve_tool
from .utils import (
    dir_total_size, extract_exceeds_limit, verify_output, zip_uncompressed_size,
)

TEMP_PATH = tempfile.gettempdir()
_COPY_BUF = 1024 * 1024


def _expand_globs(cmd: List[str], cwd: Optional[str] = None) -> List[str]:
    """Expand a bare '*' argument only (archive contents). Never glob filenames."""
    if cwd is None:
        cwd = os.getcwd()
    expanded: List[str] = []
    for arg in cmd:
        if arg == '*':
            matches = glob.glob(os.path.join(cwd, '*'))
            if matches:
                expanded.extend(os.path.relpath(m, cwd) for m in sorted(matches))
            else:
                expanded.append(arg)
        else:
            expanded.append(arg)
    return expanded


def _run_command(
    cmd: List[str],
    quiet: bool = False,
    debug: bool = False,
    cwd: Optional[str] = None,
) -> Optional[subprocess.CompletedProcess]:
    """Run an external command with an argv list. Never uses a shell."""
    cmd = _expand_globs(cmd, cwd)
    if debug:
        logging.info('command: %s', ' '.join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=cwd,
            timeout=3600,
        )
        if result.returncode == 0:
            return result
        if debug:
            logging.warning(
                'command failed with return code %d: %s',
                result.returncode, ' '.join(cmd),
            )
        return None
    except (OSError, subprocess.TimeoutExpired) as exc:
        if debug:
            logging.warning('command exception: %s', str(exc))
        return None


def _calc_savings(insize: int, outsize: int) -> float:
    if insize > 0:
        return (insize - outsize) * 100.0 / insize
    return 0.0


def _remove_quietly(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.isdir(path):
            rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _make_temp(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, dir=TEMP_PATH)
    os.close(fd)
    return path


def _commit_kwargs(**kwargs: Any) -> Dict[str, Any]:
    return {
        'dryrun': bool(kwargs.get('dryrun', False)),
        'keep_if_larger': kwargs.get('keep_if_larger', True),
        'min_savings': kwargs.get('min_savings'),
    }


def _commit_output(
    temp_path: str,
    dest_path: str,
    insize: int,
    *,
    dryrun: bool = False,
    keep_if_larger: bool = True,
    min_savings: Optional[float] = None,
    verify: Optional[str] = None,
) -> Optional[PackResult]:
    """Replace dest with temp only after verification and size checks."""
    try:
        if not temp_path or not os.path.exists(temp_path):
            return None
        if os.path.getsize(temp_path) == 0:
            return None
        if verify and not verify_output(temp_path, verify):
            return None

        outsize = os.path.getsize(temp_path)
        share = _calc_savings(insize, outsize)
        reject = False
        if keep_if_larger and outsize >= insize:
            reject = True
        if min_savings is not None and share < min_savings:
            reject = True

        if dryrun:
            if reject:
                return PackResult(dest_path, insize, insize, 0.0, replaced=False)
            return PackResult(dest_path, insize, outsize, share, replaced=False)

        if reject:
            return PackResult(dest_path, insize, insize, 0.0, replaced=False)

        dest_dir = os.path.dirname(abspath(dest_path)) or '.'
        os.makedirs(dest_dir, exist_ok=True)
        os.replace(temp_path, dest_path)
        outsize = os.path.getsize(dest_path)
        share = _calc_savings(insize, outsize)
        return PackResult(dest_path, insize, outsize, share, replaced=True)
    finally:
        _remove_quietly(temp_path)


def _run_to_file(cmd: List[str], out_path: str, debug: bool = False) -> bool:
    if debug:
        logging.info('command: %s', ' '.join(cmd))
    try:
        with open(out_path, 'wb') as fh:
            result = subprocess.run(
                cmd, stdout=fh, stderr=subprocess.PIPE, timeout=3600
            )
        return result.returncode == 0 and os.path.getsize(out_path) > 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        if debug:
            logging.warning('command exception: %s', str(exc))
        return False


def _pack_stream_codec(
    filepath: str,
    suffix: str,
    open_decomp: Callable,
    open_comp: Callable,
    cli_key: Optional[str],
    cli_args: List[str],
    verify: str,
    debug: bool = False,
    quiet: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    """Decompress to a temp file, recompress, then atomic-replace."""
    insize = os.path.getsize(filepath)
    dec_temp = _make_temp('.bin')
    out_temp = _make_temp(suffix)
    try:
        with open_decomp(filepath, 'rb') as f_in, open(dec_temp, 'wb') as f_out:
            copyfileobj(f_in, f_out, length=_COPY_BUF)

        used_cli = False
        tool = resolve_tool(cli_key) if cli_key else None
        if tool:
            used_cli = _run_to_file([tool] + cli_args + [dec_temp], out_temp, debug)

        if not used_cli:
            with open(dec_temp, 'rb') as f_in, open_comp(out_temp) as f_out:
                copyfileobj(f_in, f_out, length=_COPY_BUF)

        return _commit_output(
            out_temp, filepath, insize, verify=verify, **_commit_kwargs(**commit)
        )
    except Exception as exc:
        if debug:
            logging.warning('%s repack failed: %s', suffix, exc)
        return None
    finally:
        _remove_quietly(dec_temp)
        _remove_quietly(out_temp)


def pack_parquet(
    filepath: str, debug: bool = False, quiet: bool = False,
    ultra: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Lossless compress parquet file using the duckdb Python API."""
    try:
        import duckdb
    except ImportError:
        logging.warning('duckdb not installed, cannot compress parquet files')
        return None

    insize = os.path.getsize(filepath)
    tempfpath = _make_temp('.parquet')
    c_level = 22 if ultra else 19
    try:
        abs_in = abspath(filepath).replace('\\', '/')
        abs_out = abspath(tempfpath).replace('\\', '/')
        escaped_in = abs_in.replace("'", "''")
        escaped_out = abs_out.replace("'", "''")
        sql_cmd = (
            f"COPY (SELECT * FROM read_parquet('{escaped_in}')) "
            f"TO '{escaped_out}' (FORMAT parquet, COMPRESSION zstd, "
            f"COMPRESSION_LEVEL {c_level})"
        )
        if debug:
            logging.info('parquet sql: %s', sql_cmd)
        con = duckdb.connect()
        try:
            con.execute(sql_cmd)
        finally:
            con.close()
        return _commit_output(
            tempfpath, filepath, insize, verify='parquet',
            **_commit_kwargs(**commit),
        )
    except Exception as exc:
        if debug:
            logging.warning('parquet compression failed: %s', exc)
        return None
    finally:
        _remove_quietly(tempfpath)


def pack_gzip(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    def _gz_out(path: str):
        return gzip.open(path, 'wb', compresslevel=9)

    return _pack_stream_codec(
        filepath, '.gz', gzip.open, _gz_out, 'pigz', ['-9', '-c'],
        'gz', debug=debug, quiet=quiet, **commit,
    )


def pack_xz(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    def _xz_out(path: str):
        return lzma.open(path, 'wb', preset=9)

    return _pack_stream_codec(
        filepath, '.xz', lzma.open, _xz_out, 'xz', ['-9', '-c'],
        'xz', debug=debug, quiet=quiet, **commit,
    )


def pack_bz2(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    def _bz_out(path: str):
        return bz2.open(path, 'wb', compresslevel=9)

    return _pack_stream_codec(
        filepath, '.bz2', bz2.open, _bz_out, 'bzip2', ['-9', '-c'],
        'bz2', debug=debug, quiet=quiet, **commit,
    )


def pack_zstd(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    zstd = resolve_tool('zstd')
    if zstd is None:
        if debug:
            logging.warning('zstd not installed')
        return None
    insize = os.path.getsize(filepath)
    dec_temp = _make_temp('.bin')
    out_temp = _make_temp('.zst')
    try:
        if not _run_to_file([zstd, '-d', '-c', filepath], dec_temp, debug):
            return None
        if not _run_to_file([zstd, '-19', '-c', dec_temp], out_temp, debug):
            return None
        return _commit_output(
            out_temp, filepath, insize, verify='zst', **_commit_kwargs(**commit)
        )
    finally:
        _remove_quietly(dec_temp)
        _remove_quietly(out_temp)


def pack_brotli(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    brotli = resolve_tool('brotli')
    if brotli is None:
        if debug:
            logging.warning('brotli not installed')
        return None
    insize = os.path.getsize(filepath)
    dec_temp = _make_temp('.bin')
    out_temp = _make_temp('.br')
    try:
        if not _run_to_file([brotli, '-d', '-c', filepath], dec_temp, debug):
            return None
        if not _run_to_file([brotli, '-q', '11', '-c', dec_temp], out_temp, debug):
            return None
        return _commit_output(out_temp, filepath, insize, **_commit_kwargs(**commit))
    finally:
        _remove_quietly(dec_temp)
        _remove_quietly(out_temp)


def pack_avif(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    avifenc = resolve_tool('avifenc')
    avifdec = resolve_tool('avifdec')
    convert_path = resolve_tool('convert')
    if (avifenc is None or avifdec is None) and convert_path is None:
        if debug:
            logging.warning('avifenc/avifdec or ImageMagick not installed')
        return None
    insize = os.path.getsize(filepath)
    ck = _commit_kwargs(**commit)
    if avifenc and avifdec:
        png_temp = _make_temp('.png')
        out_temp = _make_temp('.avif')
        try:
            decode = _run_command(
                [avifdec, abspath(filepath), png_temp], quiet=quiet, debug=debug
            )
            if decode is None:
                return None
            if lossy:
                encode_cmd = [avifenc, '-q', '80', png_temp, out_temp]
            else:
                encode_cmd = [avifenc, '--lossless', png_temp, out_temp]
            encode = _run_command(encode_cmd, quiet=quiet, debug=debug)
            if encode is None:
                _remove_quietly(out_temp)
                return None
            return _commit_output(
                out_temp, filepath, insize, verify='avif', **ck
            )
        finally:
            _remove_quietly(png_temp)
            _remove_quietly(out_temp)
    out_temp = _make_temp('.avif')
    quality = '80' if lossy else '100'
    cmd = [
        convert_path or '', abspath(filepath), '-quality', quality, out_temp
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(out_temp)
        return None
    return _commit_output(out_temp, filepath, insize, verify='avif', **ck)


def pack_heic(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    convert_path = resolve_tool('convert')
    if convert_path is None:
        if debug:
            logging.warning('ImageMagick not installed for HEIC')
        return None
    insize = os.path.getsize(filepath)
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.heic'
    out_temp = _make_temp(ext)
    quality = '80' if lossy else '100'
    cmd = [convert_path, abspath(filepath), '-quality', quality, out_temp]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(out_temp)
        return None
    return _commit_output(
        out_temp, filepath, insize, verify='heic', **_commit_kwargs(**commit)
    )


def pack_flac(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    flac = resolve_tool('flac')
    if flac is None:
        if debug:
            logging.warning('flac not installed')
        return None
    insize = os.path.getsize(filepath)
    out_temp = _make_temp('.flac')
    cmd = [flac, '--best', '--verify', '-f', '-o', out_temp, abspath(filepath)]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(out_temp)
        return None
    return _commit_output(
        out_temp, filepath, insize, verify='flac', **_commit_kwargs(**commit)
    )


def pack_pdf(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Compress PDF. Default is lossless qpdf; Ghostscript is opt-in lossy."""
    insize = os.path.getsize(filepath)
    gs_path = resolve_tool('gs')
    qpdf_path = resolve_tool('qpdf')
    if gs_path is None and qpdf_path is None:
        if debug:
            logging.warning('Neither ghostscript nor qpdf is installed')
        return None

    abs_in = abspath(filepath)
    ck = _commit_kwargs(**commit)

    def _try_qpdf() -> Optional[PackResult]:
        if not qpdf_path:
            return None
        tempfpath = _make_temp('.pdf')
        cmd = [
            qpdf_path, '--linearize', '--object-streams=generate',
            '--compress-streams=y', abs_in, tempfpath,
        ]
        if debug:
            logging.info('qpdf cmd: %s', ' '.join(cmd))
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is None:
            _remove_quietly(tempfpath)
            return None
        return _commit_output(tempfpath, filepath, insize, verify='pdf', **ck)

    def _try_gs() -> Optional[PackResult]:
        if not gs_path:
            return None
        tempfpath = _make_temp('.pdf')
        cmd = [
            gs_path, '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/prepress', '-dNOPAUSE', '-dQUIET', '-dBATCH',
            '-dAutoRotatePages=/None', f'-sOutputFile={tempfpath}', abs_in,
        ]
        if debug:
            logging.info('ghostscript cmd: %s', ' '.join(cmd))
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is None:
            _remove_quietly(tempfpath)
            return None
        return _commit_output(tempfpath, filepath, insize, verify='pdf', **ck)

    if lossy:
        return _try_gs() or _try_qpdf()
    return _try_qpdf()


def pack_gif(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    gifsicle_path = resolve_tool('gifsicle')
    if gifsicle_path is None:
        if debug:
            logging.warning('gifsicle not installed')
        return None
    insize = os.path.getsize(filepath)
    tempfpath = _make_temp('.gif')
    cmd = [
        gifsicle_path, '-O3', '--lossy=0', abspath(filepath), '-o', tempfpath,
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(tempfpath)
        return None
    return _commit_output(
        tempfpath, filepath, insize, verify='gif', **_commit_kwargs(**commit)
    )


def pack_webp(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    dwebp_path = resolve_tool('dwebp')
    cwebp_path = resolve_tool('cwebp')
    if dwebp_path is None or cwebp_path is None:
        if debug:
            logging.warning('dwebp or cwebp not installed')
        return None
    insize = os.path.getsize(filepath)
    temp_png = _make_temp('.png')
    tempfpath = _make_temp('.webp')
    try:
        abs_in = abspath(filepath)
        decode = _run_command(
            [dwebp_path, abs_in, '-o', temp_png], quiet=quiet, debug=debug
        )
        if decode is None:
            return None
        encode = _run_command(
            [cwebp_path, '-lossless', '-z', '9', temp_png, '-o', tempfpath],
            quiet=quiet, debug=debug,
        )
        if encode is None:
            _remove_quietly(tempfpath)
            return None
        return _commit_output(
            tempfpath, filepath, insize, verify='webp', **_commit_kwargs(**commit)
        )
    finally:
        _remove_quietly(temp_png)
        _remove_quietly(tempfpath)


def pack_svg(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    svgo_path = resolve_tool('svgo')
    scour_path = resolve_tool('scour') if svgo_path is None else None
    if svgo_path is None and scour_path is None:
        if debug:
            logging.warning('svgo or scour not installed')
        return None
    insize = os.path.getsize(filepath)
    tempfpath = _make_temp('.svg')
    abs_in = abspath(filepath)
    if svgo_path:
        cmd = [svgo_path, '--input', abs_in, '--output', tempfpath]
    else:
        cmd = [
            scour_path or '', '--enable-viewboxing', '--enable-id-stripping',
            '--enable-comment-stripping', '--remove-metadata',
            '--strip-xml-prolog', '--no-line-breaks', abs_in, tempfpath,
        ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(tempfpath)
        return None
    return _commit_output(
        tempfpath, filepath, insize, verify='svg', **_commit_kwargs(**commit)
    )


def pack_tif(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    convert_path = resolve_tool('convert')
    tiffcp_path = resolve_tool('tiffcp')
    if convert_path is None and tiffcp_path is None:
        if debug:
            logging.warning('Neither ImageMagick nor tiffcp is installed')
        return None
    insize = os.path.getsize(filepath)
    abs_in = abspath(filepath)
    ck = _commit_kwargs(**commit)

    if convert_path:
        tempfpath = _make_temp('.tif')
        cmd = [
            convert_path, abs_in, '-compress', 'lzw', '-strip', '-quiet',
            tempfpath,
        ]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None:
            packed = _commit_output(
                tempfpath, filepath, insize, verify='tif', **ck
            )
            if packed:
                return packed
        _remove_quietly(tempfpath)

    if tiffcp_path:
        tempfpath = _make_temp('.tif')
        cmd = [tiffcp_path, '-c', 'lzw', abs_in, tempfpath]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is None:
            _remove_quietly(tempfpath)
            return None
        return _commit_output(tempfpath, filepath, insize, verify='tif', **ck)
    return None


def _encode_video(
    ffmpeg_path: str, src: str, dest: str, lossless: bool,
    quiet: bool, debug: bool, container: str = 'mp4',
) -> bool:
    if container == 'webm':
        if lossless:
            cmd = [
                ffmpeg_path, '-i', abspath(src), '-c:v', 'libvpx-vp9',
                '-lossless', '1', '-c:a', 'copy', '-y', dest,
            ]
        else:
            cmd = [
                ffmpeg_path, '-i', abspath(src), '-c:v', 'libvpx-vp9',
                '-crf', '18', '-b:v', '0', '-c:a', 'copy', '-y', dest,
            ]
    else:
        crf = '0' if lossless else '18'
        preset = 'veryslow' if lossless else 'slow'
        cmd = [
            ffmpeg_path, '-i', abspath(src), '-c:v', 'libx264', '-crf', crf,
            '-preset', preset, '-c:a', 'copy', '-y', dest,
        ]
        if container == 'mp4':
            cmd[-2:-2] = ['-movflags', '+faststart']
    result = _run_command(cmd, quiet=quiet, debug=debug)
    return result is not None and os.path.exists(dest) and os.path.getsize(dest) > 0


def _pack_video(
    filepath: str, mode: str, lossless: bool = False,
    convert_container: bool = True, debug: bool = False, quiet: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    ffmpeg_path = resolve_tool('ffmpeg')
    if ffmpeg_path is None:
        if debug:
            logging.warning('ffmpeg not installed')
        return None
    insize = os.path.getsize(filepath)
    keep_modes = {'mp4', 'mkv', 'webm'}
    dest = filepath
    if convert_container and mode not in keep_modes:
        dest = filepath.rsplit('.', 1)[0] + '.mp4'
        out_mode = 'mp4'
    else:
        out_mode = mode if mode in ('mp4', 'mkv', 'webm') else 'mp4'
    suffix = '.' + out_mode
    verify = 'mp4' if out_mode == 'mp4' else out_mode
    tempfpath = _make_temp(suffix)
    try:
        if not _encode_video(
            ffmpeg_path, filepath, tempfpath, lossless, quiet, debug,
            container=out_mode,
        ):
            return None
        result = _commit_output(
            tempfpath, dest, insize, verify=verify, **_commit_kwargs(**commit)
        )
        if result and result.replaced and dest != filepath:
            _remove_quietly(filepath)
            return PackResult(
                dest, result.insize, result.outsize, result.savings_pct, True
            )
        if result and dest != filepath:
            return PackResult(
                dest if result.replaced else filepath,
                result.insize, result.outsize, result.savings_pct,
                result.replaced,
            )
        return result
    finally:
        _remove_quietly(tempfpath)


def pack_wmv(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'wmv', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def pack_mp4(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'mp4', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def pack_avi(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'avi', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def pack_asf(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'asf', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def pack_mkv(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'mkv', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


def pack_webm(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'webm', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


def pack_jpg(
    filepath: str, debug: bool = False, quiet: bool = False,
    jpeg_quality: Optional[int] = None, lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    jpegoptim_path = resolve_tool('jpegoptim')
    if jpegoptim_path is None:
        if debug:
            logging.warning('jpegoptim not installed')
        return None
    insize = os.path.getsize(filepath)
    tempfpath = _make_temp('.jpg')
    copyfile(filepath, tempfpath)
    cmd = [jpegoptim_path, '--strip-all', '-p', '-o']
    if jpeg_quality is not None or lossy:
        quality = jpeg_quality if jpeg_quality is not None else DEFAULT_JPEG_QUALITY
        cmd.append(f'-m{quality}')
    cmd.append(tempfpath)
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(tempfpath)
        return None
    return _commit_output(
        tempfpath, filepath, insize, verify='jpg', **_commit_kwargs(**commit)
    )


def pack_png(
    filepath: str, debug: bool = False, quiet: bool = False,
    png_quality: Optional[str] = None, lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    insize = os.path.getsize(filepath)
    use_lossy = lossy or png_quality is not None
    ck = _commit_kwargs(**commit)

    if use_lossy:
        pngquant_path = resolve_tool('pngquant')
        if pngquant_path is None:
            if debug:
                logging.warning('pngquant not installed')
            return None
        tempfpath = _make_temp('.png')
        copyfile(filepath, tempfpath)
        speed = {'high': '1', 'medium': '2', 'low': '3'}.get(png_quality or '', '1')
        cmd = [pngquant_path, '--force', '--speed', speed, tempfpath]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is None:
            _remove_quietly(tempfpath)
            return None
        quant = tempfpath.rsplit('.', 1)[0] + '-fs8.png'
        if os.path.exists(quant):
            _remove_quietly(tempfpath)
            tempfpath = quant
        return _commit_output(tempfpath, filepath, insize, verify='png', **ck)

    oxipng_path = resolve_tool('oxipng')
    optipng_path = resolve_tool('optipng')
    if oxipng_path is None and optipng_path is None:
        if debug:
            logging.warning('oxipng/optipng not installed for lossless PNG')
        return None
    tempfpath = _make_temp('.png')
    copyfile(filepath, tempfpath)
    if oxipng_path:
        cmd = [oxipng_path, '-o', '4', '--strip', 'safe', '-q', tempfpath]
    else:
        cmd = [optipng_path or '', '-o7', '-quiet', tempfpath]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(tempfpath)
        return None
    return _commit_output(tempfpath, filepath, insize, verify='png', **ck)


@dataclass
class PackerSpec:
    func: Callable[..., Optional[PackResult]]
    category: str
    extra: Dict[str, str] = field(default_factory=dict)


_PACKERS: Dict[str, PackerSpec] = {
    'jpg': PackerSpec(pack_jpg, 'image', {'jpeg_quality': 'jpeg_quality'}),
    'jpeg': PackerSpec(pack_jpg, 'image', {'jpeg_quality': 'jpeg_quality'}),
    'png': PackerSpec(pack_png, 'image', {'png_quality': 'png_quality'}),
    'gif': PackerSpec(pack_gif, 'image'),
    'webp': PackerSpec(pack_webp, 'image'),
    'svg': PackerSpec(pack_svg, 'image'),
    'tif': PackerSpec(pack_tif, 'image'),
    'tiff': PackerSpec(pack_tif, 'image'),
    'parquet': PackerSpec(pack_parquet, 'data', {'ultra': 'ultra'}),
    'gz': PackerSpec(pack_gzip, 'data'),
    'xz': PackerSpec(pack_xz, 'data'),
    'bz2': PackerSpec(pack_bz2, 'data'),
    'zst': PackerSpec(pack_zstd, 'data'),
    'br': PackerSpec(pack_brotli, 'data'),
    'pdf': PackerSpec(pack_pdf, 'document'),
    'avif': PackerSpec(pack_avif, 'image'),
    'heic': PackerSpec(pack_heic, 'image'),
    'heif': PackerSpec(pack_heic, 'image'),
    'flac': PackerSpec(pack_flac, 'audio'),
    'wmv': PackerSpec(pack_wmv, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'mp4': PackerSpec(pack_mp4, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'avi': PackerSpec(pack_avi, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'asf': PackerSpec(pack_asf, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'mkv': PackerSpec(pack_mkv, 'video', {'wmv_lossless': 'lossless'}),
    'webm': PackerSpec(pack_webm, 'video', {'wmv_lossless': 'lossless'}),
}


def _dispatch_packer(
    ext: str, fullname: str, options: Dict[str, Any]
) -> Optional[PackResult]:
    spec = _PACKERS.get(ext)
    if spec is None:
        return None
    if spec.category in ('image', 'video') and not options.get('pack_images', True):
        return None
    kwargs: Dict[str, Any] = {
        'debug': options.get('debug', False),
        'quiet': options.get('quiet', False),
        'dryrun': options.get('dryrun', False),
        'keep_if_larger': options.get('keep_if_larger', True),
        'min_savings': options.get('min_savings'),
        'lossy': options.get('lossy', False),
    }
    for opt_key, arg_name in spec.extra.items():
        kwargs[arg_name] = options.get(opt_key)
    return spec.func(fullname, **kwargs)


def _normalize_options(def_options: Any) -> Dict[str, Any]:
    options = {
        'debug': False, 'pack_images': True, 'repack_archive': True,
        'pack_archives': True, 'deep_walking': True, 'log': False,
        'quiet': False, 'ultra': False, 'dryrun': False,
        'keep_if_larger': True, 'lossy': False, 'convert_container': True,
        'min_savings': None, 'compression_level': 9,
    }
    if isinstance(def_options, RepackOptions):
        options.update(def_options.to_dict())
    elif def_options:
        options.update(def_options)
    return options


def _empty_summary(filepath: str, size: int) -> RepackSummary:
    return RepackSummary(
        filepath=filepath, total_insize=size, total_outsize=size,
    )


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
    result = _run_command(
        [szip, 'l', '-slt', filename],
        quiet=options.get('quiet', False),
        debug=options.get('debug', False),
    )
    if result is None or not result.stdout:
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
    return True


class FileRepacker:
    """Document and file repacker."""

    def __init__(self, quiet: bool = False, temppath: Optional[str] = None):
        self.quiet = quiet
        self.temppath = temppath if temppath else TEMP_PATH

    def pack_images(
        self, mediapath: str, recursive: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[RepackSummary]:
        if options is None:
            options = {'debug': False}
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
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            res = _dispatch_packer(ext, fn, options)
            if res is not None:
                summary.results.append(res)
                summary.inner_count += 1
                summary.inner_insize += res.insize
                summary.inner_outsize += res.outsize
        summary.total_insize = summary.inner_insize
        summary.total_outsize = summary.inner_outsize
        return summary

    def repack_zip_file(
        self, filename: str, outfile: Optional[str] = None,
        def_options: Any = None,
    ) -> RepackSummary:
        """Repack a standalone file or archive. Never unlinks the original first."""
        options = _normalize_options(def_options)
        f_insize = os.path.getsize(filename)
        filetype = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        dest = os.path.abspath(outfile or filename)

        standalone = _dispatch_packer(filetype, filename, options)
        if standalone is not None or filetype in _PACKERS:
            summary = RepackSummary(filepath=filename, total_insize=f_insize)
            if standalone is None:
                summary.total_outsize = f_insize
                return summary
            summary.total_outsize = standalone.outsize
            summary.results.append(standalone)
            return summary

        if filetype not in ARCHIVE_EXTS and filetype not in SUPPORTED_EXTS:
            return _empty_summary(filename, f_insize)

        return self._repack_container(filename, dest, f_insize, filetype, options)

    def repack(
        self, filename: str, outfile: Optional[str] = None,
        options: Any = None,
    ) -> RepackSummary:
        """Library-facing alias for repack_zip_file."""
        return self.repack_zip_file(filename, outfile=outfile, def_options=options)

    def _repack_container(
        self, filename: str, dest: str, f_insize: int,
        filetype: str, options: Dict[str, Any],
    ) -> RepackSummary:
        summary = RepackSummary(filepath=filename, total_insize=f_insize)
        fpath = os.path.join(self.temppath, uuid.uuid4().hex)
        try:
            if filetype == 'rar':
                extracted = self._extract_rar(filename, fpath, options)
            else:
                extracted = self._extract_7z(filename, fpath, options)
            if not extracted:
                summary.total_outsize = f_insize
                return summary

            if options.get('deep_walking', True):
                self._deep_walk(fpath, options, summary)

            if filetype == 'rar':
                self._repack_rar(
                    fpath, dest, filename, options, summary, f_insize
                )
            elif filetype == '7z':
                self._write_archive(
                    fpath, dest, options, summary, f_insize, '7z', filetype
                )
            else:
                self._write_archive(
                    fpath, dest, options, summary, f_insize, 'zip', filetype
                )
            return summary
        finally:
            _remove_quietly(fpath)

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
        cmd = [szip, 'x', '-y', f'-o{fpath}', filename]
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

    def _deep_walk(
        self, fpath: str, options: Dict[str, Any], summary: RepackSummary
    ) -> None:
        for root, dirs, files in os.walk(fpath):
            for name in files:
                ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
                fullname = os.path.join(root, name)
                if ext in ARCHIVE_EXTS:
                    if not options.get('pack_archives', True):
                        continue
                    nested = self.repack_zip_file(fullname, fullname, options)
                    if nested.total_insize:
                        summary.results.append(PackResult(
                            fullname, nested.total_insize, nested.total_outsize,
                            nested.total_savings_pct,
                        ))
                        summary.inner_count += 1
                        summary.inner_insize += nested.total_insize
                        summary.inner_outsize += nested.total_outsize
                else:
                    res = _dispatch_packer(ext, fullname, options)
                    if res is not None:
                        summary.results.append(res)
                        summary.inner_count += 1
                        summary.inner_insize += res.insize
                        summary.inner_outsize += res.outsize

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
        suffix = '.zip' if archive_type == 'zip' else '.7z'
        temp_out = _make_temp(suffix)
        _remove_quietly(temp_out)
        level = options.get('compression_level', 9)
        cmd = [szip, f'-t{archive_type}', '-y', f'-mx{level}', 'a', temp_out, '*']
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
            _remove_quietly(temp_out)
            summary.total_outsize = f_insize
            return
        verify = 'zip' if archive_type == 'zip' else '7z'
        packed = _commit_output(
            temp_out, dest, f_insize, verify=verify,
            dryrun=options.get('dryrun', False),
            keep_if_larger=options.get('keep_if_larger', True),
            min_savings=options.get('min_savings'),
        )
        if packed is None:
            summary.total_outsize = f_insize
            return
        summary.total_outsize = packed.outsize

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
        cmd = [zip_tool, '-r', f'-{level}', '-X', temp_out, '*']
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
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
            self._write_archive(
                fpath, dest_7z, options, summary, f_insize, '7z', 'rar'
            )
            if (
                summary.total_outsize
                and summary.total_outsize != f_insize
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
        cmd = [rar_path, 'a', '-r', rar_level, '-y', temp_out, '*']
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
            _remove_quietly(temp_out)
            summary.total_outsize = f_insize
            return
        packed = _commit_output(
            temp_out, dest, f_insize,
            dryrun=options.get('dryrun', False),
            keep_if_larger=options.get('keep_if_larger', True),
            min_savings=options.get('min_savings'),
        )
        if packed is None:
            summary.total_outsize = f_insize
            return
        summary.total_outsize = packed.outsize


def pack_file_simple(filepath: str, pack_fn, **kwargs) -> Optional[PackResult]:
    result = pack_fn(filepath, **kwargs)
    if result is None:
        return None
    if isinstance(result, PackResult):
        return result
    return PackResult(
        filepath=result[0], insize=result[1], outsize=result[2],
        savings_pct=result[3],
    )
