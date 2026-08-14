# -*- coding: utf-8 -*-

import pytest
from unittest.mock import patch

from filerepack.repack import (
    _PACKERS, _dispatch_packer, build_gs_pdf_cmd, jpeg_quality_to_qfactor,
    normalize_pdf_profile, pack_pdf,
)
from filerepack.codecs import pack_ai
from filerepack.consts import DEFAULT_LOSSY_PDF_PROFILE, PDF_PROFILES


def _tools(gs='/usr/bin/gs', qpdf='/usr/bin/qpdf'):
    mapping = {'gs': gs, 'qpdf': qpdf}

    def resolve(name):
        return mapping.get(name)

    return resolve


class TestPdfHelpers:
    def test_normalize_none(self):
        assert normalize_pdf_profile(None) is None

    def test_normalize_aliases(self):
        assert normalize_pdf_profile('ebook') == 'ebook'
        assert normalize_pdf_profile('/ebook') == 'ebook'
        assert normalize_pdf_profile('Prepress') == 'prepress'

    def test_normalize_unknown(self):
        with pytest.raises(ValueError, match='Unknown PDF profile'):
            normalize_pdf_profile('ultra')

    def test_profiles_tuple(self):
        assert DEFAULT_LOSSY_PDF_PROFILE == 'ebook'
        assert PDF_PROFILES == (
            'screen', 'ebook', 'printer', 'prepress', 'default',
        )

    def test_qfactor_bounds(self):
        assert jpeg_quality_to_qfactor(100) == 0.15
        assert jpeg_quality_to_qfactor(1) == 2.4
        assert jpeg_quality_to_qfactor(75) == round(
            0.15 + 25 * 2.25 / 99.0, 3
        )

    def test_gs_cmd_default_ebook(self):
        cmd = build_gs_pdf_cmd('/gs', 'in.pdf', 'out.pdf')
        assert '-dPDFSETTINGS=/ebook' in cmd
        assert cmd[-1] == 'in.pdf'
        assert '-c' not in cmd

    def test_gs_cmd_explicit_profile(self):
        cmd = build_gs_pdf_cmd(
            '/gs', 'in.pdf', 'out.pdf', profile='prepress',
        )
        assert '-dPDFSETTINGS=/prepress' in cmd

    def test_gs_cmd_jpeg_quality(self):
        cmd = build_gs_pdf_cmd(
            '/gs', 'in.pdf', 'out.pdf', profile='printer', jpeg_quality=75,
        )
        qfactor = jpeg_quality_to_qfactor(75)
        assert '-dPDFSETTINGS=/printer' in cmd
        assert '-dColorImageFilter=/DCTEncode' in cmd
        assert '-dGrayImageFilter=/DCTEncode' in cmd
        assert any('setdistillerparams' in arg for arg in cmd)
        assert any(f'/QFactor {qfactor}' in arg for arg in cmd)
        assert cmd[-2] == '-f'
        assert cmd[-1] == 'in.pdf'


class TestPackPdf:
    def test_lossless_uses_qpdf(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return None

        with patch('filerepack.repack.resolve_tool', side_effect=_tools()):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                pack_pdf(str(path))
        assert len(calls) == 1
        assert calls[0][0] == '/usr/bin/qpdf'
        assert '--compress-streams=y' in calls[0]
        assert '-dPDFSETTINGS=/ebook' not in calls[0]

    def test_lossy_defaults_to_ebook(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return None

        with patch('filerepack.repack.resolve_tool', side_effect=_tools()):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                pack_pdf(str(path), lossy=True)
        assert calls[0][0] == '/usr/bin/gs'
        assert '-dPDFSETTINGS=/ebook' in calls[0]

    def test_profile_implies_ghostscript(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return None

        with patch('filerepack.repack.resolve_tool', side_effect=_tools()):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                pack_pdf(str(path), pdf_profile='prepress')
        assert calls[0][0] == '/usr/bin/gs'
        assert '-dPDFSETTINGS=/prepress' in calls[0]

    def test_jpeg_quality_implies_ghostscript(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return None

        with patch('filerepack.repack.resolve_tool', side_effect=_tools()):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                pack_pdf(str(path), jpeg_quality=85)
        assert calls[0][0] == '/usr/bin/gs'
        assert '-dPDFSETTINGS=/ebook' in calls[0]
        assert '-dColorImageFilter=/DCTEncode' in calls[0]
        assert any('setdistillerparams' in arg for arg in calls[0])

    def test_unknown_profile_skips_tools(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        with patch('filerepack.repack.resolve_tool', side_effect=_tools()):
            with patch('filerepack.repack._run_command') as run:
                assert pack_pdf(str(path), pdf_profile='ultra') is None
                run.assert_not_called()
        assert path.read_bytes().startswith(b'%PDF')

    def test_lossy_falls_back_to_qpdf(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return None

        with patch(
            'filerepack.repack.resolve_tool',
            side_effect=_tools(gs=None),
        ):
            with patch('filerepack.repack._run_command', side_effect=fake_run):
                pack_pdf(str(path), lossy=True)
        assert len(calls) == 1
        assert calls[0][0] == '/usr/bin/qpdf'

    def test_missing_tools(self, tmp_path):
        path = tmp_path / 'a.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        with patch(
            'filerepack.repack.resolve_tool',
            side_effect=_tools(gs=None, qpdf=None),
        ):
            assert pack_pdf(str(path), lossy=True) is None


class TestPdfDispatch:
    def test_packer_extra_keys(self):
        assert _PACKERS['pdf'].extra['pdf_profile'] == 'pdf_profile'
        assert _PACKERS['pdf'].extra['jpeg_quality'] == 'jpeg_quality'
        assert _PACKERS['ai'].extra['pdf_profile'] == 'pdf_profile'
        assert _PACKERS['ai'].extra['jpeg_quality'] == 'jpeg_quality'

    def test_dispatch_forwards_pdf_options(self):
        with patch.object(_PACKERS['pdf'], 'func', return_value=None) as mocked:
            _dispatch_packer('pdf', 'a.pdf', {
                'pdf_profile': 'screen',
                'jpeg_quality': 70,
                'lossy': False,
            })
        assert mocked.call_args.kwargs['pdf_profile'] == 'screen'
        assert mocked.call_args.kwargs['jpeg_quality'] == 70
        assert mocked.call_args.kwargs['lossy'] is False

    def test_pack_ai_forwards_pdf_options(self, tmp_path):
        path = tmp_path / 'logo.ai'
        path.write_bytes(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n')
        with patch('filerepack.repack.pack_pdf', return_value=None) as mocked:
            pack_ai(
                str(path), lossy=True, pdf_profile='screen', jpeg_quality=70,
            )
        kwargs = mocked.call_args.kwargs
        assert kwargs['pdf_profile'] == 'screen'
        assert kwargs['jpeg_quality'] == 70
        assert kwargs['lossy'] is True
