# -*- coding: utf-8 -*-

from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from filerepack.covers import (
    _ape_covers, _flac_covers, _mp4_covers, mutagen_available,
    optimize_embedded_covers,
)
from filerepack.models import RepackOptions
from filerepack.repack import _normalize_options, pack_jpg, pack_png


class TestMutagenGuard:
    def test_missing_mutagen_is_noop(self, tmp_path, monkeypatch):
        path = tmp_path / 'a.mp3'
        path.write_bytes(b'ID3' + b'\x00' * 32)
        monkeypatch.setattr(
            'filerepack.covers.mutagen_available', lambda: False,
        )
        assert optimize_embedded_covers(str(path)) is False
        assert path.read_bytes().startswith(b'ID3')

    def test_mutagen_available_matches_import(self):
        try:
            import mutagen  # noqa: F401
            expected = True
        except ImportError:
            expected = False
        assert mutagen_available() is expected

    def test_no_images_skips_covers(self, tmp_path):
        path = tmp_path / 'a.mp3'
        path.write_bytes(b'ID3' + b'\x00' * 32)
        with patch('filerepack.covers.mutagen_available', return_value=True):
            with patch('filerepack.covers._mp3_covers') as mp3:
                assert optimize_embedded_covers(
                    str(path), {'pack_images': False},
                ) is False
        mp3.assert_not_called()


class TestCoverRoundTrip:
    def test_mp3_apic_rewritten_other_frames_kept(self, tmp_path):
        pytest.importorskip('mutagen')
        from mutagen.id3 import ID3, APIC, TIT2

        path = tmp_path / 'song.mp3'
        # Minimal MPEG frame so mutagen will save.
        path.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 64)
        tags = ID3()
        tags.add(TIT2(encoding=3, text=['Keep me']))
        tags.add(APIC(
            encoding=3, mime='image/jpeg', type=3, desc='cover',
            data=b'\xff\xd8\xff' + b'\x00' * 80,
        ))
        tags.save(str(path))

        packed = b'\xff\xd8\xff' + b'\x01' * 8

        def fake_picture(data, mime, options):
            return packed

        with patch('filerepack.covers._pack_picture', side_effect=fake_picture):
            assert optimize_embedded_covers(str(path)) is True
        saved = ID3(str(path))
        assert saved.getall('TIT2')[0].text == ['Keep me']
        assert bytes(saved.getall('APIC')[0].data) == packed

    def test_flac_pictures_rewritten(self):
        pic = SimpleNamespace(data=b'\xff\xd8' + b'\x00' * 40, mime='image/jpeg')
        saved = []

        class FakeFlac:
            def __init__(self, path):
                self.pictures = [pic]

            def clear_pictures(self):
                self.pictures = []

            def add_picture(self, item):
                self.pictures.append(item)

            def save(self):
                saved.append(bytes(pic.data))

        flac_mod = ModuleType('mutagen.flac')
        flac_mod.FLAC = FakeFlac  # type: ignore[attr-defined]
        mutagen_mod = ModuleType('mutagen')
        with patch.dict(
            'sys.modules', {'mutagen': mutagen_mod, 'mutagen.flac': flac_mod},
        ):
            with patch(
                'filerepack.covers._pack_picture', return_value=b'smalljpg',
            ):
                assert _flac_covers('a.flac', None) is True
        assert saved == [b'smalljpg']

    def test_mp4_covr_rewritten(self):
        class FakeCover(bytes):
            imageformat = 13

        cover = FakeCover(b'\xff\xd8' + b'\x00' * 40)
        saved = []

        class MP4Cover(bytes):
            FORMAT_JPEG = 13
            FORMAT_PNG = 14

            def __new__(cls, data, imageformat=None):
                obj = bytes.__new__(cls, data)
                obj.imageformat = imageformat
                return obj

        class FakeMP4:
            def __init__(self, path):
                self._tags = {'covr': [cover]}

            def get(self, key):
                return self._tags.get(key)

            def __setitem__(self, key, value):
                self._tags[key] = value

            def save(self):
                saved.append(self._tags['covr'][0])

        mp4_mod = ModuleType('mutagen.mp4')
        mp4_mod.MP4 = FakeMP4  # type: ignore[attr-defined]
        mp4_mod.MP4Cover = MP4Cover  # type: ignore[attr-defined]
        mutagen_mod = ModuleType('mutagen')
        with patch.dict(
            'sys.modules', {'mutagen': mutagen_mod, 'mutagen.mp4': mp4_mod},
        ):
            with patch(
                'filerepack.covers._pack_picture', return_value=b'smalljpg',
            ):
                assert _mp4_covers('a.m4a', None) is True
        assert saved[0] == b'smalljpg'

    def test_ape_cover_art_rewritten(self):
        blob = b'cover.jpg\x00' + b'\xff\xd8' + b'\x00' * 40
        saved = []

        class FakeAPE:
            def __init__(self, path):
                self._tags = {
                    'Cover Art (Front)': SimpleNamespace(value=blob),
                }

            def keys(self):
                return list(self._tags)

            def __getitem__(self, key):
                return self._tags[key]

            def __setitem__(self, key, value):
                self._tags[key] = value

            def save(self, path=None):
                saved.append(self._tags['Cover Art (Front)'])

        ape_mod = ModuleType('mutagen.apev2')
        ape_mod.APEv2 = FakeAPE  # type: ignore[attr-defined]
        ape_mod.APENoHeaderError = type(  # type: ignore[attr-defined]
            'APENoHeaderError', (Exception,), {},
        )
        mutagen_mod = ModuleType('mutagen')
        with patch.dict(
            'sys.modules', {'mutagen': mutagen_mod, 'mutagen.apev2': ape_mod},
        ):
            with patch(
                'filerepack.covers._pack_picture', return_value=b'\xff\xd8x',
            ):
                assert _ape_covers('a.ape', None) is True
        assert saved[0].endswith(b'\xff\xd8x')


class TestJpegtranKeepMeta:
    def test_keep_meta_omits_strip(self, tmp_path):
        path = tmp_path / 'a.jpg'
        path.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch('filerepack.repack.resolve_tool') as resolve:
            resolve.side_effect = lambda key: (
                '/bin/jpegoptim' if key == 'jpegoptim' else None
            )
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_jpg(
                        str(path), keep_meta=True, dryrun=True,
                        keep_if_larger=False,
                    )
        jpegoptim = [c for c in calls if c and c[0] == '/bin/jpegoptim'][0]
        assert '--strip-all' not in jpegoptim

    def test_default_strips(self, tmp_path):
        path = tmp_path / 'a.jpg'
        path.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch('filerepack.repack.resolve_tool') as resolve:
            resolve.side_effect = lambda key: (
                '/bin/jpegoptim' if key == 'jpegoptim' else None
            )
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_jpg(str(path), dryrun=True, keep_if_larger=False)
        jpegoptim = [c for c in calls if c and c[0] == '/bin/jpegoptim'][0]
        assert '--strip-all' in jpegoptim

    def test_jpegtran_missing_falls_back(self, tmp_path):
        path = tmp_path / 'a.jpg'
        path.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch('filerepack.repack.resolve_tool') as resolve:
            resolve.side_effect = lambda key: (
                '/bin/jpegoptim' if key == 'jpegoptim' else None
            )
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_jpg(str(path), dryrun=True, keep_if_larger=False)
        assert any(c[0] == '/bin/jpegoptim' for c in calls)
        assert all('jpegtran' not in c[0] for c in calls)

    def test_jpegtran_then_jpegoptim(self, tmp_path):
        path = tmp_path / 'a.jpg'
        path.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            if cmd and cmd[0] == '/bin/jpegtran' and '-outfile' in cmd:
                out = cmd[cmd.index('-outfile') + 1]
                with open(out, 'wb') as fh:
                    fh.write(b'\xff\xd8\xff')
            return MagicMock(returncode=0)

        def resolve(key):
            return {
                'jpegtran': '/bin/jpegtran',
                'jpegoptim': '/bin/jpegoptim',
            }.get(key)

        with patch('filerepack.repack.resolve_tool', side_effect=resolve):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_jpg(str(path), dryrun=True, keep_if_larger=False)
        assert any(c and c[0] == '/bin/jpegtran' for c in calls)
        assert any(c and c[0] == '/bin/jpegoptim' for c in calls)
        jpegtran = [c for c in calls if c and c[0] == '/bin/jpegtran'][0]
        assert jpegtran[jpegtran.index('-copy') + 1] == 'none'

    def test_keep_meta_jpegtran_copy_all(self, tmp_path):
        path = tmp_path / 'a.jpg'
        path.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            if cmd and cmd[0] == '/bin/jpegtran' and '-outfile' in cmd:
                out = cmd[cmd.index('-outfile') + 1]
                with open(out, 'wb') as fh:
                    fh.write(b'\xff\xd8\xff')
            return MagicMock(returncode=0)

        def resolve(key):
            return {
                'jpegtran': '/bin/jpegtran',
                'jpegoptim': '/bin/jpegoptim',
            }.get(key)

        with patch('filerepack.repack.resolve_tool', side_effect=resolve):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_jpg(
                        str(path), keep_meta=True, dryrun=True,
                        keep_if_larger=False,
                    )
        jpegtran = [c for c in calls if c and c[0] == '/bin/jpegtran'][0]
        assert jpegtran[jpegtran.index('-copy') + 1] == 'all'
        jpegoptim = [c for c in calls if c and c[0] == '/bin/jpegoptim'][0]
        assert '--strip-all' not in jpegoptim

    def test_ultra_png_tries_zopflipng(self, tmp_path):
        path = tmp_path / 'a.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            dest = cmd[-1] if cmd else None
            if dest and dest.endswith('.png') and 'zopflipng' in cmd[0]:
                with open(dest, 'wb') as fh:
                    fh.write(b'\x89PNG\r\n\x1a\n')
            return MagicMock(returncode=0)

        def resolve(key):
            return {
                'oxipng': '/bin/oxipng',
                'zopflipng': '/bin/zopflipng',
            }.get(key)

        with patch('filerepack.repack.resolve_tool', side_effect=resolve):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_png(
                        str(path), ultra=True, dryrun=True, keep_if_larger=False,
                    )
        assert any(c and c[0] == '/bin/zopflipng' for c in calls)
        assert any(c and c[0] == '/bin/oxipng' for c in calls)

    def test_ultra_without_zopflipng_uses_oxipng(self, tmp_path):
        path = tmp_path / 'a.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch('filerepack.repack.resolve_tool') as resolve:
            resolve.side_effect = lambda key: (
                '/bin/oxipng' if key == 'oxipng' else None
            )
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_png(
                        str(path), ultra=True, dryrun=True, keep_if_larger=False,
                    )
        assert any(c and c[0] == '/bin/oxipng' for c in calls)
        assert all(c[0] != '/bin/zopflipng' for c in calls)

    def test_keep_meta_oxipng_omits_strip(self, tmp_path):
        path = tmp_path / 'a.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 32)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch('filerepack.repack.resolve_tool') as resolve:
            resolve.side_effect = lambda key: (
                '/bin/oxipng' if key == 'oxipng' else None
            )
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                with patch('filerepack.repack.verify_output', return_value=True):
                    pack_png(
                        str(path), keep_meta=True, dryrun=True,
                        keep_if_larger=False,
                    )
        oxipng = [c for c in calls if c and c[0] == '/bin/oxipng'][0]
        assert '--strip' not in oxipng

    def test_keep_meta_option_normalized(self):
        opts = _normalize_options(RepackOptions(keep_meta=True))
        assert opts['keep_meta'] is True
        assert _normalize_options(RepackOptions()).get('keep_meta') is False
