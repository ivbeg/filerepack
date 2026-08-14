# -*- coding: utf-8 -*-

# ZIP-based and archive formats handled by extract + recompress
ARCHIVE_EXTS = [
    'zip',
    # Microsoft OOXML zip based formats
    'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
    'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
    'sldx', 'thmx', 'vdw', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx',
    'vsdx', 'zipx', 'xps', 'dwfx', 'oxps',
    # Apple documents formats
    'pages', 'key', 'numbers',
    # OpenXML file formats
    'ods', 'odt', 'otp', 'ott', 'odp', 'odg', 'odf', 'sxw', 'sxc', 'sxi',
    'sxd', 'odc', 'odi', 'odm',
    # MindMaps
    'xmind',
    # EBooks
    'epub', 'fb2', 'lpf',
    # Programming packages
    'jar', 'egg', 'whl',
    # Android and iPhone apps
    'apk', 'ipa',
    # Miro board files
    'rtb',
    # Music files
    'mxl',
    # CBZ files
    'cbz',
    # Design and creative software files
    'idml', 'afpub', 'scrivx', 'afphoto', 'afdesign',
    # 7z / RAR
    '7z', 'rar',
    # Geographic and mapping files
    'kmz',
    # 3D files
    '3mf',
]

# Standalone formats with dedicated pack_* functions
STANDALONE_EXTS = [
    'parquet',
    'gz', 'xz', 'bz2', 'zst', 'br',
    'pdf',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'tif', 'tiff', 'avif',
    'heic', 'heif',
    'wmv', 'mp4', 'avi', 'asf', 'mkv', 'webm',
    'flac',
]

SUPPORTED_EXTS = ARCHIVE_EXTS + STANDALONE_EXTS

# OOXML-like ZIPs that historically broke with 7-Zip extra fields.
# Rewrite these with Info-ZIP `zip` when it is on PATH; fall back to 7zz.
ZIP_SENSITIVE_EXTS = [
    'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
    'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
    'sldx', 'thmx', 'vdw', 'vsdx', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm',
    'xltx', 'zipx',
]

DEFAULT_JPEG_QUALITY = 85
DEFAULT_MAX_EXTRACT_BYTES = 8 * 1024 ** 3
DEFAULT_MAX_EXTRACT_RATIO = 100.0
