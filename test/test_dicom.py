# -*- coding: utf-8 -*-

import os
from unittest.mock import patch

from filerepack.codecs import pack_dcm
from filerepack.dicom import (
    TS_EXPLICIT_VR_BE, TS_IMPLICIT_VR_LE, TS_RLE_LOSSLESS,
    dicom_is_packable, has_dicm_magic,
)
from filerepack.formats import (
    filename_exts, identify_filename, is_supported_filename, matches_ext_filter,
)
from filerepack.repack import _dispatch_packer
from filerepack.utils import verify_output

from test.dicom_fixtures import (
    TS_JPEG_BASELINE, build_dicom, encoder_fixture,
)


class TestIdentifyDicom:
    def test_dcm_is_standalone(self):
        kind = identify_filename('scan.dcm')
        assert kind is not None
        assert kind.family == 'standalone'
        assert kind.packer == 'dcm'
        assert is_supported_filename('scan.dcm')

    def test_aliases(self):
        for name in ('study.dicom', 'image.dic', 'SCAN.DCM'):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'standalone'
            assert kind.packer == 'dcm'

    def test_include_ext_dcm_matches_dicom(self):
        assert matches_ext_filter('scan.dcm', ['dcm'])
        assert matches_ext_filter('study.dicom', ['dcm'])
        assert 'dcm' in filename_exts('study.dicom')
        assert matches_ext_filter('scan.dcm', ['dicom']) is False

    def test_exclude_ext_dcm(self):
        from filerepack.formats import excluded_by_ext_filter
        assert excluded_by_ext_filter('scan.dcm', ['dcm'])
        assert excluded_by_ext_filter('study.dicom', ['dcm'])


class TestVerifyDicom:
    def test_accepts_dicm_magic(self, tmp_path):
        path = tmp_path / 'a.dcm'
        path.write_bytes(b'\x00' * 128 + b'DICM' + b'\x00' * 8)
        assert verify_output(str(path), 'dcm')
        assert verify_output(str(path), 'dicom')
        assert has_dicm_magic(str(path))

    def test_rejects_missing_magic(self, tmp_path):
        path = tmp_path / 'a.dcm'
        path.write_bytes(b'\x00' * 132)
        assert not verify_output(str(path), 'dcm')
        assert not has_dicm_magic(str(path))

    def test_rejects_short_file(self, tmp_path):
        path = tmp_path / 'a.dcm'
        path.write_bytes(b'DICM')
        assert not verify_output(str(path), 'dcm')


class TestDicomSafetyGate:
    def test_explicit_le_with_pixels(self, tmp_path):
        path = tmp_path / 'ok.dcm'
        path.write_bytes(build_dicom())
        assert dicom_is_packable(str(path))

    def test_implicit_le(self, tmp_path):
        path = tmp_path / 'ok.dcm'
        path.write_bytes(build_dicom(
            transfer_syntax=TS_IMPLICIT_VR_LE, implicit_dataset=True,
        ))
        assert dicom_is_packable(str(path))

    def test_explicit_be(self, tmp_path):
        path = tmp_path / 'ok.dcm'
        path.write_bytes(build_dicom(
            transfer_syntax=TS_EXPLICIT_VR_BE, endian='>',
        ))
        assert dicom_is_packable(str(path))

    def test_rle_lossless(self, tmp_path):
        path = tmp_path / 'ok.dcm'
        path.write_bytes(build_dicom(transfer_syntax=TS_RLE_LOSSLESS))
        assert dicom_is_packable(str(path))

    def test_missing_dicm(self, tmp_path):
        path = tmp_path / 'bad.dcm'
        path.write_bytes(b'\x00' * 200)
        assert not dicom_is_packable(str(path))

    def test_jpeg_transfer_syntax(self, tmp_path):
        path = tmp_path / 'jpeg.dcm'
        path.write_bytes(build_dicom(transfer_syntax=TS_JPEG_BASELINE))
        assert not dicom_is_packable(str(path))

    def test_no_pixel_data(self, tmp_path):
        path = tmp_path / 'sr.dcm'
        path.write_bytes(build_dicom(pixel_data=None))
        assert not dicom_is_packable(str(path))

    def test_digital_signatures(self, tmp_path):
        path = tmp_path / 'signed.dcm'
        path.write_bytes(build_dicom(signatures=True))
        assert not dicom_is_packable(str(path))

    def test_truncated_file_meta(self, tmp_path):
        path = tmp_path / 'trunc.dcm'
        path.write_bytes(b'\x00' * 128 + b'DICM' + b'\x00\x02')
        assert not dicom_is_packable(str(path))

    def test_undefined_pixel_data_tag(self, tmp_path):
        pix = b'\xe0\x7f\x10\x00OW\x00\x00\xff\xff\xff\xff'
        path = tmp_path / 'rle.dcm'
        path.write_bytes(build_dicom(
            transfer_syntax=TS_RLE_LOSSLESS,
            pixel_data=None,
            extra_dataset=[pix],
        ))
        assert dicom_is_packable(str(path))

    def test_undefined_sq_is_skipped(self, tmp_path):
        item = (
            b'\xfe\xff\x00\xe0\x04\x00\x00\x00abcd'
            b'\xfe\xff\xdd\xe0\x00\x00\x00\x00'
        )
        sq = b'\x08\x00\x11\x11SQ\x00\x00\xff\xff\xff\xff' + item
        path = tmp_path / 'seq.dcm'
        path.write_bytes(build_dicom(extra_dataset=[sq]))
        assert dicom_is_packable(str(path))


class TestPackDcm:
    def test_missing_tools_returns_none(self, tmp_path, monkeypatch):
        path = tmp_path / 'scan.dcm'
        path.write_bytes(build_dicom())
        original = path.read_bytes()
        monkeypatch.setattr('filerepack.codecs.resolve_tool', lambda key: None)
        assert pack_dcm(str(path)) is None
        assert path.read_bytes() == original

    def test_skip_before_encoder_when_unsafe(self, tmp_path, monkeypatch):
        path = tmp_path / 'jpeg.dcm'
        path.write_bytes(build_dicom(transfer_syntax=TS_JPEG_BASELINE))
        called = []

        def fake_resolve(key):
            return '/usr/bin/gdcmconv' if key == 'gdcmconv' else None

        monkeypatch.setattr('filerepack.codecs.resolve_tool', fake_resolve)
        with patch('filerepack.repack._run_command', side_effect=called.append):
            assert pack_dcm(str(path)) is None
        assert called == []

    def test_gdcmconv_success(self, tmp_path, monkeypatch):
        path = tmp_path / 'scan.dcm'
        path.write_bytes(build_dicom() + b'\x00' * 200)
        original = path.read_bytes()

        def fake_resolve(key):
            return '/usr/bin/gdcmconv' if key == 'gdcmconv' else None

        def fake_run(cmd, **kwargs):
            assert cmd[0] == '/usr/bin/gdcmconv'
            assert cmd[1] == '--jpegls'
            assert '--lossy' not in cmd
            out = cmd[-1]
            with open(out, 'wb') as fh:
                fh.write(b'\x00' * 128 + b'DICM' + b'x')
            return type('R', (), {'returncode': 0})()

        monkeypatch.setattr('filerepack.codecs.resolve_tool', fake_resolve)
        with patch('filerepack.repack._run_command', fake_run):
            result = pack_dcm(str(path), lossy=True)
        assert result is not None
        assert result.replaced
        assert path.read_bytes().startswith(b'\x00' * 128 + b'DICM')
        assert len(path.read_bytes()) < len(original)

    def test_dcmcjpls_fallback(self, tmp_path, monkeypatch):
        path = tmp_path / 'scan.dcm'
        path.write_bytes(build_dicom() + b'\x00' * 200)

        def fake_resolve(key):
            return '/usr/bin/dcmcjpls' if key == 'dcmcjpls' else None

        def fake_run(cmd, **kwargs):
            assert cmd[0] == '/usr/bin/dcmcjpls'
            assert '--jpegls' not in cmd
            with open(cmd[-1], 'wb') as fh:
                fh.write(b'\x00' * 128 + b'DICM' + b'y')
            return type('R', (), {'returncode': 0})()

        monkeypatch.setattr('filerepack.codecs.resolve_tool', fake_resolve)
        with patch('filerepack.repack._run_command', fake_run):
            result = pack_dcm(str(path))
        assert result is not None
        assert result.replaced

    def test_failed_encoder_leaves_original(self, tmp_path, monkeypatch):
        path = tmp_path / 'scan.dcm'
        path.write_bytes(build_dicom())
        original = path.read_bytes()

        monkeypatch.setattr(
            'filerepack.codecs.resolve_tool',
            lambda key: '/usr/bin/gdcmconv' if key == 'gdcmconv' else None,
        )
        with patch('filerepack.repack._run_command', return_value=None):
            assert pack_dcm(str(path)) is None
        assert path.read_bytes() == original

    def test_invalid_output_not_committed(self, tmp_path, monkeypatch):
        path = tmp_path / 'scan.dcm'
        path.write_bytes(build_dicom() + b'\x00' * 200)
        original = path.read_bytes()

        def fake_run(cmd, **kwargs):
            with open(cmd[-1], 'wb') as fh:
                fh.write(b'not-dicom')
            return type('R', (), {'returncode': 0})()

        monkeypatch.setattr(
            'filerepack.codecs.resolve_tool',
            lambda key: '/usr/bin/gdcmconv' if key == 'gdcmconv' else None,
        )
        with patch('filerepack.repack._run_command', fake_run):
            assert pack_dcm(str(path)) is None
        assert path.read_bytes() == original

    def test_env_override(self, monkeypatch, tmp_path):
        fake = tmp_path / 'gdcmconv'
        fake.write_text('#!/bin/sh\n')
        monkeypatch.setenv('FILEREPACK_GDCMCONV', str(fake))
        from filerepack.tools import resolve_tool
        import filerepack.tools as tools_mod
        tools_mod._CONFIG_CACHE = None
        assert resolve_tool('gdcmconv') == str(fake)

    def test_no_images_skips_dispatch(self, tmp_path):
        path = tmp_path / 'scan.dcm'
        path.write_bytes(build_dicom())
        with patch('filerepack.codecs.pack_dcm') as mocked:
            res = _dispatch_packer('dcm', str(path), {'pack_images': False})
        assert res is None
        mocked.assert_not_called()


class TestPackDcmIntegration:
    def test_real_encoder_if_installed(self, tmp_path):
        import shutil
        if not shutil.which('gdcmconv') and not shutil.which('dcmcjpls'):
            import pytest
            pytest.skip('gdcmconv/dcmcjpls not installed')
        path = tmp_path / 'scan.dcm'
        path.write_bytes(encoder_fixture())
        result = pack_dcm(str(path))
        assert has_dicm_magic(str(path))
        if result is not None and result.replaced:
            assert verify_output(str(path), 'dcm')
            assert os.path.getsize(str(path)) > 132
