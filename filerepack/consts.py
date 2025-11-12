#-*- coding: utf-8 -*-

# Compression options
ZIP_PATH = 'zip'
SZIP_PATH = '7zz'
SZIP_OPTIONS = ''
RAR_PATH = 'rar'
UNRAR_PATH = 'unrar'

# Compression options
DEFAULT_JPEG_QUALITY = '85'
JPEGOPTIM_PATH = 'jpegoptim'
JPEGIOPTIM_OPTIONS = ' --strip-all -m%s -p -o -f ' % (DEFAULT_JPEG_QUALITY)
PNGQUANT_PATH = 'pngquant'
PNGQUANT_OPTIONS = ' --force --speed 1 '
JPEG_RE_CMD = 'jpeg-recompress'
JPEG_RE_OPTIONS = '-a -s -q veryhigh'

SUPPORTED_EXTS = ["zip",
# Microsoft OOXML zip based formats
'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
'sldx', 'thmx', 'vdw', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx', 'vsdx', 'zipx',
'xps', 'dwfx', 'oxps',
# Apple documents formats
'pages', 'key', 'numbers', 
# OpenXML file formats
'ods', 'odt', 'otp','ott', 'odp', 'odg', 'odf', 'sxw', 'sxc', 'sxi', 'sxd', 'odc', 'odi', 'odm',
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
# Parquet files
'parquet', 
# Gzip files
'gz',
# XZ files
'xz',
# BZ2 files
'bz2',
# 7z archive files
'7z',
# RAR archive files
'rar',
# Geographic and mapping files
'kmz',
# 3D files
'3mf',
# PDF files
'pdf',
# Image formats
'gif', 'webp', 'svg', 'tif', 'tiff',
# Video formats
'wmv', 'mp4', 'avi', 'asf'
]
                                

EXT_IMAGE_MAP = {
    'docx': ['/word/media', '/docProps'],
    'xlsx': ['/xl/media', '/docProps'],
    'vsdx' : ['/visio/media'],
    'pptx': ['/ppt/media', '/docProps'],
    'ppsx': ['/ppt/media', '/docProps'],
    'sldx' : ['/ppt/media', '/docProps'],
    'ods': ['/Thumbnails', '/Pictures'],
    'odp': ['/Thumbnails', '/Pictures'],
    'odt': ['/Thumbnails', '/Pictures'],
    'ott': ['/Thumbnails', '/Pictures'],
    'otp': ['/Thumbnails', '/Pictures'],
    'xmind': ['/Thumbnails', '/markers'],
    'epub': [''],
    'zip' : ['',],
    'jar' : ['',],
    'apk' : ['',],
    'ipa' : ['',],
    'rtb' : ['',],
    'pages': [''],
    'key': [''],
    'numbers': [''],
}

# File types with this extension are sensitive to ZIP program used. We use "zip" instead of 7-Zip to improve it's compression
ZIP_SENSITIVE_EXTS = ['accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
'sldx', 'thmx', 'vdw', 'vsdx', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx', 'zipx']
