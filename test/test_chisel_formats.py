# -*- coding: utf-8 -*-

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from filerepack.codecs import pack_bmp, pack_oga, pack_ogg
from filerepack.pdf_streams import _pdf_is_locked, rebuild_pdf_images
from filerepack.repack import _PACKERS, _dispatch_packer, pack_pdf, pack_svg


class TestRasterMissingTool:
    def test_bmp_missing_convert(self, tmp_path):
        path = tmp_path / 'a.bmp'
        path.write_bytes(b'BM' + b'\x00' * 32)
        with patch('filerepack.codecs.resolve_tool', return_value=None):
            assert pack_bmp(str(path)) is None

    def test_no_images_skips_bmp(self, tmp_path):
        path = tmp_path / 'a.bmp'
        path.write_bytes(b'BM' + b'\x00' * 32)
        assert 'bmp' in _PACKERS
        result = _dispatch_packer('bmp', str(path), {'pack_images': False})
        assert result is None


class TestOptivorbis:
    def test_missing_tool_leaves_file(self, tmp_path):
        path = tmp_path / 'a.ogg'
        original = b'OggS' + b'\x00' * 32
        path.write_bytes(original)
        with patch('filerepack.codecs.resolve_tool', return_value=None):
            with patch('filerepack.covers.optimize_embedded_covers', return_value=False):
                assert pack_ogg(str(path)) is None
        assert path.read_bytes() == original


class TestPdfStreams:
    def test_no_pikepdf_qpdf_only(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n' + b'1' * 40)
        calls = []

        def fake_run(cmd, quiet=False, debug=False, cwd=None):
            calls.append(cmd)
            if cmd and 'qpdf' in cmd[0]:
                with open(cmd[-1], 'wb') as fh:
                    fh.write(b'%PDF-1.5\n')
            return MagicMock(returncode=0)

        with patch('filerepack.pdf_streams.pikepdf_available', return_value=False):
            with patch(
                'filerepack.pdf_streams.rebuild_pdf_images', return_value=False,
            ):
                with patch('filerepack.repack.resolve_tool') as resolve:
                    resolve.side_effect = lambda k: (
                        '/bin/qpdf' if k == 'qpdf' else None
                    )
                    with patch(
                        'filerepack.repack._run_command', side_effect=fake_run,
                    ):
                        with patch(
                            'filerepack.repack.verify_output', return_value=True,
                        ):
                            pack_pdf(str(path), dryrun=True, keep_if_larger=False)
        assert any('qpdf' in c[0] for c in calls)

    def test_lossy_skips_stream_walk(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        with patch('filerepack.pdf_streams.rebuild_pdf_images') as walk:
            with patch('filerepack.repack.resolve_tool') as resolve:
                resolve.side_effect = lambda k: (
                    '/bin/gs' if k == 'gs' else '/bin/qpdf' if k == 'qpdf' else None
                )
                with patch(
                    'filerepack.repack._run_command',
                    return_value=MagicMock(returncode=0),
                ):
                    with patch(
                        'filerepack.repack.verify_output', return_value=True,
                    ):
                        pack_pdf(
                            str(path), lossy=True, dryrun=True,
                            keep_if_larger=False,
                        )
        walk.assert_not_called()

    def test_rebuild_skips_without_pikepdf(self, tmp_path):
        src = tmp_path / 'a.pdf'
        dest = tmp_path / 'b.pdf'
        src.write_bytes(b'%PDF-1.4\n')
        with patch.dict('sys.modules', {'pikepdf': None}):
            assert rebuild_pdf_images(str(src), str(dest)) is False

    def test_encrypted_pdf_is_locked(self):
        pdf = SimpleNamespace(is_encrypted=True, trailer={}, Root={})
        assert _pdf_is_locked(pdf) is True

    def test_encrypt_dict_is_locked(self):
        pdf = SimpleNamespace(
            is_encrypted=False, trailer={'/Encrypt': {}}, Root={},
        )
        assert _pdf_is_locked(pdf) is True

    def test_perms_is_locked(self):
        pdf = SimpleNamespace(
            is_encrypted=False, trailer={}, Root={'/Perms': {}},
        )
        assert _pdf_is_locked(pdf) is True

    def test_sigflags_is_locked(self):
        pdf = SimpleNamespace(
            is_encrypted=False, trailer={},
            Root={'/AcroForm': {'/SigFlags': 3}},
        )
        assert _pdf_is_locked(pdf) is True

    def test_unsigned_unlocked(self):
        pdf = SimpleNamespace(
            is_encrypted=False, trailer={},
            Root={'/AcroForm': {'/SigFlags': 0}},
        )
        assert _pdf_is_locked(pdf) is False

    def test_rebuild_skips_encrypted(self, tmp_path):
        src = tmp_path / 'a.pdf'
        dest = tmp_path / 'b.pdf'
        src.write_bytes(b'%PDF-1.4\n')

        class LockedPdf:
            is_encrypted = True
            trailer = {}
            Root = {}
            pages = []

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def save(self, path):
                raise AssertionError('locked PDFs must not be saved')

        class Name(str):
            DCTDecode = '/DCTDecode'
            JPXDecode = '/JPXDecode'

        fake = ModuleType('pikepdf')
        fake.open = lambda *_a, **_k: LockedPdf()  # type: ignore[attr-defined]
        fake.Name = Name
        fake.Array = list
        with patch.dict(sys.modules, {'pikepdf': fake}):
            assert rebuild_pdf_images(str(src), str(dest)) is False
        assert not dest.exists()

    def test_rebuild_injects_smaller_jpeg(self, tmp_path):
        src = tmp_path / 'a.pdf'
        dest = tmp_path / 'b.pdf'
        src.write_bytes(b'%PDF-1.4\n' + b'0' * 40)
        written = {}

        class FakeImage:
            def get(self, key):
                return '/DCTDecode' if key == '/Filter' else None

            def read_raw_bytes(self):
                return b'\xff\xd8' + b'\x00' * 80

            def write(self, packed, filter=None):
                written['data'] = packed
                written['filter'] = filter

        class FakePage:
            images = {'Im0': FakeImage()}

        class FakePdf:
            is_encrypted = False
            trailer = {}
            Root = {}
            pages = [FakePage()]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def save(self, path):
                with open(path, 'wb') as fh:
                    fh.write(b'%PDF-1.4 rebuilt\n')

        class Name(str):
            DCTDecode = '/DCTDecode'
            JPXDecode = '/JPXDecode'

        fake = ModuleType('pikepdf')
        fake.open = lambda *_a, **_k: FakePdf()  # type: ignore[attr-defined]
        fake.Name = Name
        fake.Array = list
        packed = b'\xff\xd8small'
        with patch.dict(sys.modules, {'pikepdf': fake}):
            with patch(
                'filerepack.pdf_streams._pack_stream_bytes', return_value=packed,
            ):
                assert rebuild_pdf_images(str(src), str(dest)) is True
        assert written['data'] == packed
        assert dest.read_bytes().startswith(b'%PDF-1.4 rebuilt')


class TestSvgFallback:
    def test_missing_svgo_scour_uses_xml(self, tmp_path):
        path = tmp_path / 'a.svg'
        path.write_text(
            '<?xml version="1.0"?>\n<svg>\n  <g></g>\n</svg>\n',
            encoding='utf-8',
        )
        with patch('filerepack.repack.resolve_tool', return_value=None):
            with patch('filerepack.markup.pack_xml') as xml_pack:
                xml_pack.return_value = None
                pack_svg(str(path))
                xml_pack.assert_called_once()
                assert xml_pack.call_args[0][0] == str(path)


class TestOgaRouting:
    def test_vorbis_oga_uses_optivorbis_path(self, tmp_path):
        path = tmp_path / 'a.oga'
        path.write_bytes(b'OggS' + b'\x00' * 32)
        with patch('filerepack.codecs.resolve_tool', return_value='/bin/ffmpeg'):
            with patch(
                'filerepack.codecs._probe_audio_codec', return_value='vorbis',
            ):
                with patch('filerepack.codecs.pack_ogg') as ogg:
                    ogg.return_value = None
                    pack_oga(str(path))
        ogg.assert_called_once()

    def test_flac_oga_does_not_call_pack_ogg(self, tmp_path):
        path = tmp_path / 'a.oga'
        path.write_bytes(b'OggS' + b'\x00' * 32)
        with patch('filerepack.codecs.resolve_tool', return_value='/bin/ffmpeg'):
            with patch(
                'filerepack.codecs._probe_audio_codec', return_value='flac',
            ):
                with patch('filerepack.codecs.pack_ogg') as ogg:
                    with patch(
                        'filerepack.covers.optimize_embedded_covers',
                        return_value=False,
                    ):
                        with patch(
                            'filerepack.codecs._pack_ffmpeg_audio',
                            return_value=None,
                        ):
                            pack_oga(
                                str(path), dryrun=True, keep_if_larger=False,
                            )
        ogg.assert_not_called()
