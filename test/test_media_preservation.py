import subprocess

import pytest

from filerepack.media import _encode_video, pack_mp4
from filerepack.media_verify import inventory, verify_media_preservation
from filerepack.tools import resolve_tool
from filerepack.validation import validate_options


@pytest.fixture
def movie(tmp_path):
    ffmpeg = resolve_tool('ffmpeg')
    if not ffmpeg or not resolve_tool('ffprobe'):
        pytest.skip('native media readers required')
    path = tmp_path / 'multitrack.mp4'
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=s=32x32:r=5:d=0.6', '-f', 'lavfi', '-i',
                    'sine=frequency=300:duration=0.6', '-f', 'lavfi', '-i',
                    'sine=frequency=500:duration=0.6', '-map', '0', '-map', '1', '-map', '2',
                    '-c:v', 'libx264', '-c:a', 'aac', '-metadata:s:a:0', 'language=eng',
                    '-metadata:s:a:1', 'language=fra', '-metadata', 'title=Preserved title',
                    '-y', str(path)], check=True, capture_output=True)
    return path, ffmpeg


def test_default_remux_retains_all_tracks(movie, tmp_path):
    source, ffmpeg = movie
    target = tmp_path / 'copy.mp4'
    assert _encode_video(ffmpeg, str(source), str(target), False, True, False)
    assert len(inventory(str(target))['streams']) == 3
    assert verify_media_preservation(str(source), str(target), 'remux', True)


def test_dropped_track_refused(movie, tmp_path):
    source, ffmpeg = movie
    target = tmp_path / 'dropped.mp4'
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(source),
                    '-map', '0:v', '-map', '0:a:0', '-c', 'copy', '-y', str(target)],
                   check=True, capture_output=True)
    assert not verify_media_preservation(str(source), str(target), 'remux', False)


def test_shifted_timestamps_refused(movie, tmp_path):
    source, ffmpeg = movie
    target = tmp_path / 'shifted.mp4'
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-itsoffset', '0.2', '-i', str(source),
                    '-copyts', '-map', '0', '-c', 'copy', '-y', str(target)],
                   check=True, capture_output=True)
    assert not verify_media_preservation(str(source), str(target), 'remux', False)


def test_actual_default_packer_never_changes_content(movie):
    source, _ = movie
    result = pack_mp4(str(source), dryrun=True)
    assert result is not None
    assert not result.replaced


def test_subtitles_attachment_chapters_and_track_languages(movie, tmp_path):
    source, ffmpeg = movie
    subtitle, attachment, chapters = (tmp_path / 'subtitle.srt', tmp_path / 'attachment.txt',
                                     tmp_path / 'chapters.ffmeta')
    subtitle.write_text('1\n00:00:00,000 --> 00:00:00,500\nPreserved subtitle\n')
    attachment.write_text('Required attached content')
    chapters.write_text(';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=500\n'
                        'title=Preserved chapter\n')
    bundle, target = tmp_path / 'complete.mkv', tmp_path / 'copy.mkv'
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(source), '-i', str(subtitle),
                    '-i', str(chapters), '-map', '0', '-map', '1', '-map_metadata', '0',
                    '-map_chapters', '2', '-c', 'copy', '-attach', str(attachment),
                    '-metadata:s:t', 'mimetype=text/plain', '-metadata:s:s:0', 'language=deu',
                    '-y', str(bundle)], check=True, capture_output=True)
    assert _encode_video(ffmpeg, str(bundle), str(target), False, True, False, container='mkv')
    assert len(inventory(str(target))['streams']) == 5
    assert len(inventory(str(target))['chapters']) == 1
    assert verify_media_preservation(str(bundle), str(target), 'remux', False)
    from filerepack.media_verify import _tags
    left, right = inventory(str(bundle)), inventory(str(target))
    exact_tags = all(_tags(a.get('tags', {}), True) == _tags(b.get('tags', {}), True)
                     for a, b in zip(left['streams'], right['streams']))
    assert verify_media_preservation(str(bundle), str(target), 'remux', True) is exact_tags
    if not exact_tags:
        # Some FFmpeg versions recompute Matroska DURATION tags. The strict
        # retention request must refuse that otherwise faithful candidate.
        from filerepack.media import _pack_video
        original = bundle.read_bytes()
        assert _pack_video(str(bundle), 'mkv', keep_meta=True, keep_if_larger=False) is None
        assert bundle.read_bytes() == original


@pytest.mark.parametrize('settings', [
    {'video_mode': 'lossy'}, {'video_mode': 'invalid'},
    {'video_mode': 'remux', 'wmv_lossless': True},
])
def test_conflicting_mode_before_writes(settings):
    with pytest.raises(ValueError):
        validate_options(settings)
