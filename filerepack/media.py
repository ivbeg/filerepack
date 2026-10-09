"""Media packers using the shared candidate lifecycle."""

import logging
import os
from os.path import abspath
from typing import Any, Dict, Optional
from shutil import copyfile

from . import candidates as tx
from .commands import capture_command, run_command as _run_command
from .models import PackResult
from .tools import resolve_tool
from .transactions import guard_packer
from .destinations import DestinationPlan, PathReservation, normalize_path
from .validation import validate_options, video_mode


@guard_packer
def pack_flac(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    from .covers import optimize_embedded_covers

    flac = resolve_tool('flac')
    insize = os.path.getsize(filepath)
    work = tx.make_temp('.flac')
    copyfile(filepath, work)
    optimize_embedded_covers(work, {
        'debug': debug, 'quiet': quiet,
        'pack_images': bool(commit.get('pack_images', True)),
        'keep_meta': bool(commit.get('keep_meta', False)),
        'lossy': bool(commit.get('lossy', False)),
        'ultra': bool(commit.get('ultra', False)),
    })
    if flac is not None:
        out_temp = tx.make_temp('.flac')
        cmd = [flac, '--best', '--verify', '-f', '-o', out_temp, abspath(work)]
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None:
            tx.remove_quietly(work)
            work = out_temp
        else:
            tx.remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        tx.remove_quietly(work)
        if debug:
            logging.warning('flac not installed')
        return None
    return tx.commit_output(
        work, filepath, insize, verify='flac', **tx.commit_kwargs(**commit)
    )


def _encode_video(
    ffmpeg_path: str, src: str, dest: str, lossless: bool,
    quiet: bool, debug: bool, container: str = 'mp4', mode: Optional[str] = None,
) -> bool:
    mode = mode or ('lossless' if lossless else 'remux')
    mapping = ['-map', '0', '-map_metadata', '0', '-map_chapters', '0', '-copy_unknown']
    if mode == 'remux':
        cmd = [ffmpeg_path, '-nostdin', '-i', abspath(src)] + mapping + ['-c', 'copy', '-y', dest]
    elif container == 'webm':
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
    if mode != 'remux':
        cmd[1:1] = ['-nostdin']
        cmd[4:4] = mapping + ['-c', 'copy']
    from .format_support import tool_threads
    cmd[1:1] = ['-threads', str(tool_threads())]
    cmd[-1:-1] = ['-threads', str(tool_threads())]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    return result is not None and os.path.exists(dest) and os.path.getsize(dest) > 0


def _pack_video(
    filepath: str, mode: str, lossless: bool = False,
    convert_container: bool = True, debug: bool = False, quiet: bool = False,
    **commit: Any,
) -> Optional[PackResult]:
    commit = validate_options({**commit, 'wmv_lossless': lossless})
    commit['_video_mode'] = video_mode(commit)
    filepath = normalize_path(filepath)
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
    plan = DestinationPlan(filepath, dest, overwrite=bool(commit.get('overwrite', False)))
    plan.validate()
    suffix = '.' + dest.rsplit('.', 1)[-1].lower() if '.' in dest else '.' + out_mode
    if out_mode in ('mp4', 'mov', 'm4v', '3gp'):
        verify = 'mp4'
    elif out_mode in ('ts', 'mts', 'm2ts'):
        verify = 'ts'
    else:
        verify = out_mode
    with PathReservation(plan.paths, dryrun=bool(commit.get('dryrun', False))) as reservation:
        plan.validate()
        return _pack_video_reserved(
            filepath, dest, suffix, out_mode, verify, ffmpeg_path, lossless,
            quiet, debug, insize, reservation, commit,
        )


def _pack_video_reserved(
    filepath: str, dest: str, suffix: str, out_mode: str, verify: str,
    ffmpeg_path: str, lossless: bool, quiet: bool, debug: bool,
    insize: int, reservation: PathReservation, commit: Dict[str, Any],
) -> Optional[PackResult]:
    tempfpath = tx.make_temp(suffix)
    try:
        if not _encode_video(
            ffmpeg_path, filepath, tempfpath, lossless, quiet, debug,
            container=out_mode, mode=commit['_video_mode'],
        ):
            return None
        from .media_verify import verify_media_preservation
        if not verify_media_preservation(filepath, tempfpath, commit['_video_mode'],
                                         bool(commit.get('keep_meta', False))):
            from .outcomes import record
            record('failed', 'media_preservation_failed', 'Media streams or content changed')
            return None
        result = tx.commit_output(
            tempfpath, dest, insize, verify=verify, reservation=reservation,
            overwrite=dest == filepath or bool(commit.get('overwrite', False)),
            rejected_path=filepath,
            **tx.commit_kwargs(**commit),
        )
        if result and result.replaced and dest != filepath:
            reservation.require_source_unchanged()
            tx.remove_quietly(filepath)
        return result
    finally:
        tx.remove_quietly(tempfpath)


@guard_packer
def pack_wmv(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'wmv', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_mp4(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'mp4', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_avi(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'avi', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_asf(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'asf', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_mkv(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'mkv', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_webm(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'webm', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


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
    work = tx.make_temp(suffix)
    copyfile(filepath, work)
    optimize_embedded_covers(work, _cover_options(**commit))
    return work


@guard_packer
def pack_mov(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'mov', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_m4v(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'm4v', lossless=lossless, convert_container=False,
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_3gp(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, '3gp', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_ts(
    filepath: str, debug: bool = False, quiet: bool = False,
    lossless: bool = False, convert_container: bool = True, **commit: Any,
) -> Optional[PackResult]:
    return _pack_video(
        filepath, 'ts', lossless=lossless,
        convert_container=convert_container, debug=debug, quiet=quiet, **commit,
    )


def _probe_audio_codec(filepath: str, ffmpeg: str, debug: bool) -> str:
    import logging
    proc = capture_command([ffmpeg, '-i', abspath(filepath)], timeout=60)
    if proc is None:
        return ''
    text = (proc.stderr or '') + (proc.stdout or '')
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
    found = _probe_audio_codec(filepath, ffmpeg, debug)
    if found and found not in allowed:
        return None
    insize = os.path.getsize(filepath)
    out_temp = tx.make_temp(suffix)
    cmd = [
        ffmpeg, '-i', abspath(filepath), '-c:a', codec, '-c:v', 'copy',
        '-y', out_temp,
    ]
    result = _run_command(cmd, quiet=quiet, debug=debug)
    if result is None:
        tx.remove_quietly(out_temp)
        return None
    return tx.commit_output(
        out_temp, filepath, insize, verify=verify, **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_m4a(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
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
        tx.remove_quietly(work)
        return None
    return tx.commit_output(
        work, filepath, insize, verify='m4a', **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_wv(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_ffmpeg_audio(
        filepath, 'wavpack', '.wv', 'wv', allowed=('wavpack', ''),
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_tta(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    return _pack_ffmpeg_audio(
        filepath, 'tta', '.tta', 'tta', allowed=('tta', ''),
        debug=debug, quiet=quiet, **commit,
    )


@guard_packer
def pack_oga(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    ffmpeg = resolve_tool('ffmpeg')
    found = ''
    if ffmpeg:
        found = _probe_audio_codec(filepath, ffmpeg, debug)
    if found in ('vorbis', 'opus'):
        return pack_ogg(filepath, debug=debug, quiet=quiet, **commit)
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(filepath, '.oga', debug=debug, quiet=quiet, **commit)
    if ffmpeg:
        _pack_ffmpeg_audio(
            work, 'flac', '.oga', 'oga', allowed=('flac', ''),
            debug=debug, quiet=quiet, dryrun=False, keep_if_larger=True,
            min_savings=None,
        )
    elif os.path.getsize(work) >= insize:
        tx.remove_quietly(work)
        return None
    return tx.commit_output(
        work, filepath, insize, verify='oga', **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_ape(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    mac = resolve_tool('mac')
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(filepath, '.ape', debug=debug, quiet=quiet, **commit)
    if mac:
        out_temp = tx.make_temp('.ape')
        result = _run_command(
            [mac, abspath(work), out_temp, '-c5000'],
            quiet=quiet, debug=debug,
        )
        if result is not None:
            tx.remove_quietly(work)
            work = out_temp
        else:
            tx.remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        tx.remove_quietly(work)
        return None
    return tx.commit_output(
        work, filepath, insize, verify='ape', **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_mp3(
    filepath: str, debug: bool = False, quiet: bool = False,
    ultra: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Lossless MP3 frame packing via mp3packer (not a transcode)."""
    tool = resolve_tool('mp3packer')
    insize = os.path.getsize(filepath)
    work = _copy_with_covers(
        filepath, '.mp3', debug=debug, quiet=quiet, ultra=ultra, **commit
    )
    if tool:
        out_temp = tx.make_temp('.mp3')
        cmd = [tool]
        if ultra:
            cmd.append('-z')
        cmd.extend([abspath(work), out_temp])
        result = _run_command(cmd, quiet=quiet, debug=debug)
        if result is not None:
            tx.remove_quietly(work)
            work = out_temp
        else:
            tx.remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        tx.remove_quietly(work)
        return None
    return tx.commit_output(
        work, filepath, insize, verify='mp3', **tx.commit_kwargs(**commit)
    )


@guard_packer
def pack_ogg(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    tool = resolve_tool('optivorbis')
    insize = os.path.getsize(filepath)
    suffix = '.opus' if filepath.lower().endswith('.opus') else '.ogg'
    work = _copy_with_covers(filepath, suffix, debug=debug, quiet=quiet, **commit)
    if tool:
        out_temp = tx.make_temp(suffix)
        result = _run_command(
            [tool, abspath(work), out_temp], quiet=quiet, debug=debug,
        )
        if result is not None:
            tx.remove_quietly(work)
            work = out_temp
        else:
            tx.remove_quietly(out_temp)
    elif os.path.getsize(work) >= insize:
        tx.remove_quietly(work)
        return None
    return tx.commit_output(
        work, filepath, insize, verify='ogg', **tx.commit_kwargs(**commit)
    )
