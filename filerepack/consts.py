#-*- coding: utf-8 -*-

# Compression options
ZIP_PATH = 'zip'
SZIP_PATH = '7za'
SZIP_OPTIONS = ''

# Compression options
DEFAULT_JPEG_QUALITY = '85'
JPEGOPTIM_PATH = 'jpegoptim'
JPEGIOPTIM_OPTIONS = ' --strip-all -m%s -p -o ' % (DEFAULT_JPEG_QUALITY)
PNGQUANT_PATH = 'pngquant'
PNGQUANT_OPTIONS = ' --force --speed 1 '
JPEG_RE_CMD = 'jpeg-recompress'
JPEG_RE_OPTIONS = '-a -s -q veryhigh'

SUPPORTED_EXTS = ["zip",
# Microsoft OOXML zip based formats
'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
'sldx', 'thmx', 'vdw', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx', 'vsdx', 'zipx',
# OpenXML file formats
'ods', 'odt', 'otp','ott',
# MindMaps
'xmind',
# EBooks
'epub',
# Programming packages
'jar', 'egg',
# Android and iPhone apps
'apk', 'ipa']
                                

EXT_IMAGE_MAP = {
    'docx': ['/word/media', '/docProps'],
    'xlsx': ['/xl/media', '/docProps'],
    'vsdx' : ['/visio/media'],
    'pptx': ['/ppt/media', '/docProps'],
    'ppsx': ['/ppt/media', '/docProps'],
    'sldx' : ['/ppt/media', '/docProps'],
    'ods': ['/Thumbnails', '/Pictures'],
    'odt': ['/Thumbnails', '/Pictures'],
    'ott': ['/Thumbnails', '/Pictures'],
    'otp': ['/Thumbnails', '/Pictures'],
    'xmind': ['/Thumbnails', '/markers'],
    'epub': [''],
    'zip' : ['',],
    'jar' : ['',],
    'apk' : ['',],
    'ipa' : ['',],
}

# File types with this extension are sensitive to ZIP program used. We use "zip" instead of 7-Zip to improve it's compression
ZIP_SENSITIVE_EXTS = ['accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox', 'gqsx',
'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx',
'sldx', 'thmx', 'vdw', 'vsdx', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx', 'zipx']
