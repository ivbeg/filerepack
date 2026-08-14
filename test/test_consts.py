# -*- coding: utf-8 -*-

from filerepack.consts import (
    ARCHIVE_EXTS, STANDALONE_EXTS, SUPPORTED_EXTS, ZIP_SENSITIVE_EXTS,
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

    def test_contains_compressed(self):
        assert 'gz' in SUPPORTED_EXTS
        assert 'xz' in SUPPORTED_EXTS
        assert 'bz2' in SUPPORTED_EXTS


class TestZipSensitiveExts:
    def test_docx_in_sensitive(self):
        assert 'docx' in ZIP_SENSITIVE_EXTS

    def test_xlsx_in_sensitive(self):
        assert 'xlsx' in ZIP_SENSITIVE_EXTS
