# -*- coding: utf-8 -*-

import gzip
import io
import tarfile

from unittest.mock import patch

from filerepack.formats import (
    compound_suffix, filename_exts, identify_filename, is_supported_filename,
    peek_stream_is_tar,
)


class TestIdentifyFilename:
    def test_ooxml_is_zip_family(self):
        kind = identify_filename('slides.pptx')
        assert kind is not None
        assert kind.family == 'zip'
        assert kind.is_archive

    def test_visio_stencils_are_zip_family(self):
        for name in ('shapes.vssx', 'macros.vssm'):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'zip'
            assert kind.is_archive

    def test_odf_templates_are_zip_family(self):
        for name in ('web.oth', 'master.otm', 'chart.otc', 'image.oti'):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'zip'

    def test_ooo1_zip_is_zip_family(self):
        for name in (
            'doc.stw', 'sheet.stc', 'slides.sti', 'draw.std',
            'master.sxg', 'math.sxm',
        ):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'zip'

    def test_iwork_templates_are_zip_family(self):
        for name in ('theme.kth', 'sheet.nmbtemplate', 'letter.template'):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'zip'

    def test_otf_font_is_not_odf(self, tmp_path):
        path = tmp_path / 'Inter.otf'
        path.write_bytes(b'OTTO' + b'\x00' * 32)
        assert identify_filename(str(path), peek_path=str(path)) is None
        assert is_supported_filename(str(path), peek_path=str(path)) is False

    def test_otf_zip_is_odf_package(self, tmp_path):
        import zipfile
        path = tmp_path / 'formula.otf'
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('mimetype', 'application/vnd.oasis.opendocument.formula-template')
            zf.writestr('META-INF/manifest.xml', '<manifest/>')
        kind = identify_filename(str(path), peek_path=str(path))
        assert kind is not None
        assert kind.family == 'zip'
        assert kind.key == 'otf'

    def test_compound_tar_gz(self):
        kind = identify_filename('photos.tar.gz')
        assert kind is not None
        assert kind.key == 'tar.gz'
        assert kind.family == 'tar.gz'
        assert kind.is_archive

    def test_tgz_alias(self):
        kind = identify_filename('bundle.tgz')
        assert kind is not None
        assert kind.family == 'tar.gz'

    def test_tar_lzo_is_tar_family(self):
        kind = identify_filename('src.tar.lzo')
        assert kind is not None
        assert kind.key == 'tar.lzo'
        assert kind.family == 'tar.lzo'

    def test_tlz_is_lzip_tarball(self):
        kind = identify_filename('src.tlz')
        assert kind is not None
        assert kind.family == 'tar.lz'

    def test_tzo_is_lzo_tarball(self):
        kind = identify_filename('src.tzo')
        assert kind is not None
        assert kind.family == 'tar.lzo'

    def test_sqlite_aliases_are_standalone(self):
        for name in ('map.gpkg', 'tiles.mbtiles'):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'standalone'
            assert kind.packer in ('gpkg', 'mbtiles')

    def test_new_zip_slice_is_zip_family(self):
        for name in (
            'addon.oxt', 'app.aab', 'weights.npz', 'part.fcstd',
            'mod.xapk', 'world.mcworld', 'pack.mcpack',
        ):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'zip'

    def test_unitypackage_is_targz_family(self):
        kind = identify_filename('asset.unitypackage')
        assert kind is not None
        assert kind.family == 'tar.gz'

    def test_mp3_psd_ai_standalone(self):
        for name, packer in (('song.mp3', 'mp3'), ('art.psd', 'psd'), ('logo.ai', 'ai')):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.family == 'standalone'
            assert kind.packer == packer

    def test_cbr_is_rar(self):
        kind = identify_filename('comic.cbr')
        assert kind is not None
        assert kind.family == 'rar'

    def test_cb7_is_7z(self):
        kind = identify_filename('comic.cb7')
        assert kind is not None
        assert kind.family == '7z'

    def test_cbt_is_tar(self):
        kind = identify_filename('comic.cbt')
        assert kind is not None
        assert kind.family == 'tar'

    def test_war_is_zip(self):
        kind = identify_filename('app.war')
        assert kind is not None
        assert kind.family == 'zip'

    def test_standalone_jpeg_alias(self):
        kind = identify_filename('pic.jfif')
        assert kind is not None
        assert kind.family == 'standalone'
        assert kind.packer == 'jpg'

    def test_sqlite_db_alias(self):
        kind = identify_filename('notes.db')
        assert kind is not None
        assert kind.family == 'standalone'
        assert kind.packer == 'sqlite'

    def test_apng_and_cur_aliases(self):
        assert identify_filename('icon.apng').packer == 'png'
        assert identify_filename('pointer.cur').packer == 'ico'

    def test_m4b_is_m4a(self):
        assert identify_filename('book.m4b').packer == 'm4a'

    def test_ogg_opus(self):
        assert identify_filename('a.ogg').packer == 'ogg'
        assert identify_filename('a.opus').packer == 'ogg'

    def test_xml_aliases(self):
        for name in ('a.xml', 'a.kml', 'book.fb2', 'style.xsl'):
            kind = identify_filename(name)
            assert kind is not None
            assert kind.packer == 'xml'

    def test_pk3_is_zip(self):
        kind = identify_filename('pak.pk3')
        assert kind is not None
        assert kind.family == 'zip'

    def test_deb_unsupported(self):
        assert identify_filename('pkg.deb') is None

    def test_include_ext_png_matches_apng(self):
        from filerepack.formats import filename_exts
        assert 'png' in filename_exts('icon.apng')
        assert 'jpg' in filename_exts('preview.thm')

    def test_unsupported(self):
        assert identify_filename('notes.txt') is None

    def test_peek_gz_tarball(self, tmp_path):
        tar_gz = tmp_path / 'payload.gz'
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as tar:
            info = tarfile.TarInfo('a.txt')
            data = b'hello'
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with gzip.open(tar_gz, 'wb') as fh:
            fh.write(buf.getvalue())
        kind = identify_filename(str(tar_gz), peek_path=str(tar_gz))
        assert kind is not None
        assert kind.family == 'tar.gz'

    def test_plain_gz_not_tar(self, tmp_path):
        path = tmp_path / 'log.gz'
        with gzip.open(path, 'wb') as fh:
            fh.write(b'not-a-tar-payload' * 8)
        kind = identify_filename(str(path), peek_path=str(path))
        assert kind is not None
        assert kind.family == 'standalone'
        assert kind.packer == 'gz'

    def test_peek_zst_via_cli(self, tmp_path):
        path = tmp_path / 'payload.zst'
        path.write_bytes(b'fake-zst')
        header = (b'\x00' * 257) + b'ustar' + (b'\x00' * 250)

        class _Proc:
            def __init__(self):
                self.stdout = io.BytesIO(header)

            def kill(self):
                return None

            def wait(self, timeout=None):
                return 0

        with patch('filerepack.tools.resolve_tool', return_value='/usr/bin/zstd'):
            with patch('subprocess.Popen', side_effect=lambda *a, **k: _Proc()):
                assert peek_stream_is_tar(str(path), 'zst') is True
                kind = identify_filename(str(path), peek_path=str(path))
        assert kind is not None
        assert kind.family == 'tar.zst'


class TestFilenameExts:
    def test_tar_gz_keys(self):
        keys = filename_exts('a.tar.gz')
        assert 'tar.gz' in keys
        assert 'gz' in keys

    def test_tgz_includes_family(self):
        keys = filename_exts('a.tgz')
        assert 'tgz' in keys
        assert 'tar.gz' in keys

    def test_tlz_includes_family(self):
        keys = filename_exts('a.tlz')
        assert 'tlz' in keys
        assert 'tar.lz' in keys

    def test_compound_suffix(self):
        assert compound_suffix('x.tar.xz') == 'tar.xz'
        assert compound_suffix('x.tar.lzo') == 'tar.lzo'
        assert compound_suffix('x.xz') is None


class TestIsSupported:
    def test_new_zip_aliases(self):
        assert is_supported_filename('lib.aar')
        assert is_supported_filename('pkg.nupkg')
        assert is_supported_filename('ext.vsix')
        assert is_supported_filename('board.sketch')
        assert is_supported_filename('addon.oxt')
        assert is_supported_filename('app.aab')
        assert is_supported_filename('weights.npz')
        assert is_supported_filename('part.fcstd')
        assert is_supported_filename('mod.xapk')
        assert is_supported_filename('world.mcworld')
        assert is_supported_filename('asset.unitypackage')

    def test_tarball_names(self):
        assert is_supported_filename('src.tar.gz')
        assert is_supported_filename('src.tgz')
        assert is_supported_filename('src.tar.zst')
        assert is_supported_filename('src.tar.lzo')
        assert is_supported_filename('src.tlz')
        assert is_supported_filename('src.tzo')

    def test_new_standalone(self):
        assert is_supported_filename('a.jxl')
        assert is_supported_filename('a.lz4')
        assert is_supported_filename('clip.mov')
        assert is_supported_filename('db.sqlite')
        assert is_supported_filename('map.gpkg')
        assert is_supported_filename('tiles.mbtiles')
        assert is_supported_filename('song.mp3')
        assert is_supported_filename('art.psd')
        assert is_supported_filename('logo.ai')
        assert is_supported_filename('scan.dcm')
        assert is_supported_filename('study.dicom')
        assert is_supported_filename('image.dic')
        assert is_supported_filename('notes.json')
        assert is_supported_filename('data.xml')
        assert is_supported_filename('icon.apng')
        assert is_supported_filename('notes.db')
        assert is_supported_filename('song.ogg')
        assert is_supported_filename('a.bmp')
