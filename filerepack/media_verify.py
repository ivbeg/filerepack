"""Independent FFprobe inventory and FFmpeg decoded-content qualification."""

import hashlib
import json
from fractions import Fraction
from typing import Any, Dict, Optional, cast

from .commands import capture_bytes, consume_command
from .tools import resolve_tool


def inventory(path: str) -> Dict[str, Any]:
    probe = resolve_tool('ffprobe')
    if not probe:
        raise ValueError('ffprobe is required for complete stream inventory')
    raw = capture_bytes([probe, '-v', 'error', '-show_streams', '-show_chapters', '-show_format',
                         '-show_data_hash', 'sha256', '-of', 'json', path], max_output=1024 * 1024)
    if raw is None:
        raise ValueError('bounded media inventory unavailable')
    value = json.loads(raw)
    if not value.get('streams'):
        raise ValueError('empty media inventory')
    return cast(Dict[str, Any], value)


def _tags(value: Dict[str, Any], keep_meta: bool) -> Dict[str, Any]:
    return {key.lower(): item for key, item in value.items()
            if key.lower() != 'encoder' and
            (keep_meta or key.lower() in ('language', 'title', 'rotate', 'filename', 'mimetype'))}


def _stream(value: Dict[str, Any], mode: str, keep_meta: bool) -> Dict[str, Any]:
    keys = ('codec_type', 'width', 'height', 'sample_aspect_ratio', 'color_range',
            'color_space', 'color_transfer', 'color_primaries', 'chroma_location',
            'sample_rate', 'channels', 'channel_layout', 'disposition', 'side_data_list')
    result = {key: value[key] for key in keys if key in value}
    for key in ('r_frame_rate', 'avg_frame_rate'):
        if value.get(key) and value[key] != '0/0':
            result[key] = Fraction(value[key])
    if mode != 'lossy' or value['codec_type'] != 'video':
        result['pix_fmt'] = value.get('pix_fmt')
    if mode == 'remux' or value['codec_type'] != 'video':
        result['codec_name'] = value.get('codec_name')
        result['extradata_hash'] = value.get('extradata_hash')
    result['tags'] = _tags(value.get('tags', {}), keep_meta)
    return result


def _chapter(value: Dict[str, Any]) -> Dict[str, Any]:
    timebase = Fraction(value['time_base'])
    return {'start': int(value['start']) * timebase, 'end': int(value['end']) * timebase,
            'tags': value.get('tags', {})}


def _timed_rows(cmd: list, timebase: Fraction) -> Optional[str]:
    checksum, pending = hashlib.sha256(), bytearray()
    timing = ('pts', 'dts', 'duration', 'best_effort_timestamp', 'pkt_duration')

    def consume(block: bytes) -> None:
        pending.extend(block)
        while b'\n' in pending:
            line, _, tail = pending.partition(b'\n')
            pending[:] = tail
            fields = {}
            for part in line.decode('ascii').split('|'):
                key, separator, value = part.partition('=')
                if separator:
                    fields[key] = (str(int(value) * timebase)
                                   if key in timing and value != 'N/A' else value)
            checksum.update(json.dumps(fields, sort_keys=True).encode() + b'\n')
        if len(pending) > 65536:
            raise ValueError('Media timing row exceeds bounded profile')

    return checksum.hexdigest() if consume_command(cmd, consume) and not pending else None


def _packets(path: str, stream: Dict[str, Any]) -> Optional[str]:
    tool = resolve_tool('ffprobe')
    if not tool:
        return None
    # Packet data hashes preserve subtitles, attachments and copied compressed
    # tracks without copying packet bodies into the Python process.
    cmd = [tool, '-v', 'error', '-select_streams', str(stream['index']), '-show_packets',
           '-show_data_hash', 'sha256', '-show_entries', 'packet=pts,dts,duration,size,data_hash',
           '-of', 'compact=p=0:nk=0', path]
    return _timed_rows(cmd, Fraction(stream['time_base']))


def _timing(path: str, stream: Dict[str, Any]) -> Optional[str]:
    tool = resolve_tool('ffprobe')
    if not tool:
        return None
    cmd = [tool, '-v', 'error', '-select_streams', str(stream['index']), '-show_frames',
           '-show_entries',
           'frame=best_effort_timestamp,duration,pkt_duration,repeat_pict,nb_samples',
           '-of', 'compact=p=0:nk=0', path]
    return _timed_rows(cmd, Fraction(stream['time_base']))


def _frames(path: str, stream: Dict[str, Any]) -> Optional[str]:
    tool = resolve_tool('ffmpeg')
    if not tool:
        return None
    cmd = [tool, '-nostdin', '-v', 'error', '-xerror', '-i', path,
           '-map', '0:' + str(stream['index'])]
    if stream['codec_type'] == 'video':
        cmd += ['-c:v', 'rawvideo', '-pix_fmt', stream['pix_fmt']]
    else:
        floating = stream.get('sample_fmt', '').startswith(('flt', 'dbl'))
        codec = 'pcm_f64le' if floating else 'pcm_s32le'
        cmd += ['-c:a', codec]
    cmd += ['-f', 'hash', '-hash', 'sha256', '-']
    raw = capture_bytes(cmd, max_output=1024)
    return raw.decode('ascii').strip() if raw else None


def verify_media_preservation(source: str, candidate: str, mode: str, keep_meta: bool) -> bool:
    try:
        left, right = inventory(source), inventory(candidate)
        a, b = left['streams'], right['streams']
        if len(a) != len(b) or [_stream(x, mode, keep_meta) for x in a] != [
            _stream(x, mode, keep_meta) for x in b
        ]:
            return False
        if [_chapter(x) for x in left.get('chapters', [])] != [
            _chapter(x) for x in right.get('chapters', [])
        ]:
            return False
        if _tags(left['format'].get('tags', {}), keep_meta) != _tags(
            right['format'].get('tags', {}), keep_meta
        ):
            return False
        for x, y in zip(a, b):
            kind = x['codec_type']
            if kind == 'video' and mode != 'remux':
                first_timing, second_timing = _timing(source, x), _timing(candidate, y)
                if first_timing is None or first_timing != second_timing:
                    return False
            if mode == 'lossy' and kind == 'video':
                continue
            decode = mode == 'lossless' and kind in ('audio', 'video')
            first = _frames(source, x) if decode else _packets(source, x)
            second = _frames(candidate, y) if decode else _packets(candidate, y)
            if first is None or first != second:
                return False
        return True
    except (ValueError, OSError, KeyError, TypeError):
        return False
