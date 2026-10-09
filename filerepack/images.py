"""Images packers using the shared candidate lifecycle."""

import logging
import os
from os.path import abspath
from typing import Any, List, Optional
from shutil import copyfile, copyfileobj

from . import candidates as tx
from .commands import run_command as _run_command
from .models import PackResult
from .outcomes import record
from .tools import resolve_tool
from .transactions import guard_packer
import zlib
import struct
from .consts import DEFAULT_JPEG_QUALITY
from .utils import verify_output
from .verification import verify_preservation


@guard_packer
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
    ck = tx.commit_kwargs(**commit)
    if avifenc and avifdec:
        png_temp = tx.make_temp('.png')
        out_temp = tx.make_temp('.avif')
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
                tx.remove_quietly(out_temp)
                return None
            return tx.commit_output(
                out_temp, filepath, insize, verify='avif', lossless=not lossy, **ck
            )
        finally:
            tx.remove_quietly(png_temp)
            tx.remove_quietly(out_temp)
    out_temp = tx.make_temp('.avif')
    quality = '80' if lossy else '100'
    cmd = [
        convert_path or '', abspath(filepath), '-quality', quality, out_temp
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        tx.remove_quietly(out_temp)
        return None
    return tx.commit_output(out_temp, filepath, insize, verify='avif', lossless=not lossy, **ck)


@guard_packer
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
    out_temp = tx.make_temp(ext)
    quality = '80' if lossy else '100'
    cmd = [convert_path, abspath(filepath), '-quality', quality, out_temp]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        tx.remove_quietly(out_temp)
        return None
    return tx.commit_output(
        out_temp, filepath, insize, verify='heic', lossless=not lossy,
        **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_gif(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    gifsicle_path = resolve_tool('gifsicle')
    if gifsicle_path is None:
        if debug:
            logging.warning('gifsicle not installed')
        return None
    insize = os.path.getsize(filepath)
    tempfpath = tx.make_temp('.gif')
    cmd = [
        gifsicle_path, '-O3', '--lossy=0', abspath(filepath), '-o', tempfpath,
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        tx.remove_quietly(tempfpath)
        return None
    return tx.commit_output(
        tempfpath, filepath, insize, verify='gif', lossless=True, **tx.commit_kwargs(**commit)
    )


@guard_packer
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
    temp_png = tx.make_temp('.png')
    tempfpath = tx.make_temp('.webp')
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
            tx.remove_quietly(tempfpath)
            return None
        return tx.commit_output(
            tempfpath, filepath, insize, verify='webp', lossless=True, **tx.commit_kwargs(**commit)
        )
    finally:
        tx.remove_quietly(temp_png)
        tx.remove_quietly(tempfpath)


@guard_packer
def pack_svg(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .markup import pack_xml, rewrite_data_uris

    svgo_path = resolve_tool('svgo')
    scour_path = resolve_tool('scour') if svgo_path is None else None
    if svgo_path is None and scour_path is None:
        return pack_xml(filepath, debug=debug, quiet=quiet, **commit)
    insize = os.path.getsize(filepath)
    tempfpath = tx.make_temp('.svg')
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
        tx.remove_quietly(tempfpath)
        return pack_xml(filepath, debug=debug, quiet=quiet, **commit)
    try:
        with open(tempfpath, 'r', encoding='utf-8') as fh:
            text = fh.read()
        options = {**commit, 'debug': debug, 'quiet': quiet}
        rewritten = rewrite_data_uris(text, options)
        if rewritten != text:
            with open(tempfpath, 'w', encoding='utf-8') as fh:
                fh.write(rewritten)
    except (OSError, UnicodeError):
        pass
    return tx.commit_output(
        tempfpath, filepath, insize, verify='svg', **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_tif(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .format_support import pack_format
    return pack_format('tiff-native', filepath, {'debug': debug, 'quiet': quiet, **commit})


def _requires_presentation_metadata(path: str) -> bool:
    """Conservatively keep metadata when a backend cannot separate presentation fields."""
    try:
        from PIL import Image
        with Image.open(path) as image:
            return any(image.info.get(key) is not None for key in
                       ('icc_profile', 'exif', 'xmp', 'gamma', 'srgb', 'chromaticity', 'dpi'))
    except (ImportError, OSError, ValueError):
        return True


@guard_packer
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
    keep_meta = keep_meta or _requires_presentation_metadata(filepath)
    work = tx.make_temp('.jpg')
    copyfile(filepath, work)
    ck = tx.commit_kwargs(**commit)
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
        return tx.commit_output(work, filepath, insize, verify='jpg', lossless=not use_lossy, **ck)
    finally:
        tx.remove_quietly(work)


def _jpegtran_inplace(
    jpegtran_path: str, work: str, keep_meta: bool,
    debug: bool, quiet: bool,
) -> None:
    out = tx.make_temp('.jpg')
    copy_mode = 'all' if keep_meta else 'none'
    cmd = [
        jpegtran_path, '-optimize', '-progressive',
        '-copy', copy_mode, '-outfile', out, work,
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None or not verify_output(out, 'jpg'):
        tx.remove_quietly(out)
        return
    if os.path.getsize(out) < os.path.getsize(work):
        os.replace(out, work)
    else:
        tx.remove_quietly(out)


def _pngquant_lossy(
    filepath: str, png_quality: Optional[str], debug: bool, quiet: bool,
) -> Optional[str]:
    pngquant_path = resolve_tool('pngquant')
    if pngquant_path is None:
        if debug:
            logging.warning('pngquant not installed')
        return None
    tempfpath = tx.make_temp('.png')
    copyfile(filepath, tempfpath)
    quant = tx.own_sidecar(tempfpath.rsplit('.', 1)[0] + '-fs8.png')
    speed = {'high': '1', 'medium': '2', 'low': '3'}.get(png_quality or '', '1')
    cmd = [pngquant_path, '--force', '--speed', speed, tempfpath]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        tx.remove_quietly(tempfpath)
        return None
    if os.path.exists(quant):
        tx.remove_quietly(tempfpath)
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
        tempfpath = tx.make_temp('.png')
        copyfile(filepath, tempfpath)
        if oxipng_path:
            cmd = [oxipng_path, '-o', '4', '--nb', '--nc', '--np', '-q', tempfpath]
            if not keep_meta:
                cmd[3:3] = ['--strip', 'safe']
        else:
            cmd = [optipng_path or '', '-o7', '-nb', '-nc', '-np', '-quiet', tempfpath]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None and verify_output(tempfpath, 'png'):
            candidates.append(tempfpath)
        else:
            tx.remove_quietly(tempfpath)

    if zopflipng_path:
        z_out = tx.make_temp('.png')
        cmd = [zopflipng_path, '-y']
        if keep_meta:
            cmd.append('--keepchunks=iCCP,sRGB,gAMA,pHYs,eXIf,tEXt,zTXt,iTXt')
        cmd.extend([abspath(filepath), z_out])
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None and verify_output(z_out, 'png'):
            candidates.append(z_out)
        else:
            tx.remove_quietly(z_out)
    return candidates


@guard_packer
def pack_png(
    filepath: str, debug: bool = False, quiet: bool = False,
    png_quality: Optional[str] = None, lossy: bool = False,
    ultra: bool = False, keep_meta: bool = False, **commit: Any,
) -> Optional[PackResult]:
    insize = os.path.getsize(filepath)
    ck = tx.commit_kwargs(**commit)
    if lossy or png_quality is not None:
        tempfpath = _pngquant_lossy(filepath, png_quality, debug, quiet)
        if tempfpath is None:
            return None
        return tx.commit_output(tempfpath, filepath, insize, verify='png', **ck)

    candidates = _png_lossless_candidates(
        filepath, ultra, keep_meta or _requires_presentation_metadata(filepath), debug, quiet,
    )
    if not candidates:
        return None
    preserving = []
    for path in candidates:
        if verify_preservation(filepath, path, 'png'):
            preserving.append(path)
        else:
            tx.remove_quietly(path)
    if not preserving:
        record('failed', 'preservation_failed', 'No PNG candidate preserves the source')
        return None
    candidates = preserving
    best = min(candidates, key=os.path.getsize)
    for path in candidates:
        if path != best:
            tx.remove_quietly(path)
    return tx.commit_output(best, filepath, insize, verify='png', lossless=True, **ck)


@guard_packer
def pack_svgz(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    import gzip
    insize = os.path.getsize(filepath)
    svg_temp = tx.make_temp('.svg')
    gz_temp = tx.make_temp('.svgz')
    try:
        with gzip.open(filepath, 'rb') as f_in, open(svg_temp, 'wb') as f_out:
            copyfileobj(f_in, f_out, length=tx.COPY_BUF)
        pack_svg(
            svg_temp, debug=debug, quiet=quiet, dryrun=False,
            keep_if_larger=True, min_savings=None,
        )
        with open(svg_temp, 'rb') as f_in, gzip.open(gz_temp, 'wb', compresslevel=9) as f_out:
            copyfileobj(f_in, f_out, length=tx.COPY_BUF)
        return tx.commit_output(
            gz_temp, filepath, insize, verify='svgz', **tx.commit_kwargs(**commit)
        )
    except Exception:
        return None
    finally:
        tx.remove_quietly(svg_temp)
        tx.remove_quietly(gz_temp)


@guard_packer
def pack_jxl(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    cjxl = resolve_tool('cjxl')
    djxl = resolve_tool('djxl')
    if cjxl is None or djxl is None:
        return None
    insize = os.path.getsize(filepath)
    png_temp = tx.make_temp('.png')
    out_temp = tx.make_temp('.jxl')
    ck = tx.commit_kwargs(**commit)
    try:
        if _run_command(
            [djxl, abspath(filepath), png_temp], quiet=quiet, debug=debug
        ) is None:
            return None
        if lossy:
            encode = [cjxl, png_temp, out_temp, '-q', '85']
        else:
            encode = [cjxl, png_temp, out_temp, '-d', '0']
        if _run_command(encode, quiet=quiet, debug=debug) is None:
            return None
        return tx.commit_output(out_temp, filepath, insize, verify='jxl', lossless=not lossy, **ck)
    finally:
        tx.remove_quietly(png_temp)
        tx.remove_quietly(out_temp)


def _pack_magick(
    filepath: str, suffix: str, verify: str,
    extra: Optional[List[str]] = None, lossy: bool = False,
    debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    convert_path = resolve_tool('convert')
    if convert_path is None:
        return None
    insize = os.path.getsize(filepath)
    out_temp = tx.make_temp(suffix)
    quality = '80' if lossy else '100'
    cmd = [convert_path, abspath(filepath)]
    if extra:
        cmd.extend(extra)
    cmd.extend(['-quality', quality, out_temp])
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        tx.remove_quietly(out_temp)
        return None
    return tx.commit_output(
        out_temp, filepath, insize, verify=verify, lossless=not lossy,
        **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_bmp(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.bmp', 'bmp', debug=debug, quiet=quiet, **commit)


@guard_packer
def pack_tga(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.tga', 'tga', debug=debug, quiet=quiet, **commit)


@guard_packer
def pack_pnm(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.pnm', 'pnm', debug=debug, quiet=quiet, **commit)


@guard_packer
def pack_pcx(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(filepath, '.pcx', 'pcx', debug=debug, quiet=quiet, **commit)


@guard_packer
def pack_jp2(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossy: bool = False, **commit: Any,
) -> Optional[PackResult]:
    ext = '.' + filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else '.jp2'
    return _pack_magick(
        filepath, ext, 'jp2', lossy=lossy, debug=debug, quiet=quiet, **commit
    )


@guard_packer
def pack_exr(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(
        filepath, '.exr', 'exr', extra=['-compress', 'Zip'],
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_dng(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tiffcp_path = resolve_tool('tiffcp')
    if tiffcp_path is None:
        return None
    insize = os.path.getsize(filepath)
    out_temp = tx.make_temp('.dng')
    result = _run_command(
        [tiffcp_path, '-c', 'zip', abspath(filepath), out_temp],
        quiet=quiet, debug=debug,
    )
    if result is None:
        tx.remove_quietly(out_temp)
        return None
    return tx.commit_output(
        out_temp, filepath, insize, verify='dng', **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_ico(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(
        filepath, '.ico', 'ico', extra=['-strip'],
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_icns(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_magick(
        filepath, '.icns', 'icns', extra=['-strip'],
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_psd(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Recompress ZIP-encoded Photoshop channels; leave RLE/raw layers alone."""
    try:
        from .native import read_native
        data = read_native(filepath)
    except OSError:
        return None
    rewritten = _recompress_psd_bytes(data)
    if rewritten is None or rewritten == data:
        return None
    insize = len(data)
    out_temp = tx.make_temp('.psd')
    try:
        with open(out_temp, 'wb') as fh:
            fh.write(rewritten)
        return tx.commit_output(
            out_temp, filepath, insize, verify='psd', **tx.commit_kwargs(**commit)
        )
    except Exception:
        tx.remove_quietly(out_temp)
        return None


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
        from .format_support import current_budget, Budget, FormatLimits, inflate
        budget = current_budget() or Budget(FormatLimits())
        raw = inflate(blob, budget)
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
