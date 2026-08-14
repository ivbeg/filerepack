# -*- coding: utf-8 -*-

# ZIP-based and archive formats handled by extract + recompress
ARCHIVE_EXTS = [
    'zip',
    # Microsoft OOXML zip based formats
    'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
    'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
    'sldm', 'sldx', 'thmx', 'vdw', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm',
    'xltx', 'vsdx', 'vsdm', 'vstx', 'vstm', 'vssx', 'vssm', 'zipx', 'xps',
    'dwfx', 'oxps',
    # Apple documents formats
    'pages', 'key', 'numbers', 'kth', 'nmbtemplate', 'template',
    # OpenDocument / OpenOffice
    'ods', 'odt', 'otp', 'ott', 'ots', 'otg', 'odp', 'odg', 'odf', 'odb',
    'oth', 'otm', 'otc', 'oti',
    'sxw', 'sxc', 'sxi', 'sxd', 'stw', 'stc', 'sti', 'std', 'sxg', 'sxm',
    'odc', 'odi', 'odm', 'oxt',
    # MindMaps
    'xmind',
    # EBooks
    'epub', 'fb2', 'lpf', 'ibooks',
    # Programming / package manager archives (ZIP)
    'jar', 'egg', 'whl', 'war', 'ear', 'aar', 'npz',
    'nupkg', 'snupkg', 'vsix', 'xpi', 'crx',
    # Android, iOS, Windows app packages
    'apk', 'aab', 'xapk', 'apks', 'ipa', 'appx', 'msix', 'appxbundle',
    # Miro board files
    'rtb',
    # Music files
    'mxl',
    # Comic book archives
    'cbz', 'cbr', 'cb7', 'cbt',
    'mcworld', 'mcpack', 'mcaddon',
    # Design and creative software files
    'idml', 'afpub', 'scrivx', 'afphoto', 'afdesign',
    'sketch', 'kra', 'ora', 'xd',
    # 7z / RAR
    '7z', 'rar',
    # Geographic and mapping files
    'kmz', 'ifczip',
    # 3D files
    '3mf', 'usdz', 'fcstd',
    # Other ZIP-based
    'onepkg', 'wgt',
    # Tarballs and compressed-tar aliases (walk members, then rewrite)
    'tar', 'tgz', 'taz', 'tbz', 'tbz2', 'txz', 'tzst', 'tlz', 'tzo',
    'gem', 'crate', 'unitypackage',
    # Other 7-Zip writable containers
    'cab', 'wim',
]

# Standalone formats with dedicated pack_* functions
STANDALONE_EXTS = [
    'parquet', 'orc', 'avro', 'feather', 'arrow', 'ipc',
    'sqlite', 'sqlite3', 'gpkg', 'mbtiles',
    'h5', 'hdf5', 'hdf', 'nc', 'nc4',
    'gz', 'xz', 'bz2', 'zst', 'br', 'lz4', 'lz', 'lzma', 'lzo', 'z',
    'pdf',
    'jpg', 'jpeg', 'jpe', 'jfif', 'png', 'gif', 'webp', 'svg', 'svgz',
    'tif', 'tiff', 'avif', 'heic', 'heif',
    'jxl', 'jp2', 'j2k', 'jpf', 'jpx', 'exr', 'dng', 'ico', 'icns',
    'dcm', 'dicom', 'dic',
    'wmv', 'mp4', 'avi', 'asf', 'mkv', 'webm',
    'mov', 'm4v', '3gp', 'ts', 'mts', 'm2ts',
    'flac', 'm4a', 'wv', 'ape', 'tta', 'oga', 'mp3',
    'woff', 'woff2',
    'psd', 'ai',
]

SUPPORTED_EXTS = ARCHIVE_EXTS + STANDALONE_EXTS

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
