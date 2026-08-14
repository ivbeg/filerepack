# -*- coding: utf-8 -*-

from filerepack.consts import (
    ARCHIVE_EXTS, DEFAULT_LOSSY_PDF_PROFILE, PDF_PROFILES,
    STANDALONE_EXTS, SUPPORTED_EXTS, ZIP_SENSITIVE_EXTS,
)


class TestSupportedExts:
    def test_contains_ooxml_formats(self):
        assert 'docx' in SUPPORTED_EXTS
        assert 'xlsx' in SUPPORTED_EXTS
        assert 'pptx' in SUPPORTED_EXTS

    def test_contains_archives(self):
        assert 'zip' in SUPPORTED_EXTS
        assert '7z' in SUPPORTED_EXTS
        assert 'rar' in SUPPORTED_EXTS

    def test_contains_jpeg_and_png(self):
        assert 'jpg' in SUPPORTED_EXTS
        assert 'jpeg' in SUPPORTED_EXTS
        assert 'png' in SUPPORTED_EXTS
        assert 'jpg' in STANDALONE_EXTS
        assert 'jpg' not in ARCHIVE_EXTS

    def test_contains_zstd(self):
        assert 'zst' in SUPPORTED_EXTS

    def test_contains_new_formats(self):
        assert 'br' in SUPPORTED_EXTS
        assert 'avif' in SUPPORTED_EXTS
        assert 'heic' in SUPPORTED_EXTS
        assert 'flac' in SUPPORTED_EXTS
        assert 'mkv' in SUPPORTED_EXTS
        assert 'webm' in SUPPORTED_EXTS

    def test_contains_images(self):
        assert 'gif' in SUPPORTED_EXTS
        assert 'webp' in SUPPORTED_EXTS
        assert 'svg' in SUPPORTED_EXTS
        assert 'tif' in SUPPORTED_EXTS
        assert 'tiff' in SUPPORTED_EXTS

    def test_contains_videos(self):
        assert 'wmv' in SUPPORTED_EXTS
        assert 'mp4' in SUPPORTED_EXTS
        assert 'avi' in SUPPORTED_EXTS
        assert 'asf' in SUPPORTED_EXTS

    def test_contains_zip_aliases(self):
        for ext in (
            'war', 'ear', 'aar', 'nupkg', 'vsix', 'sketch', 'cbr', 'cb7',
            'oxt', 'aab', 'npz', 'fcstd', 'xapk', 'mcworld', 'unitypackage',
        ):
            assert ext in SUPPORTED_EXTS
            assert ext in ARCHIVE_EXTS

    def test_contains_tarball_aliases(self):
        for ext in (
            'tar', 'tgz', 'tbz2', 'txz', 'tzst', 'tlz', 'tzo', 'gem', 'crate',
            'unitypackage', 'cab', 'wim',
        ):
            assert ext in ARCHIVE_EXTS

    def test_contains_new_standalone(self):
        for ext in (
            'lz4', 'jxl', 'jp2', 'exr', 'dng', 'mov', 'm4a', 'sqlite',
            'gpkg', 'mbtiles', 'orc', 'woff2', 'svgz', 'jpe', 'mp3', 'psd', 'ai',
            'dcm', 'dicom', 'dic',
        ):
            assert ext in STANDALONE_EXTS

    def test_contains_odf_templates(self):
        for ext in ('oth', 'otm', 'otc', 'oti'):
            assert ext in ARCHIVE_EXTS
        assert 'otf' not in ARCHIVE_EXTS

    def test_contains_ooo1_zip(self):
        for ext in ('sxw', 'sxc', 'sxi', 'sxd', 'stw', 'stc', 'sti', 'std', 'sxg', 'sxm'):
            assert ext in ARCHIVE_EXTS

    def test_contains_iwork_templates(self):
        for ext in ('pages', 'key', 'numbers', 'kth', 'nmbtemplate', 'template'):
            assert ext in ARCHIVE_EXTS

    def test_ooxml_siblings_sensitive(self):
        for ext in ('vsdm', 'vstx', 'vstm', 'vssx', 'vssm', 'sldm'):
            assert ext in ZIP_SENSITIVE_EXTS


class TestPdfConsts:
    def test_lossy_default_is_ebook(self):
        assert DEFAULT_LOSSY_PDF_PROFILE == 'ebook'
        assert 'ebook' in PDF_PROFILES
        assert 'prepress' in PDF_PROFILES


class TestZipSensitiveExts:
    def test_docx_in_sensitive(self):
        assert 'docx' in ZIP_SENSITIVE_EXTS

    def test_xlsx_in_sensitive(self):
        assert 'xlsx' in ZIP_SENSITIVE_EXTS
