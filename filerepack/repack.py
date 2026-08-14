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

from . import codecs as extra_codecs
from .consts import (
    DEFAULT_JPEG_QUALITY, DEFAULT_LOSSY_PDF_PROFILE,
    DEFAULT_MAX_EXTRACT_BYTES, DEFAULT_MAX_EXTRACT_RATIO,
    PDF_PROFILES, ZIP_SENSITIVE_EXTS,
)
from .formats import identify_filename
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


def _pack_pipe_codec(
    filepath: str,
    decode_cmd: List[str],
    encode_prefix: List[str],
    suffix: str,
    verify: Optional[str],
    debug: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    """Decode with argv stdout, encode with prefix+[payload], then replace."""
    insize = os.path.getsize(filepath)
    dec_temp = _make_temp('.bin')
    out_temp = _make_temp(suffix)
    try:
        if not _run_to_file(decode_cmd, dec_temp, debug):
            return None
        if not _run_to_file(encode_prefix + [dec_temp], out_temp, debug):
            return None
        return _commit_output(
            out_temp, filepath, insize, verify=verify, **_commit_kwargs(**commit)
        )
    finally:
        _remove_quietly(dec_temp)
        _remove_quietly(out_temp)


def _compress_file(src: str, dest: str, codec: str, debug: bool = False) -> bool:
    """Compress a single payload file with the named stream codec."""
    if codec == 'gz':
        tool = resolve_tool('pigz')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        with open(src, 'rb') as f_in, gzip.open(dest, 'wb', compresslevel=9) as f_out:
            copyfileobj(f_in, f_out, length=_COPY_BUF)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    if codec == 'bz2':
        tool = resolve_tool('bzip2')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        with open(src, 'rb') as f_in, bz2.open(dest, 'wb', compresslevel=9) as f_out:
            copyfileobj(f_in, f_out, length=_COPY_BUF)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    if codec == 'xz':
        tool = resolve_tool('xz')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        with open(src, 'rb') as f_in, lzma.open(dest, 'wb', preset=9) as f_out:
            copyfileobj(f_in, f_out, length=_COPY_BUF)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    if codec == 'lzma':
        tool = resolve_tool('lzma')
        if tool:
            return _run_to_file([tool, '-9', '-c', src], dest, debug)
        with open(src, 'rb') as f_in:
            with lzma.open(dest, 'wb', format=lzma.FORMAT_ALONE, preset=9) as f_out:
                copyfileobj(f_in, f_out, length=_COPY_BUF)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    tool_map = {
        'zst': ('zstd', ['-19', '-c']),
        'br': ('brotli', ['-q', '11', '-c']),
        'lz4': ('lz4', ['-9', '-c']),
        'lz': ('lzip', ['-9', '-c']),
        'lzo': ('lzop', ['-9', '-c']),
        'z': ('compress', ['-c']),
    }
    spec = tool_map.get(codec)
    if spec is None:
        return False
    key, flags = spec
    tool = resolve_tool(key)
    if tool is None:
        return False
    return _run_to_file([tool] + flags + [src], dest, debug)


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
    return _pack_pipe_codec(
        filepath, [zstd, '-d', '-c', filepath], [zstd, '-19', '-c'],
        '.zst', 'zst', debug=debug, **commit,
    )


def pack_brotli(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    brotli = resolve_tool('brotli')
    if brotli is None:
        if debug:
            logging.warning('brotli not installed')
        return None
    return _pack_pipe_codec(
        filepath, [brotli, '-d', '-c', filepath], [brotli, '-q', '11', '-c'],
        '.br', None, debug=debug, **commit,
    )


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
    from .covers import optimize_embedded_covers

    flac = resolve_tool('flac')
    insize = os.path.getsize(filepath)
    work = _make_temp('.flac')
    copyfile(filepath, work)
    optimize_embedded_covers(work, {
        'debug': debug, 'quiet': quiet,
        'pack_images': bool(commit.get('pack_images', True)),
        'keep_meta': bool(commit.get('keep_meta', False)),
        'lossy': bool(commit.get('lossy', False)),
        'ultra': bool(commit.get('ultra', False)),
    })
    if flac is not None:
        out_temp = _make_temp('.flac')
        cmd = [flac, '--best', '--verify', '-f', '-o', out_temp, abspath(work)]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None:
            _remove_quietly(work)
            work = out_temp
        else:
            _remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        _remove_quietly(work)
        if debug:
            logging.warning('flac not installed')
        return None
    return _commit_output(
        work, filepath, insize, verify='flac', **_commit_kwargs(**commit)
    )


def normalize_pdf_profile(value: Optional[str]) -> Optional[str]:
    """Return a canonical Ghostscript profile name, or None if unset."""
    if value is None:
        return None
    key = str(value).strip().lower().lstrip('/')
    if key not in PDF_PROFILES:
        raise ValueError(
            f"Unknown PDF profile {value!r}; expected one of "
            + ', '.join(PDF_PROFILES)
        )
    return key


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
    from .pdf_streams import rebuild_pdf_images
    walked = _make_temp('.pdf')
    options = {
        'debug': debug, 'quiet': quiet, 'pack_images': True,
        'keep_meta': bool(commit.get('keep_meta', False)),
        'ultra': bool(commit.get('ultra', False)),
    }
    if rebuild_pdf_images(abs_in, walked, options):
        return walked, walked
    _remove_quietly(walked)
    return abs_in, None


def _qpdf_linearize(
    qpdf_path: Optional[str], walk_src: str, walked: Optional[str],
    filepath: str, insize: int, debug: bool, quiet: bool, ck: Dict[str, Any],
) -> Optional[PackResult]:
    if not qpdf_path:
        if walked:
            return _commit_output(walked, filepath, insize, verify='pdf', **ck)
        return None
    tempfpath = _make_temp('.pdf')
    cmd = [
        qpdf_path, '--linearize', '--object-streams=generate',
        '--compress-streams=y', walk_src, tempfpath,
    ]
    if debug:
        logging.info('qpdf cmd: %s', ' '.join(cmd))
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(tempfpath)
        if walked:
            return _commit_output(walked, filepath, insize, verify='pdf', **ck)
        return None
    _remove_quietly(walked)
    return _commit_output(tempfpath, filepath, insize, verify='pdf', **ck)


def _gs_pdf(
    gs_path: Optional[str], abs_in: str, filepath: str, insize: int,
    gs_profile: str, jpeg_quality: Optional[int],
    debug: bool, quiet: bool, ck: Dict[str, Any],
) -> Optional[PackResult]:
    if not gs_path:
        return None
    tempfpath = _make_temp('.pdf')
    cmd = build_gs_pdf_cmd(
        gs_path, abs_in, tempfpath, profile=gs_profile,
        jpeg_quality=jpeg_quality,
    )
    if debug:
        logging.info('ghostscript cmd: %s', ' '.join(cmd))
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        _remove_quietly(tempfpath)
        return None
    return _commit_output(tempfpath, filepath, insize, verify='pdf', **ck)


def pack_pdf(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, pdf_profile: Optional[str] = None,
    jpeg_quality: Optional[int] = None, **commit: Any,
) -> Optional[PackResult]:
    """Compress PDF. Default is lossless qpdf; Ghostscript is opt-in lossy."""
    insize = os.path.getsize(filepath)
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
    ck = _commit_kwargs(**commit)
    use_gs = bool(lossy or profile is not None or jpeg_quality is not None)
    gs_profile = profile or DEFAULT_LOSSY_PDF_PROFILE
    walk_src, walked = abs_in, None
    if not use_gs:
        walk_src, walked = _maybe_walk_pdf_images(abs_in, debug, quiet, commit)

    if use_gs:
        gs_result = _gs_pdf(
            gs_path, abs_in, filepath, insize, gs_profile, jpeg_quality,
            debug, quiet, ck,
        )
        if gs_result:
            return gs_result
    return _qpdf_linearize(
        qpdf_path, walk_src, walked, filepath, insize, debug, quiet, ck,
    )


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
    from .markup import pack_xml, rewrite_data_uris

    svgo_path = resolve_tool('svgo')
    scour_path = resolve_tool('scour') if svgo_path is None else None
    if svgo_path is None and scour_path is None:
        return pack_xml(filepath, debug=debug, quiet=quiet, **commit)
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
        return pack_xml(filepath, debug=debug, quiet=quiet, **commit)
    try:
        with open(tempfpath, 'r', encoding='utf-8') as fh:
            text = fh.read()
        options = {
            'debug': debug, 'quiet': quiet, 'pack_images': True,
            'lossy': bool(commit.get('lossy', False)),
            'keep_meta': bool(commit.get('keep_meta', False)),
        }
        rewritten = rewrite_data_uris(text, options)
        if rewritten != text:
            with open(tempfpath, 'w', encoding='utf-8') as fh:
                fh.write(rewritten)
    except (OSError, UnicodeError):
        pass
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
        if container in ('mp4', 'mov', 'm4v'):
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
    keep_modes = {'mp4', 'mkv', 'webm', 'mov', 'm4v'}
    known = keep_modes | {'3gp', 'ts', 'mts', 'm2ts'}
    dest = filepath
    if convert_container and mode not in keep_modes:
        dest = filepath.rsplit('.', 1)[0] + '.mp4'
        out_mode = 'mp4'
    else:
        out_mode = mode if mode in known else 'mp4'
    suffix = '.' + dest.rsplit('.', 1)[-1].lower() if '.' in dest else '.' + out_mode
    if out_mode in ('mp4', 'mov', 'm4v', '3gp'):
        verify = 'mp4'
    elif out_mode in ('ts', 'mts', 'm2ts'):
        verify = 'ts'
    else:
        verify = out_mode
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
    jpeg_quality: Optional[int] = None, lossy: bool = False,
    keep_meta: bool = False, **commit: Any,
) -> Optional[PackResult]:
    jpegoptim_path = resolve_tool('jpegoptim')
    jpegtran_path = resolve_tool('jpegtran')
    if jpegoptim_path is None and jpegtran_path is None:
        if debug:
            logging.warning('jpegoptim/jpegtran not installed')
        return None
    insize = os.path.getsize(filepath)
    work = _make_temp('.jpg')
    copyfile(filepath, work)
    ck = _commit_kwargs(**commit)
    use_lossy = jpeg_quality is not None or lossy
    try:
        if jpegtran_path and not use_lossy:
            _jpegtran_inplace(
                jpegtran_path, work, keep_meta=keep_meta,
                debug=debug, quiet=quiet,
            )
        if jpegoptim_path:
            cmd = [jpegoptim_path, '-p', '-o']
            if not keep_meta:
                cmd.append('--strip-all')
            if use_lossy:
                quality = (
                    jpeg_quality if jpeg_quality is not None
                    else DEFAULT_JPEG_QUALITY
                )
                cmd.append(f'-m{quality}')
            cmd.append(work)
            result = _run_command(cmd, quiet=quiet, debug=debug)
            if result is None and jpegtran_path is None:
                return None
        return _commit_output(work, filepath, insize, verify='jpg', **ck)
    finally:
        _remove_quietly(work)


def _jpegtran_inplace(
    jpegtran_path: str, work: str, keep_meta: bool,
    debug: bool, quiet: bool,
) -> None:
    out = _make_temp('.jpg')
    copy_mode = 'all' if keep_meta else 'none'
    cmd = [
        jpegtran_path, '-optimize', '-progressive',
        '-copy', copy_mode, '-outfile', out, work,
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None or not verify_output(out, 'jpg'):
        _remove_quietly(out)
        return
    if os.path.getsize(out) < os.path.getsize(work):
        os.replace(out, work)
    else:
        _remove_quietly(out)


def _pngquant_lossy(
    filepath: str, png_quality: Optional[str], debug: bool, quiet: bool,
) -> Optional[str]:
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
        return quant
    return tempfpath


def _png_lossless_candidates(
    filepath: str, ultra: bool, keep_meta: bool, debug: bool, quiet: bool,
) -> List[str]:
    oxipng_path = resolve_tool('oxipng')
    optipng_path = resolve_tool('optipng')
    zopflipng_path = resolve_tool('zopflipng') if ultra else None
    if oxipng_path is None and optipng_path is None and zopflipng_path is None:
        if debug:
            logging.warning('oxipng/optipng not installed for lossless PNG')
        return []

    candidates: List[str] = []
    if oxipng_path or optipng_path:
        tempfpath = _make_temp('.png')
        copyfile(filepath, tempfpath)
        if oxipng_path:
            cmd = [oxipng_path, '-o', '4', '-q', tempfpath]
            if not keep_meta:
                cmd[3:3] = ['--strip', 'safe']
        else:
            cmd = [optipng_path or '', '-o7', '-quiet', tempfpath]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None and verify_output(tempfpath, 'png'):
            candidates.append(tempfpath)
        else:
            _remove_quietly(tempfpath)

    if zopflipng_path:
        z_out = _make_temp('.png')
        cmd = [zopflipng_path, '-y']
        if keep_meta:
            cmd.append('--keepchunks=iCCP,sRGB,gAMA,pHYs,eXIf,tEXt,zTXt,iTXt')
        cmd.extend([abspath(filepath), z_out])
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None and verify_output(z_out, 'png'):
            candidates.append(z_out)
        else:
            _remove_quietly(z_out)
    return candidates


def pack_png(
    filepath: str, debug: bool = False, quiet: bool = False,
    png_quality: Optional[str] = None, lossy: bool = False,
    ultra: bool = False, keep_meta: bool = False, **commit: Any,
) -> Optional[PackResult]:
    insize = os.path.getsize(filepath)
    ck = _commit_kwargs(**commit)
    if lossy or png_quality is not None:
        tempfpath = _pngquant_lossy(filepath, png_quality, debug, quiet)
        if tempfpath is None:
            return None
        return _commit_output(tempfpath, filepath, insize, verify='png', **ck)

    candidates = _png_lossless_candidates(
        filepath, ultra, keep_meta, debug, quiet,
    )
    if not candidates:
        return None
    best = min(candidates, key=os.path.getsize)
    for path in candidates:
        if path != best:
            _remove_quietly(path)
    return _commit_output(best, filepath, insize, verify='png', **ck)


@dataclass
class PackerSpec:
    func: Callable[..., Optional[PackResult]]
    category: str
    extra: Dict[str, str] = field(default_factory=dict)


_PACKERS: Dict[str, PackerSpec] = {
    'jpg': PackerSpec(pack_jpg, 'image', {
        'jpeg_quality': 'jpeg_quality', 'keep_meta': 'keep_meta',
    }),
    'png': PackerSpec(pack_png, 'image', {
        'png_quality': 'png_quality', 'ultra': 'ultra', 'keep_meta': 'keep_meta',
    }),
    'gif': PackerSpec(pack_gif, 'image'),
    'webp': PackerSpec(pack_webp, 'image'),
    'svg': PackerSpec(pack_svg, 'image', {'keep_meta': 'keep_meta'}),
    'svgz': PackerSpec(extra_codecs.pack_svgz, 'image'),
    'tif': PackerSpec(pack_tif, 'image'),
    'tiff': PackerSpec(pack_tif, 'image'),
    'jxl': PackerSpec(extra_codecs.pack_jxl, 'image'),
    'jp2': PackerSpec(extra_codecs.pack_jp2, 'image'),
    'j2k': PackerSpec(extra_codecs.pack_jp2, 'image'),
    'jpf': PackerSpec(extra_codecs.pack_jp2, 'image'),
    'jpx': PackerSpec(extra_codecs.pack_jp2, 'image'),
    'exr': PackerSpec(extra_codecs.pack_exr, 'image'),
    'dng': PackerSpec(extra_codecs.pack_dng, 'image'),
    'dcm': PackerSpec(extra_codecs.pack_dcm, 'image'),
    'dicom': PackerSpec(extra_codecs.pack_dcm, 'image'),
    'dic': PackerSpec(extra_codecs.pack_dcm, 'image'),
    'ico': PackerSpec(extra_codecs.pack_ico, 'image'),
    'icns': PackerSpec(extra_codecs.pack_icns, 'image'),
    'bmp': PackerSpec(extra_codecs.pack_bmp, 'image'),
    'tga': PackerSpec(extra_codecs.pack_tga, 'image'),
    'pnm': PackerSpec(extra_codecs.pack_pnm, 'image'),
    'pcx': PackerSpec(extra_codecs.pack_pcx, 'image'),
    'xml': PackerSpec(extra_codecs.pack_xml, 'document', {
        'keep_meta': 'keep_meta', 'ultra': 'ultra',
        'jpeg_quality': 'jpeg_quality', 'png_quality': 'png_quality',
    }),
    'json': PackerSpec(extra_codecs.pack_json, 'document'),
    'parquet': PackerSpec(pack_parquet, 'data', {'ultra': 'ultra'}),
    'orc': PackerSpec(extra_codecs.pack_orc, 'data'),
    'avro': PackerSpec(extra_codecs.pack_avro, 'data'),
    'feather': PackerSpec(extra_codecs.pack_feather, 'data'),
    'arrow': PackerSpec(extra_codecs.pack_arrow, 'data'),
    'ipc': PackerSpec(extra_codecs.pack_arrow, 'data'),
    'sqlite': PackerSpec(extra_codecs.pack_sqlite, 'data'),
    'sqlite3': PackerSpec(extra_codecs.pack_sqlite, 'data'),
    'gpkg': PackerSpec(extra_codecs.pack_sqlite, 'data'),
    'mbtiles': PackerSpec(extra_codecs.pack_sqlite, 'data'),
    'h5': PackerSpec(extra_codecs.pack_hdf5, 'data'),
    'hdf5': PackerSpec(extra_codecs.pack_hdf5, 'data'),
    'hdf': PackerSpec(extra_codecs.pack_hdf5, 'data'),
    'nc': PackerSpec(extra_codecs.pack_netcdf, 'data'),
    'nc4': PackerSpec(extra_codecs.pack_netcdf, 'data'),
    'gz': PackerSpec(pack_gzip, 'data'),
    'xz': PackerSpec(pack_xz, 'data'),
    'bz2': PackerSpec(pack_bz2, 'data'),
    'zst': PackerSpec(pack_zstd, 'data'),
    'br': PackerSpec(pack_brotli, 'data'),
    'lz4': PackerSpec(extra_codecs.pack_lz4, 'data'),
    'lz': PackerSpec(extra_codecs.pack_lzip, 'data'),
    'lzma': PackerSpec(extra_codecs.pack_lzma, 'data'),
    'lzo': PackerSpec(extra_codecs.pack_lzo, 'data'),
    'z': PackerSpec(extra_codecs.pack_compress, 'data'),
    'pdf': PackerSpec(pack_pdf, 'document', {
        'pdf_profile': 'pdf_profile',
        'jpeg_quality': 'jpeg_quality',
        'keep_meta': 'keep_meta',
        'ultra': 'ultra',
    }),
    'avif': PackerSpec(pack_avif, 'image'),
    'heic': PackerSpec(pack_heic, 'image'),
    'heif': PackerSpec(pack_heic, 'image'),
    'flac': PackerSpec(pack_flac, 'audio', {'keep_meta': 'keep_meta'}),
    'm4a': PackerSpec(extra_codecs.pack_m4a, 'audio', {'keep_meta': 'keep_meta'}),
    'wv': PackerSpec(extra_codecs.pack_wv, 'audio'),
    'ape': PackerSpec(extra_codecs.pack_ape, 'audio', {'keep_meta': 'keep_meta'}),
    'tta': PackerSpec(extra_codecs.pack_tta, 'audio'),
    'oga': PackerSpec(extra_codecs.pack_oga, 'audio', {'keep_meta': 'keep_meta'}),
    'ogg': PackerSpec(extra_codecs.pack_ogg, 'audio', {'keep_meta': 'keep_meta'}),
    'mp3': PackerSpec(extra_codecs.pack_mp3, 'audio', {
        'ultra': 'ultra', 'keep_meta': 'keep_meta',
    }),
    'psd': PackerSpec(extra_codecs.pack_psd, 'image'),
    'ai': PackerSpec(extra_codecs.pack_ai, 'document', {
        'pdf_profile': 'pdf_profile',
        'jpeg_quality': 'jpeg_quality',
    }),
    'woff': PackerSpec(extra_codecs.pack_woff, 'data'),
    'woff2': PackerSpec(extra_codecs.pack_woff2, 'data'),
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
    'mov': PackerSpec(extra_codecs.pack_mov, 'video', {'wmv_lossless': 'lossless'}),
    'm4v': PackerSpec(extra_codecs.pack_m4v, 'video', {'wmv_lossless': 'lossless'}),
    '3gp': PackerSpec(extra_codecs.pack_3gp, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'ts': PackerSpec(extra_codecs.pack_ts, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'mts': PackerSpec(extra_codecs.pack_ts, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
    'm2ts': PackerSpec(extra_codecs.pack_ts, 'video', {
        'wmv_lossless': 'lossless',
        'convert_container': 'convert_container',
    }),
}


def _dispatch_packer(
    ext: str, fullname: str, options: Dict[str, Any]
) -> Optional[PackResult]:
    spec = _PACKERS.get(ext)
    if spec is None:
        return None
    if spec.category in ('image', 'video', 'audio') and not options.get(
        'pack_images', True
    ):
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
        'pdf_profile': None, 'jpeg_quality': None,
        'keep_meta': False,
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


def _notify(
    hook: Optional[Callable[..., None]],
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
            kind = identify_filename(name, peek_path=fn)
            if kind is None or kind.is_archive:
                continue
            res = _dispatch_packer(kind.packer or kind.key, fn, options)
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
        def_options: Any = None, *,
        on_progress: Optional[Callable[..., None]] = None,
    ) -> RepackSummary:
        """Repack a standalone file or archive. Never unlinks the original first."""
        options = _normalize_options(def_options)
        f_insize = os.path.getsize(filename)
        dest = os.path.abspath(outfile or filename)
        kind = identify_filename(filename, peek_path=filename)
        if kind is None:
            _notify(on_progress, 'standalone', name=filename)
            return _empty_summary(filename, f_insize)

        if kind.is_archive:
            return self._repack_container(
                filename, dest, f_insize, kind.key, options,
                family=kind.family, on_progress=on_progress,
            )

        packer_key = kind.packer or kind.key
        _notify(on_progress, 'standalone', name=filename)
        standalone = _dispatch_packer(packer_key, filename, options)
        if standalone is not None or packer_key in _PACKERS:
            summary = RepackSummary(filepath=filename, total_insize=f_insize)
            if standalone is None:
                summary.total_outsize = f_insize
                return summary
            summary.total_outsize = standalone.outsize
            summary.results.append(standalone)
            return summary

        return _empty_summary(filename, f_insize)

    def repack(
        self, filename: str, outfile: Optional[str] = None,
        options: Any = None, *,
        on_progress: Optional[Callable[..., None]] = None,
    ) -> RepackSummary:
        """Library-facing alias for repack_zip_file."""
        return self.repack_zip_file(
            filename, outfile=outfile, def_options=options,
            on_progress=on_progress,
        )

    def _repack_container(
        self, filename: str, dest: str, f_insize: int,
        filetype: str, options: Dict[str, Any], family: Optional[str] = None,
        on_progress: Optional[Callable[..., None]] = None,
    ) -> RepackSummary:
        if family is None:
            kind = identify_filename(filename, peek_path=filename)
            family = kind.family if kind else 'zip'
        summary = RepackSummary(filepath=filename, total_insize=f_insize)
        fpath = os.path.join(self.temppath, uuid.uuid4().hex)
        try:
            _notify(on_progress, 'extract', name=filename)
            if family == 'rar':
                extracted = self._extract_rar(filename, fpath, options)
            else:
                extracted = self._extract_7z(filename, fpath, options)
            if not extracted:
                summary.total_outsize = f_insize
                return summary

            if options.get('deep_walking', True):
                # Inner files live in a throwaway extract dir. Replace them even
                # on dryrun so the rewritten archive size matches a real run.
                # The outer _commit_output still honors dryrun.
                walk_options = options
                if options.get('dryrun'):
                    walk_options = {**options, 'dryrun': False}
                self._deep_walk(
                    fpath, walk_options, summary, on_progress=on_progress,
                )

            _notify(on_progress, 'write', name=filename)
            self._write_by_family(
                family, fpath, dest, filename, options, summary, f_insize, filetype
            )
            return summary
        finally:
            _remove_quietly(fpath)

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
        self, fpath: str, options: Dict[str, Any], summary: RepackSummary,
        on_progress: Optional[Callable[..., None]] = None,
    ) -> None:
        items = []
        for root, dirs, files in os.walk(fpath):
            for name in files:
                fullname = os.path.join(root, name)
                kind = identify_filename(name, peek_path=fullname)
                if kind is None:
                    continue
                if kind.is_archive and not options.get('pack_archives', True):
                    continue
                items.append((fullname, name, kind))
        _notify(on_progress, 'files', current=0, total=len(items))
        for i, (fullname, name, kind) in enumerate(items, 1):
            self._process_walk_item(fullname, kind, options, summary)
            _notify(on_progress, 'file', current=i, total=len(items), name=name)

    def _process_walk_item(
        self, fullname: str, kind: Any, options: Dict[str, Any],
        summary: RepackSummary,
    ) -> None:
        if kind.is_archive:
            nested = self.repack_zip_file(fullname, fullname, options)
            if nested.total_insize:
                summary.results.append(PackResult(
                    fullname, nested.total_insize, nested.total_outsize,
                    nested.total_savings_pct,
                ))
                summary.inner_count += 1
                summary.inner_insize += nested.total_insize
                summary.inner_outsize += nested.total_outsize
            return
        res = _dispatch_packer(kind.packer or kind.key, fullname, options)
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
            cmd = [szip, '-ttar', '-y', '-mx0', 'a', temp_out, '*']
        else:
            cmd = [
                szip, f'-t{archive_type}', '-y', f'-mx{level}', 'a', temp_out, '*',
            ]
        result = _run_command(
            cmd, quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
            _remove_quietly(temp_out)
            summary.total_outsize = f_insize
            return
        verify = verify_map.get(archive_type, 'zip')
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

    def _write_tar_bundle(
        self, fpath: str, dest: str, options: Dict[str, Any],
        summary: RepackSummary, f_insize: int, outer: str,
    ) -> None:
        """Write an uncompressed tar, then wrap it in gz/xz/bz2/zst/..."""
        szip = resolve_szip()
        if szip is None:
            summary.total_outsize = f_insize
            return
        tar_temp = _make_temp('.tar')
        _remove_quietly(tar_temp)
        result = _run_command(
            [szip, '-ttar', '-y', '-mx0', 'a', tar_temp, '*'],
            quiet=options.get('quiet', False),
            debug=options.get('debug', False), cwd=fpath,
        )
        if result is None:
            _remove_quietly(tar_temp)
            summary.total_outsize = f_insize
            return
        suffix = {
            'gz': '.gz', 'bz2': '.bz2', 'xz': '.xz', 'zst': '.zst',
            'br': '.br', 'lz4': '.lz4', 'lz': '.lz', 'lzo': '.lzo',
            'lzma': '.lzma', 'z': '.Z',
        }.get(outer, '.gz')
        verify = {
            'gz': 'gz', 'bz2': 'bz2', 'xz': 'xz', 'zst': 'zst',
            'lz4': 'lz4', 'lz': 'lz', 'lzo': 'lzo', 'lzma': 'lzma', 'z': 'z',
        }.get(outer)
        out_temp = _make_temp(suffix)
        ok = _compress_file(tar_temp, out_temp, outer, options.get('debug', False))
        _remove_quietly(tar_temp)
        if not ok:
            _remove_quietly(out_temp)
            summary.total_outsize = f_insize
            return
        packed = _commit_output(
            out_temp, dest, f_insize, verify=verify,
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
