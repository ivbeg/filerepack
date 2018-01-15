#-*- coding: utf-8 -*-

ZIP_PATH = 'zip'
SZIP_PATH = '7za'
SZIP_OPTIONS = ''

DEFAULT_JPEG_QUALITY = '85'
JPEGOPTIM_PATH = 'jpegoptim'
JPEGIOPTIM_OPTIONS = ' --strip-all -m%s -p -o ' % (DEFAULT_JPEG_QUALITY)
PNGQUANT_PATH = 'pngquant'
PNGQUANT_OPTIONS = ' --force --speed 1 '
SUPPORTED_EXTS = ['docx', 'pptx', 'xlsx', 'ods', 'odt', 'otp','ott', 'ppsx', 'xmind', 'epub', 'zip', 'jar', 'apk', 'ipa', 'sldx']
EXT_IMAGE_MAP = {
    'docx': ['/word/media', '/docProps'],
    'xlsx': ['/xl/media', '/docProps'],
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
ZIP_SENSITIVE_EXTS = ['docx', 'pptx', 'xlsx', 'ppsx', 'pptx']
