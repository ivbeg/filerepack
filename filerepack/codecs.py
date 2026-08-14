# -*- coding: utf-8 -*-

"""Standalone packers for formats added after the core ZIP/OOXML set."""

import os
import struct
import zlib
from os.path import abspath
from shutil import copyfile
from typing import Any, List, Optional

from .models import PackResult
from .tools import resolve_tool


def _r() -> Any:
    from . import repack as r
    return r


def pack_lz4(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('lz4')
    if tool is None:
        return None
    r = _r()
    return r._pack_pipe_codec(
        filepath, [tool, '-d', '-c', filepath], [tool, '-9', '-c'],
        '.lz4', 'lz4', debug=debug, **commit,
    )


def pack_lzip(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('lzip')
    if tool is None:
        return None
    r = _r()
    return r._pack_pipe_codec(
        filepath, [tool, '-d', '-c', filepath], [tool, '-9', '-c'],
        '.lz', 'lz', debug=debug, **commit,
    )


def pack_lzo(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('lzop')
    if tool is None:
        return None
    r = _r()
    return r._pack_pipe_codec(
        filepath, [tool, '-d', '-c', filepath], [tool, '-9', '-c'],
        '.lzo', 'lzo', debug=debug, **commit,
    )


def pack_lzma(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    import lzma
    r = _r()

    def _lzma_out(path: str):
        return lzma.open(path, 'wb', format=lzma.FORMAT_ALONE, preset=9)

    def _lzma_in(path: str, mode: str = 'rb'):
        return lzma.open(path, mode, format=lzma.FORMAT_ALONE)

    return r._pack_stream_codec(
        filepath, '.lzma', _lzma_in, _lzma_out, 'lzma', ['-9', '-c'],
        'lzma', debug=debug, quiet=quiet, **commit,
    )


def pack_compress(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    compress = resolve_tool('compress')
    gzip_tool = resolve_tool('gzip') or resolve_tool('pigz')
    if compress is None or gzip_tool is None:
        if debug:
            import logging
            logging.warning('compress/gzip not installed for .Z')
        return None
    r = _r()
    return r._pack_pipe_codec(
        filepath, [gzip_tool, '-d', '-c', filepath], [compress, '-c'],
        '.Z', 'z', debug=debug, **commit,
    )


def pack_svgz(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    import gzip
    from shutil import copyfileobj
    r = _r()
    insize = os.path.getsize(filepath)
    svg_temp = r._make_temp('.svg')
    gz_temp = r._make_temp('.svgz')
    try:
        with gzip.open(filepath, 'rb') as f_in, open(svg_temp, 'wb') as f_out:
            copyfileobj(f_in, f_out, length=r._COPY_BUF)
        from .repack import pack_svg
        pack_svg(
            svg_temp, debug=debug, quiet=quiet, dryrun=False,
            keep_if_larger=True, min_savings=None,
        )
        with open(svg_temp, 'rb') as f_in, gzip.open(gz_temp, 'wb', compresslevel=9) as f_out:
            copyfileobj(f_in, f_out, length=r._COPY_BUF)
        return r._commit_output(
            gz_temp, filepath, insize, verify='svgz', **r._commit_kwargs(**commit)
        )
    except Exception:
        return None
    finally:
        r._remove_quietly(svg_temp)
        r._remove_quietly(gz_temp)


def pack_jxl(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    cjxl = resolve_tool('cjxl')
    djxl = resolve_tool('djxl')
    if cjxl is None or djxl is None:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    png_temp = r._make_temp('.png')
    out_temp = r._make_temp('.jxl')
    ck = r._commit_kwargs(**commit)
    try:
        if r._run_command(
            [djxl, abspath(filepath), png_temp], quiet=quiet, debug=debug
        ) is None:
            return None
        if lossy:
            encode = [cjxl, png_temp, out_temp, '-q', '85']
        else:
            encode = [cjxl, png_temp, out_temp, '-d', '0']
        if r._run_command(encode, quiet=quiet, debug=debug) is None:
            return None
        return r._commit_output(out_temp, filepath, insize, verify='jxl', **ck)
    finally:
        r._remove_quietly(png_temp)
        r._remove_quietly(out_temp)


def _pack_magick(
    filepath: str, suffix: str, verify: str,
    extra: Optional[List[str]] = None, lossy: bool = False,
    debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    convert_path = resolve_tool('convert')
    if convert_path is None:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp(suffix)
    quality = '80' if lossy else '100'
    cmd = [convert_path, abspath(filepath)]
    if extra:
        cmd.extend(extra)
    cmd.extend(['-quality', quality, out_temp])
    result = r._run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        r._remove_quietly(out_temp)
        return None
    return r._commit_output(
        out_temp, filepath, insize, verify=verify, **r._commit_kwargs(**commit)
    )


def pack_bmp(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.bmp', 'bmp', debug=debug, quiet=quiet, **commit)


def pack_tga(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.tga', 'tga', debug=debug, quiet=quiet, **commit)


def pack_pnm(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.pnm', 'pnm', debug=debug, quiet=quiet, **commit)


def pack_pcx(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.pcx', 'pcx', debug=debug, quiet=quiet, **commit)


def pack_xml(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .markup import pack_xml as _pack
    return _pack(filepath, debug=debug, quiet=quiet, **commit)


def pack_json(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .markup import pack_json as _pack
    return _pack(filepath, debug=debug, quiet=quiet, **commit)


def _cover_options(**commit: Any) -> dict:
    return {
        'debug': bool(commit.get('debug', False)),
        'quiet': bool(commit.get('quiet', False)),
        'pack_images': bool(commit.get('pack_images', True)),
        'keep_meta': bool(commit.get('keep_meta', False)),
        'lossy': bool(commit.get('lossy', False)),
        'ultra': bool(commit.get('ultra', False)),
        'jpeg_quality': commit.get('jpeg_quality'),
        'png_quality': commit.get('png_quality'),
    }


def _copy_with_covers(filepath: str, suffix: str, **commit: Any) -> str:
    from .covers import optimize_embedded_covers
    r = _r()
    work = r._make_temp(suffix)
    copyfile(filepath, work)
    optimize_embedded_covers(work, _cover_options(**commit))
    return work


def pack_jp2(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.jp2'
    return _pack_magick(
        filepath, ext, 'jp2', lossy=lossy, debug=debug, quiet=quiet, **commit
    )


def pack_exr(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(
        filepath, '.exr', 'exr', extra=['-compress', 'Zip'],
        debug=debug, quiet=quiet, **commit,
    )


def pack_dcm(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Lossless JPEG-LS recompress of uncompressed/RLE image DICOM.

    ``lossy`` in *commit* is ignored; DICOM is never lossy-encoded.
    """
    from .dicom import dicom_is_packable
    if not dicom_is_packable(filepath):
        return None
    gdcm = resolve_tool('gdcmconv')
    dcmcjpls = resolve_tool('dcmcjpls')
    tool = gdcm or dcmcjpls
    if tool is None:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp('.dcm')
    abs_in = abspath(filepath)
    if gdcm:
        cmd = [gdcm, '--jpegls', abs_in, out_temp]
    else:
        cmd = [tool, abs_in, out_temp]
    result = r._run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        r._remove_quietly(out_temp)
        return None
    return r._commit_output(
        out_temp, filepath, insize, verify='dcm', **r._commit_kwargs(**commit)
    )


def pack_dng(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tiffcp_path = resolve_tool('tiffcp')
    if tiffcp_path is None:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp('.dng')
    result = r._run_command(
        [tiffcp_path, '-c', 'zip', abspath(filepath), out_temp],
        quiet=quiet, debug=debug,
    )
    if result is None:
        r._remove_quietly(out_temp)
        return None
    return r._commit_output(
        out_temp, filepath, insize, verify='dng', **r._commit_kwargs(**commit)
    )


def pack_ico(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(
        filepath, '.ico', 'ico', extra=['-strip'],
        debug=debug, quiet=quiet, **commit,
    )


def pack_icns(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(
        filepath, '.icns', 'icns', extra=['-strip'],
        debug=debug, quiet=quiet, **commit,
    )


def pack_mov(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _r()._pack_video(
        filepath, 'mov', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


def pack_m4v(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _r()._pack_video(
        filepath, 'm4v', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


def pack_3gp(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _r()._pack_video(
        filepath, '3gp', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def pack_ts(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _r()._pack_video(
        filepath, 'ts', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def _probe_audio_codec(filepath: str, ffmpeg: str, debug: bool) -> str:
    import logging
    import subprocess
    try:
        proc = subprocess.run(
            [ffmpeg, '-i', abspath(filepath)],
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=60,
        )
        text = (proc.stderr or '') + (proc.stdout or '')
    except (OSError, subprocess.TimeoutExpired):
        return ''
    if debug:
        logging.debug('ffmpeg probe for %s: %s', filepath, text[:200])
    lower = text.lower()
    for marker in (
        'audio: alac', 'audio: aac', 'audio: flac', 'audio: wavpack',
        'audio: tta', 'audio: ape', 'audio: vorbis', 'audio: opus',
        'audio: mp3',
    ):
        if marker in lower:
            return marker.split(': ', 1)[1]
    return ''


def _pack_ffmpeg_audio(
    filepath: str, codec: str, suffix: str, verify: str,
    allowed: tuple, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    ffmpeg = resolve_tool('ffmpeg')
    if ffmpeg is None:
        return None
    r = _r()
    found = _probe_audio_codec(filepath, ffmpeg, debug)
    if found and found not in allowed:
        return None
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp(suffix)
    cmd = [
        ffmpeg, '-i', abspath(filepath), '-c:a', codec, '-c:v', 'copy',
        '-y', out_temp,
    ]
    result = r._run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        r._remove_quietly(out_temp)
        return None
    return r._commit_output(
        out_temp, filepath, insize, verify=verify, **r._commit_kwargs(**commit)
    )


def pack_m4a(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    r = _r()
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(filepath, '.m4a', debug=debug, quiet=quiet, **commit)
    ffmpeg = resolve_tool('ffmpeg')
    if ffmpeg:
        _pack_ffmpeg_audio(
            work, 'alac', '.m4a', 'm4a', allowed=('alac',),
            debug=debug, quiet=quiet, dryrun=False, keep_if_larger=True,
            min_savings=None,
        )
    elif os.path.getsize(work) >= insize:
        r._remove_quietly(work)
        return None
    return r._commit_output(
        work, filepath, insize, verify='m4a', **r._commit_kwargs(**commit)
    )


def pack_wv(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_ffmpeg_audio(
        filepath, 'wavpack', '.wv', 'wv', allowed=('wavpack', ''),
        debug=debug, quiet=quiet, **commit,
    )


def pack_tta(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_ffmpeg_audio(
        filepath, 'tta', '.tta', 'tta', allowed=('tta', ''),
        debug=debug, quiet=quiet, **commit,
    )


def pack_oga(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    ffmpeg = resolve_tool('ffmpeg')
    found = ''
    if ffmpeg:
        found = _probe_audio_codec(filepath, ffmpeg, debug)
    if found in ('vorbis', 'opus'):
        return pack_ogg(filepath, debug=debug, quiet=quiet, **commit)
    r = _r()
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(filepath, '.oga', debug=debug, quiet=quiet, **commit)
    if ffmpeg:
        _pack_ffmpeg_audio(
            work, 'flac', '.oga', 'oga', allowed=('flac', ''),
            debug=debug, quiet=quiet, dryrun=False, keep_if_larger=True,
            min_savings=None,
        )
    elif os.path.getsize(work) >= insize:
        r._remove_quietly(work)
        return None
    return r._commit_output(
        work, filepath, insize, verify='oga', **r._commit_kwargs(**commit)
    )


def pack_ape(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    mac = resolve_tool('mac')
    r = _r()
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(filepath, '.ape', debug=debug, quiet=quiet, **commit)
    if mac:
        out_temp = r._make_temp('.ape')
        result = r._run_command(
            [mac, abspath(work), out_temp, '-c5000'],
            quiet=quiet, debug=debug,
        )
        if result is not None:
            r._remove_quietly(work)
            work = out_temp
        else:
            r._remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        r._remove_quietly(work)
        return None
    return r._commit_output(
        work, filepath, insize, verify='ape', **r._commit_kwargs(**commit)
    )


def pack_sqlite(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    import sqlite3
    r = _r()
    try:
        with open(filepath, 'rb') as fh:
            if not fh.read(16).startswith(b'SQLite format 3'):
                return None
    except OSError:
        return None
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp('.sqlite')
    r._remove_quietly(out_temp)
    try:
        src = sqlite3.connect(filepath)
        try:
            escaped = abspath(out_temp).replace("'", "''")
            src.execute(f"VACUUM INTO '{escaped}'")
        except sqlite3.Error:
            r._remove_quietly(out_temp)
            dst = sqlite3.connect(out_temp)
            try:
                src.backup(dst)
                dst.execute('VACUUM')
            finally:
                dst.close()
        finally:
            src.close()
        return r._commit_output(
            out_temp, filepath, insize, verify='sqlite', **r._commit_kwargs(**commit)
        )
    except sqlite3.Error:
        r._remove_quietly(out_temp)
        return None


def pack_orc(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        import pyarrow.orc as orc
    except ImportError:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp('.orc')
    try:
        table = orc.read_table(filepath)
        orc.write_table(table, out_temp, compression='zstd')
        return r._commit_output(
            out_temp, filepath, insize, verify='orc', **r._commit_kwargs(**commit)
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def pack_avro(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        import fastavro
    except ImportError:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    out_temp = r._make_temp('.avro')
    try:
        with open(filepath, 'rb') as src, open(out_temp, 'wb') as dest:
            reader = fastavro.reader(src)
            schema = reader.writer_schema
            fastavro.writer(dest, schema, reader, codec='zstandard')
        return r._commit_output(
            out_temp, filepath, insize, verify='avro', **r._commit_kwargs(**commit)
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def pack_feather(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        import pyarrow.feather as feather
    except ImportError:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.feather'
    out_temp = r._make_temp(ext)
    try:
        table = feather.read_table(filepath)
        feather.write_feather(table, out_temp, compression='zstd')
        return r._commit_output(
            out_temp, filepath, insize, **r._commit_kwargs(**commit)
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def pack_arrow(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        import pyarrow as pa
    except ImportError:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.arrow'
    out_temp = r._make_temp(ext)
    try:
        with pa.memory_map(filepath, 'r') as source:
            try:
                reader = pa.ipc.open_file(source)
            except (pa.ArrowInvalid, OSError):
                source.seek(0)
                reader = pa.ipc.open_stream(source)
            table = reader.read_all()
        options = pa.ipc.IpcWriteOptions(compression='zstd')
        with pa.OSFile(out_temp, 'wb') as sink:
            with pa.ipc.new_file(sink, table.schema, options=options) as writer:
                writer.write_table(table)
        return r._commit_output(
            out_temp, filepath, insize, **r._commit_kwargs(**commit)
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def pack_hdf5(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('h5repack')
    if tool is None:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.h5'
    out_temp = r._make_temp(ext)
    r._remove_quietly(out_temp)
    result = r._run_command(
        [tool, '-f', 'GZIP=9', abspath(filepath), out_temp],
        quiet=quiet, debug=debug,
    )
    if result is None:
        r._remove_quietly(out_temp)
        return None
    return r._commit_output(
        out_temp, filepath, insize, verify='hdf5', **r._commit_kwargs(**commit)
    )


def pack_netcdf(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('nccopy')
    if tool is None:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.nc'
    out_temp = r._make_temp(ext)
    r._remove_quietly(out_temp)
    result = r._run_command(
        [tool, '-d', '9', '-s', abspath(filepath), out_temp],
        quiet=quiet, debug=debug,
    )
    if result is None:
        r._remove_quietly(out_temp)
        return None
    return r._commit_output(
        out_temp, filepath, insize, verify='nc', **r._commit_kwargs(**commit)
    )


def pack_woff(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    r = _r()
    insize = os.path.getsize(filepath)
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.woff'
    flavor = 'woff2' if ext == '.woff2' else 'woff'
    out_temp = r._make_temp(ext)
    try:
        font = TTFont(filepath)
        font.flavor = flavor
        font.save(out_temp)
        font.close()
        verify = 'woff2' if flavor == 'woff2' else 'woff'
        return r._commit_output(
            out_temp, filepath, insize, verify=verify, **r._commit_kwargs(**commit)
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def pack_woff2(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    result = pack_woff(filepath, debug=debug, quiet=quiet, **commit)
    if result is not None:
        return result
    compress = resolve_tool('woff2_compress')
    decompress = resolve_tool('woff2_decompress')
    if compress is None or decompress is None:
        return None
    import tempfile
    from shutil import copy2
    r = _r()
    insize = os.path.getsize(filepath)
    tmpdir = tempfile.mkdtemp(prefix='filerepack-woff2-')
    try:
        src_copy = os.path.join(tmpdir, 'font.woff2')
        copy2(filepath, src_copy)
        if r._run_command(
            [decompress, src_copy], quiet=quiet, debug=debug
        ) is None:
            return None
        ttf = os.path.join(tmpdir, 'font.ttf')
        if not os.path.exists(ttf):
            return None
        if r._run_command(
            [compress, ttf], quiet=quiet, debug=debug
        ) is None:
            return None
        out_woff = os.path.join(tmpdir, 'font.woff2')
        if not os.path.exists(out_woff):
            return None
        staged = r._make_temp('.woff2')
        copy2(out_woff, staged)
        return r._commit_output(
            staged, filepath, insize, verify='woff2', **r._commit_kwargs(**commit)
        )
    finally:
        r._remove_quietly(tmpdir)


def pack_mp3(
    filepath: str, debug: bool = False, quiet: bool = False,
    ultra: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Lossless MP3 frame packing via mp3packer (not a transcode)."""
    tool = resolve_tool('mp3packer')
    r = _r()
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(
        filepath, '.mp3', debug=debug, quiet=quiet, ultra=ultra, **commit
    )
    if tool:
        out_temp = r._make_temp('.mp3')
        cmd = [tool]
        if ultra:
            cmd.append('-z')
        cmd.extend([abspath(work), out_temp])
        result = r._run_command(cmd, quiet=quiet, debug=debug)
        if result is not None:
            r._remove_quietly(work)
            work = out_temp
        else:
            r._remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        r._remove_quietly(work)
        return None
    return r._commit_output(
        work, filepath, insize, verify='mp3', **r._commit_kwargs(**commit)
    )


def pack_ogg(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('optivorbis')
    r = _r()
    insize = os.path.getsize(filepath)
    suffix = '.opus' if filepath.lower().endswith('.opus') else '.ogg'
    work = _copy_with_covers(filepath, suffix, debug=debug, quiet=quiet, **commit)
    if tool:
        out_temp = r._make_temp(suffix)
        result = r._run_command(
            [tool, abspath(work), out_temp], quiet=quiet, debug=debug,
        )
        if result is not None:
            r._remove_quietly(work)
            work = out_temp
        else:
            r._remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        r._remove_quietly(work)
        return None
    return r._commit_output(
        work, filepath, insize, verify='ogg', **r._commit_kwargs(**commit)
    )


def pack_ai(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, pdf_profile: Optional[str] = None,
    jpeg_quality: Optional[int] = None, **commit: Any,
) -> Optional[PackResult]:
    """Illustrator files that are PDF wrappers go through the PDF packer."""
    if not _is_pdf_header(filepath):
        return None
    from .repack import pack_pdf
    return pack_pdf(
        filepath, debug=debug, quiet=quiet, lossy=lossy,
        pdf_profile=pdf_profile, jpeg_quality=jpeg_quality, **commit
    )


def pack_psd(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Recompress ZIP-encoded Photoshop channels; leave RLE/raw layers alone."""
    r = _r()
    try:
        with open(filepath, 'rb') as fh:
            data = fh.read()
    except OSError:
        return None
    rewritten = _recompress_psd_bytes(data)
    if rewritten is None or rewritten == data:
        return None
    insize = len(data)
    out_temp = r._make_temp('.psd')
    try:
        with open(out_temp, 'wb') as fh:
            fh.write(rewritten)
        return r._commit_output(
            out_temp, filepath, insize, verify='psd', **r._commit_kwargs(**commit)
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def _is_pdf_header(path: str) -> bool:
    try:
        with open(path, 'rb') as fh:
            head = fh.read(1024)
    except OSError:
        return False
    return head.lstrip().startswith(b'%PDF') or b'%PDF-' in head[:1024]


class _PsdError(Exception):
    pass


class _PsdBuf:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read(self, n: int) -> bytes:
        if n < 0 or self.remaining() < n:
            raise _PsdError('truncated PSD')
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def skip(self, n: int) -> None:
        self.read(n)

    def u16(self) -> int:
        return int.from_bytes(self.read(2), 'big')

    def i16(self) -> int:
        return int.from_bytes(self.read(2), 'big', signed=True)

    def u32(self) -> int:
        return int.from_bytes(self.read(4), 'big')

    def u64(self) -> int:
        return int.from_bytes(self.read(8), 'big')

    def length(self, psb: bool) -> int:
        return self.u64() if psb else self.u32()


def _rezip_payload(blob: bytes) -> bytes:
    if len(blob) < 2:
        return blob
    try:
        raw = zlib.decompress(blob)
        out = zlib.compress(raw, 9)
    except zlib.error:
        return blob
    return out if 0 < len(out) < len(blob) else blob


def _recompress_psd_channel(block: bytes) -> bytes:
    if len(block) < 2:
        return block
    compression = int.from_bytes(block[:2], 'big')
    if compression not in (2, 3):
        return block
    new_payload = _rezip_payload(block[2:])
    return block[:2] + new_payload


def _recompress_layer_payload(payload: bytes, psb: bool) -> bytes:
    if not payload:
        return payload
    buf = _PsdBuf(payload)
    try:
        info_len = buf.length(psb)
        info_bytes = buf.read(info_len)
        rest = payload[buf.pos:]
        rebuilt = _recompress_layer_info(info_bytes, psb)
        if rebuilt is None:
            return payload
        len_bytes = len(rebuilt).to_bytes(8 if psb else 4, 'big')
        return len_bytes + rebuilt + rest
    except _PsdError:
        return payload


def _recompress_layer_info(info: bytes, psb: bool) -> Optional[bytes]:
    if not info:
        return info
    buf = _PsdBuf(info)
    try:
        count = buf.i16()
        n_layers = abs(count)
        records: List[bytes] = []
        channel_sizes: List[int] = []
        length_size = 8 if psb else 4
        for _ in range(n_layers):
            start = buf.pos
            buf.skip(16)
            n_ch = buf.u16()
            size_offsets = []
            for _ch in range(n_ch):
                buf.skip(2)
                size_offsets.append(buf.pos)
                channel_sizes.append(buf.length(psb))
            buf.skip(12)
            extra_len = buf.u32()
            buf.skip(extra_len)
            records.append(info[start:buf.pos])
        channels = [_recompress_psd_channel(buf.read(size)) for size in channel_sizes]
        if buf.remaining() not in (0, 1):
            return None
        padding = buf.read(buf.remaining()) if buf.remaining() else b''
        patched = bytearray()
        patched += count.to_bytes(2, 'big', signed=True)
        idx = 0
        for rec in records:
            rec_buf = bytearray(rec)
            inner = _PsdBuf(bytes(rec))
            inner.skip(16)
            n_ch = inner.u16()
            for _ch in range(n_ch):
                inner.skip(2)
                new_len = len(channels[idx])
                off = inner.pos
                rec_buf[off:off + length_size] = new_len.to_bytes(length_size, 'big')
                inner.length(psb)
                idx += 1
            patched += rec_buf
        for block in channels:
            patched += block
        patched += padding
        return bytes(patched)
    except (_PsdError, IndexError, struct.error):
        return None


def _recompress_psd_bytes(data: bytes) -> Optional[bytes]:
    if not data.startswith(b'8BPS') or len(data) < 26:
        return None
    try:
        version = struct.unpack('>H', data[4:6])[0]
        if version not in (1, 2):
            return None
        psb = version == 2
        buf = _PsdBuf(data, 26)
        buf.skip(buf.u32())
        buf.skip(buf.u32())
        layer_len_off = buf.pos
        layer_len = buf.length(psb)
        layer_payload = buf.read(layer_len)
        composite = bytearray(data[buf.pos:])
        new_layers = _recompress_layer_payload(bytes(layer_payload), psb)
        if len(composite) >= 2:
            compression = int.from_bytes(composite[:2], 'big')
            if compression in (2, 3):
                new_body = _rezip_payload(bytes(composite[2:]))
                composite = bytearray(composite[:2]) + new_body
        layer_len_bytes = len(new_layers).to_bytes(8 if psb else 4, 'big')
        return data[:layer_len_off] + layer_len_bytes + new_layers + bytes(composite)
    except (_PsdError, ValueError, OverflowError):
        return None

