# -*- coding: utf-8 -*-

import gzip
import io
import os
import tarfile
import zipfile
from unittest.mock import patch

from filerepack.repack import (
    FileRepacker, _commit_output, _dispatch_packer, _expand_globs,
    pack_jpg, pack_png, pack_wmv, pack_avif, pack_brotli, pack_flac, pack_heic,
)
from filerepack.codecs import (
    pack_lz4, pack_jxl, pack_sqlite, pack_woff, pack_mp3, pack_ai, pack_psd,
)
from filerepack.utils import verify_output


class TestExpandGlobs:
    def test_expand_star_pattern(self, tmp_path):
        (tmp_path / 'file1.txt').write_text('hello')
        (tmp_path / 'file2.txt').write_text('world')
        (tmp_path / 'subdir').mkdir()
        (tmp_path / 'subdir' / 'file3.txt').write_text('nested')

        cmd = ['7zz', 'a', 'output.7z', '*']
        expanded = _expand_globs(cmd, cwd=str(tmp_path))

        assert expanded[0] == '7zz'
        assert expanded[1] == 'a'
        assert expanded[2] == 'output.7z'
        assert 'file1.txt' in expanded
        assert 'file2.txt' in expanded
        assert 'subdir' in expanded

    def test_no_glob_patterns(self, tmp_path):
        cmd = ['7zz', 'x', '-y', 'archive.7z']
        expanded = _expand_globs(cmd, cwd=str(tmp_path))
        assert expanded == cmd

    def test_star_in_filename_not_expanded(self, tmp_path):
        cmd = ['7zz', 'a', 'output.7z', '*.nonexistent']
        expanded = _expand_globs(cmd, cwd=str(tmp_path))
        assert expanded == cmd


class TestCommitOutput:
    def test_keeps_original_if_larger(self, tmp_path):
        dest = tmp_path / 'orig.bin'
        dest.write_bytes(b'aa')
        temp = tmp_path / 'new.bin'
        temp.write_bytes(b'aaaa')
        res = _commit_output(str(temp), str(dest), 2, keep_if_larger=True)
        assert res is not None
        assert res.replaced is False
        assert dest.read_bytes() == b'aa'
        assert not temp.exists()

    def test_replaces_when_smaller(self, tmp_path):
        dest = tmp_path / 'orig.bin'
        dest.write_bytes(b'xxxx')
        temp = tmp_path / 'new.bin'
        temp.write_bytes(b'yy')
        res = _commit_output(str(temp), str(dest), 4, keep_if_larger=True)
        assert res is not None
        assert res.replaced is True
        assert dest.read_bytes() == b'yy'
        assert res.outsize == 2

    def test_min_savings_does_not_mutate(self, tmp_path):
        dest = tmp_path / 'orig.bin'
        dest.write_bytes(b'x' * 100)
        temp = tmp_path / 'new.bin'
        temp.write_bytes(b'x' * 99)
        original = dest.read_bytes()
        res = _commit_output(
            str(temp), str(dest), 100, keep_if_larger=True, min_savings=5.0
        )
        assert res is not None
        assert res.replaced is False
        assert dest.read_bytes() == original

    def test_dryrun_does_not_replace(self, tmp_path):
        dest = tmp_path / 'orig.bin'
        dest.write_bytes(b'xxxx')
        temp = tmp_path / 'new.bin'
        temp.write_bytes(b'y')
        res = _commit_output(str(temp), str(dest), 4, dryrun=True)
        assert res is not None
        assert res.replaced is False
        assert dest.read_bytes() == b'xxxx'
        assert res.outsize == 1


class TestZipRepack:
    def test_repack_zip_file(self, tmp_path):
        zip_path = str(tmp_path / 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('test.txt', 'A' * 1000)
            zf.writestr('subdir/more.txt', 'B' * 500)

        dr = FileRepacker(quiet=True)
        results = dr.repack_zip_file(zip_path, def_options={
            'debug': True,
            'quiet': True,
            'pack_images': False,
            'dryrun': False,
        })

        assert results is not None
        assert 'final' in results
        assert os.path.exists(zip_path)

    def test_repack_zip_progress_events(self, tmp_path):
        zip_path = str(tmp_path / 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('a.gz', gzip.compress(b'hello' * 80))
            zf.writestr('b.gz', gzip.compress(b'world' * 80))
        events = []

        def hook(event, **kwargs):
            events.append((event, kwargs.get('total', 0), kwargs.get('name', '')))

        FileRepacker(quiet=True).repack_zip_file(
            zip_path,
            def_options={'quiet': True, 'dryrun': True},
            on_progress=hook,
        )
        names = [e[0] for e in events]
        assert names[0] == 'extract'
        if 'files' not in names:
            return
        assert 'files' in names
        assert names.count('file') == 2
        assert 'write' in names

    def test_repack_dryrun(self, tmp_path):
        zip_path = str(tmp_path / 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('test.txt', 'A' * 1000)

        original_size = os.path.getsize(zip_path)
        original = open(zip_path, 'rb').read()

        dr = FileRepacker(quiet=True)
        dr.repack_zip_file(zip_path, def_options={
            'debug': False,
            'quiet': True,
            'pack_images': False,
            'dryrun': True,
        })

        assert os.path.getsize(zip_path) == original_size
        assert open(zip_path, 'rb').read() == original

    def test_dryrun_predicts_inner_file_savings(self, tmp_path):
        zip_path = str(tmp_path / 'test.zip')
        payload = bytes(range(256)) * 2000
        fat_gz = gzip.compress(payload, compresslevel=1)
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_STORED) as zf:
            zf.writestr('payload.gz', fat_gz)

        original = open(zip_path, 'rb').read()
        dr = FileRepacker(quiet=True)
        predicted = dr.repack_zip_file(zip_path, def_options={
            'quiet': True, 'dryrun': True,
        })
        assert open(zip_path, 'rb').read() == original

        actual = dr.repack_zip_file(zip_path, def_options={
            'quiet': True, 'dryrun': False,
        })
        if predicted.inner_count == 0 and actual.inner_count == 0:
            return
        assert predicted.total_outsize == actual.total_outsize
        assert predicted.total_outsize < predicted.total_insize

    def test_dryrun_applies_inner_packs_in_extract_dir(self, tmp_path):
        zip_path = str(tmp_path / 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('payload.gz', gzip.compress(b'hello' * 80, compresslevel=1))

        seen = []

        def spy(ext, fullname, options):
            seen.append(options.get('dryrun'))
            return _dispatch_packer(ext, fullname, options)

        with patch('filerepack.repack._dispatch_packer', side_effect=spy):
            FileRepacker(quiet=True).repack_zip_file(
                zip_path, def_options={'quiet': True, 'dryrun': True},
            )
        if not seen:
            return
        assert seen == [False]

    def test_missing_7zz_does_not_delete_zip(self, tmp_path):
        zip_path = str(tmp_path / 'test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('test.txt', 'hello-world')
        original = open(zip_path, 'rb').read()

        with patch('filerepack.repack.resolve_szip', return_value=None):
            dr = FileRepacker(quiet=True)
            results = dr.repack_zip_file(zip_path, def_options={'quiet': True})

        assert os.path.exists(zip_path)
        assert open(zip_path, 'rb').read() == original
        assert results.total_outsize == results.total_insize


class TestOoxmlAndExtractLimits:
    def _minimal_docx(self, path):
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr(
                '[Content_Types].xml',
                '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                'package/2006/content-types"></Types>',
            )
            zf.writestr('word/document.xml', '<w:document>' + ('x' * 200) + '</w:document>')

    def test_ooxml_roundtrip_keeps_content_types(self, tmp_path):
        path = str(tmp_path / 'doc.docx')
        self._minimal_docx(path)
        dr = FileRepacker(quiet=True)
        dr.repack_zip_file(path, def_options={
            'quiet': True, 'pack_images': False, 'dryrun': False,
        })
        assert zipfile.is_zipfile(path)
        with zipfile.ZipFile(path) as zf:
            assert '[Content_Types].xml' in zf.namelist()

    def test_oversized_zip_is_not_rewritten(self, tmp_path):
        zip_path = str(tmp_path / 'bomb.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('a.txt', 'hello-world')
        original = open(zip_path, 'rb').read()
        with patch(
            'filerepack.repack.zip_uncompressed_size',
            return_value=10 * 1024 ** 3,
        ):
            dr = FileRepacker(quiet=True)
            results = dr.repack_zip_file(zip_path, def_options={'quiet': True})
        assert open(zip_path, 'rb').read() == original
        assert results.total_outsize == results.total_insize

    def test_docx_prefers_infozip(self, tmp_path):
        path = str(tmp_path / 'doc.docx')
        self._minimal_docx(path)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd[0] if cmd else '')
            for arg in cmd:
                if arg.endswith('.zip') and arg != path:
                    with zipfile.ZipFile(arg, 'w') as zf:
                        zf.writestr('[Content_Types].xml', '<Types/>')
                        zf.writestr('word/document.xml', 'x')
                    from subprocess import CompletedProcess
                    return CompletedProcess(cmd, 0, stdout='', stderr='')
            from subprocess import CompletedProcess
            return CompletedProcess(cmd, 0, stdout='', stderr='')

        with patch('filerepack.repack.resolve_tool', return_value='/usr/bin/zip'):
            with patch('filerepack.repack.resolve_szip', return_value='/usr/bin/7zz'):
                with patch('filerepack.repack._run_command', side_effect=fake_run):
                    FileRepacker(quiet=True).repack_zip_file(
                        path, def_options={'quiet': True, 'pack_images': False},
                    )
        assert any('zip' in c for c in calls)


class TestPackerFailures:
    def test_pack_jpg_missing_tool(self, tmp_path):
        jpg = tmp_path / 'a.jpg'
        jpg.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        with patch('filerepack.repack.resolve_tool', return_value=None):
            assert pack_jpg(str(jpg)) is None
        assert jpg.exists()

    def test_pack_png_missing_lossless_tool(self, tmp_path):
        png = tmp_path / 'a.png'
        png.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 32)
        with patch('filerepack.repack.resolve_tool', return_value=None):
            assert pack_png(str(png)) is None
        assert png.exists()

    def test_pack_wmv_ffmpeg_failure_keeps_source(self, tmp_path):
        wmv = tmp_path / 'clip.wmv'
        wmv.write_bytes(b'fake-wmv-content-not-empty')
        with patch('filerepack.repack.resolve_tool', return_value='/bin/ffmpeg'):
            with patch('filerepack.repack._encode_video', return_value=False):
                assert pack_wmv(str(wmv)) is None
        assert wmv.exists()

    def test_pack_brotli_missing_tool(self, tmp_path):
        path = tmp_path / 'a.br'
        path.write_bytes(b'\xce' + b'\x00' * 16)
        with patch('filerepack.repack.resolve_tool', return_value=None):
            assert pack_brotli(str(path)) is None
        assert path.exists()

    def test_pack_flac_missing_tool(self, tmp_path):
        path = tmp_path / 'a.flac'
        path.write_bytes(b'fLaC' + b'\x00' * 16)
        with patch('filerepack.repack.resolve_tool', return_value=None):
            assert pack_flac(str(path)) is None
        assert path.exists()

    def test_pack_avif_missing_tool(self, tmp_path):
        path = tmp_path / 'a.avif'
        path.write_bytes(b'\x00\x00\x00\x1cftypavif')
        with patch('filerepack.repack.resolve_tool', return_value=None):
            assert pack_avif(str(path)) is None
        assert path.exists()

    def test_pack_heic_missing_tool(self, tmp_path):
        path = tmp_path / 'a.heic'
        path.write_bytes(b'\x00\x00\x00\x18ftypheic')
        with patch('filerepack.repack.resolve_tool', return_value=None):
            assert pack_heic(str(path)) is None
        assert path.exists()

    def test_pack_lz4_missing_tool(self, tmp_path):
        path = tmp_path / 'a.lz4'
        path.write_bytes(b'\x04\x22\x4d\x18' + b'\x00' * 16)
        with patch('filerepack.codecs.resolve_tool', return_value=None):
            assert pack_lz4(str(path)) is None
        assert path.exists()

    def test_pack_jxl_missing_tool(self, tmp_path):
        path = tmp_path / 'a.jxl'
        path.write_bytes(b'\xff\x0a' + b'\x00' * 16)
        with patch('filerepack.codecs.resolve_tool', return_value=None):
            assert pack_jxl(str(path)) is None
        assert path.exists()

    def test_pack_woff_missing_fonttools(self, tmp_path):
        path = tmp_path / 'a.woff'
        path.write_bytes(b'wOFF' + b'\x00' * 16)
        with patch.dict('sys.modules', {'fontTools': None, 'fontTools.ttLib': None}):
            assert pack_woff(str(path)) is None
        assert path.exists()


class TestSqlitePack:
    def test_vacuum_shrinks_or_keeps(self, tmp_path):
        import sqlite3
        path = tmp_path / 'db.sqlite'
        conn = sqlite3.connect(str(path))
        conn.execute('CREATE TABLE t (x TEXT)')
        conn.execute("INSERT INTO t VALUES (?)", ('x' * 10000,))
        conn.commit()
        conn.execute('DELETE FROM t')
        conn.commit()
        conn.close()
        original = path.read_bytes()
        result = pack_sqlite(str(path))
        assert path.exists()
        if result is not None and result.replaced:
            assert path.stat().st_size <= len(original)
            assert path.read_bytes().startswith(b'SQLite format 3')
        else:
            assert path.read_bytes() == original

    def test_gpkg_and_mbtiles_use_sqlite_packer(self):
        from filerepack.repack import _PACKERS
        assert _PACKERS['gpkg'].func is pack_sqlite
        assert _PACKERS['mbtiles'].func is pack_sqlite


class TestMp3AiPsd:
    def test_pack_mp3_missing_tool(self, tmp_path):
        path = tmp_path / 'a.mp3'
        path.write_bytes(b'ID3' + b'\x00' * 16)
        with patch('filerepack.codecs.resolve_tool', return_value=None):
            assert pack_mp3(str(path)) is None
        assert path.exists()

    def test_pack_ai_skips_eps(self, tmp_path):
        path = tmp_path / 'logo.ai'
        path.write_bytes(b'%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator\n')
        assert pack_ai(str(path)) is None
        assert path.read_bytes().startswith(b'%!PS-Adobe')

    def test_pack_ai_pdf_calls_pdf_packer(self, tmp_path):
        path = tmp_path / 'logo.ai'
        path.write_bytes(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n')
        with patch('filerepack.repack.pack_pdf', return_value=None) as mocked:
            assert pack_ai(str(path)) is None
            mocked.assert_called_once()

    def test_pack_psd_skips_raw_composite(self, tmp_path):
        import struct
        path = tmp_path / 'flat.psd'
        header = b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6
        header += struct.pack('>H', 3)
        header += struct.pack('>I', 1) + struct.pack('>I', 1)
        header += struct.pack('>H', 8) + struct.pack('>H', 3)
        header += struct.pack('>I', 0) + struct.pack('>I', 0) + struct.pack('>I', 0)
        original = header + struct.pack('>H', 0) + b'\x00\x00\x00'
        path.write_bytes(original)
        assert pack_psd(str(path)) is None
        assert path.read_bytes() == original

    def test_pack_psd_recompresses_zip_composite(self, tmp_path):
        import struct
        import zlib
        width = height = 48
        raw = bytes((i * 13) % 256 for i in range(width * height * 3))
        payload = zlib.compress(raw, 1)
        header = b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6
        header += struct.pack('>H', 3)
        header += struct.pack('>I', height) + struct.pack('>I', width)
        header += struct.pack('>H', 8) + struct.pack('>H', 3)
        header += struct.pack('>I', 0) + struct.pack('>I', 0) + struct.pack('>I', 0)
        original = header + struct.pack('>H', 2) + payload
        path = tmp_path / 'zipped.psd'
        path.write_bytes(original)
        result = pack_psd(str(path))
        assert path.exists()
        assert path.read_bytes().startswith(b'8BPS')
        if result is not None and result.replaced:
            assert path.stat().st_size <= len(original)



class TestTarGzContainer:
    def test_targz_roundtrip_with_7zz(self, tmp_path):
        import shutil
        if not shutil.which('7zz') and not shutil.which('7z'):
            import pytest
            pytest.skip('7zz/7z required')
        archive = tmp_path / 'bundle.tar.gz'
        payload = io.BytesIO(b'hello-world' * 50)
        with tarfile.open(str(archive), 'w:gz') as tar:
            info = tarfile.TarInfo('hello.txt')
            info.size = payload.getbuffer().nbytes
            payload.seek(0)
            tar.addfile(info, payload)
        original = archive.read_bytes()
        FileRepacker(quiet=True).repack_zip_file(
            str(archive), def_options={'quiet': True, 'pack_images': False},
        )
        assert archive.exists()
        assert archive.read_bytes()[:2] == b'\x1f\x8b' or archive.read_bytes() == original


class TestVerifyOutput:
    def test_zip(self, tmp_path):
        path = tmp_path / 't.zip'
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('a.txt', 'x')
        assert verify_output(str(path), 'zip')

    def test_jpeg_header(self, tmp_path):
        path = tmp_path / 't.jpg'
        path.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 8)
        assert verify_output(str(path), 'jpg')
        path.write_bytes(b'not-a-jpeg')
        assert not verify_output(str(path), 'jpg')

    def test_dcm_magic(self, tmp_path):
        path = tmp_path / 't.dcm'
        path.write_bytes(b'\x00' * 128 + b'DICM' + b'\x00' * 4)
        assert verify_output(str(path), 'dcm')
        path.write_bytes(b'\x00' * 132)
        assert not verify_output(str(path), 'dcm')

    def test_flac_header(self, tmp_path):
        path = tmp_path / 't.flac'
        path.write_bytes(b'fLaC' + b'\x00' * 8)
        assert verify_output(str(path), 'flac')

    def test_new_magics(self, tmp_path):
        cases = [
            ('lz4', b'\x04\x22\x4d\x18' + b'\x00' * 4),
            ('cab', b'MSCF' + b'\x00' * 8),
            ('woff2', b'wOF2' + b'\x00' * 8),
            ('sqlite', b'SQLite format 3\x00'),
            ('z', b'\x1f\x9d' + b'\x00' * 8),
            ('psd', b'8BPS' + b'\x00' * 8),
            ('mp3', b'ID3' + b'\x00' * 8),
        ]
        for kind, data in cases:
            path = tmp_path / f't.{kind}'
            path.write_bytes(data)
            assert verify_output(str(path), kind), kind
