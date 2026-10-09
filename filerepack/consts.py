# -*- coding: utf-8 -*-

from .format_registry import (
    ARCHIVE_EXTS as ARCHIVE_EXTS,
    STANDALONE_EXTS as STANDALONE_EXTS,
    SUPPORTED_EXTS as SUPPORTED_EXTS,
)

# OOXML-like ZIPs that historically broke with 7-Zip extra fields.
# Rewrite these with Info-ZIP `zip` when it is on PATH; fall back to 7zz.
ZIP_SENSITIVE_EXTS = [
    'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
    'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
    'sldm', 'sldx', 'thmx', 'vdw', 'vsdx', 'vsdm', 'vstx', 'vstm', 'vssx',
    'vssm',
    'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx', 'zipx',
]

DEFAULT_JPEG_QUALITY = 85
PDF_PROFILES = ('screen', 'ebook', 'printer', 'prepress', 'default')
DEFAULT_LOSSY_PDF_PROFILE = 'ebook'
DEFAULT_MAX_EXTRACT_BYTES = 8 * 1024 ** 3
DEFAULT_MAX_EXTRACT_RATIO = 100.0
