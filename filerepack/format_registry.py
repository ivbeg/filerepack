"""Typed filename metadata; legacy extension/alias/family tables are derived views."""

from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class FormatDefinition:
    extension: str
    family: str
    packer: Optional[str] = None
    inspection_only: bool = False

_ARCHIVE_NAMES = (
    'zip', 'accdt', 'crtx', 'docm', 'docx', 'dotm', 'dotx', 'gcsx', 'glox',
    'gqsx', 'potm', 'potx', 'ppam', 'ppsm', 'ppsx', 'pptm', 'pptx', 'sldm',
    'sldx', 'thmx', 'vdw', 'xlam', 'xlsb', 'xlsm', 'xlsx', 'xltm', 'xltx',
    'vsdx', 'vsdm', 'vstx', 'vstm', 'vssx', 'vssm', 'zipx', 'xps', 'dwfx',
    'oxps', 'pages', 'key', 'numbers', 'kth', 'nmbtemplate', 'template', 'ods', 'odt',
    'otp', 'ott', 'ots', 'otg', 'odp', 'odg', 'odf', 'odb', 'oth',
    'otm', 'otc', 'oti', 'sxw', 'sxc', 'sxi', 'sxd', 'stw', 'stc',
    'sti', 'std', 'sxg', 'sxm', 'odc', 'odi', 'odm', 'oxt', 'xmind',
    'epub', 'lpf', 'ibooks', 'air', 'pk3', 'xap', 'ipsw', 'osk', 'oex',
    'puz', 'rmskin', 'notebook', 'nbk', 'mellel', 'jar', 'egg', 'whl', 'war',
    'ear', 'aar', 'npz', 'nupkg', 'snupkg', 'vsix', 'xpi', 'crx', 'apk',
    'aab', 'xapk', 'apks', 'ipa', 'appx', 'msix', 'appxbundle', 'rtb', 'mxl',
    'cbz', 'cbr', 'cb7', 'cbt', 'mcworld', 'mcpack', 'mcaddon', 'idml', 'afpub',
    'scrivx', 'afphoto', 'afdesign', 'sketch', 'kra', 'ora', 'xd', '7z', 'rar',
    'kmz', 'ifczip', 'qgz', '3mf', 'usdz', 'fcstd', 'onepkg', 'wgt', 'tar',
    'tgz', 'taz', 'tbz', 'tbz2', 'txz', 'tzst', 'tlz', 'tzo', 'cpio',
    'cpbz2', 'gem', 'crate', 'unitypackage', 'cab', 'wim',
)
_STANDALONE_NAMES = (
    'warc', 'rds', 'rda', 'rdata', 'mat', 'pt', 'pth', 'sav', 'zsav',
    'safetensors', 'gguf', 'onnx', 'doc', 'dot', 'xls', 'xlt', 'xla', 'ppt',
    'pot', 'pps', 'msg', 'vsd', 'pub', 'mpp', 'msi', 'hwp', 'parquet',
    'orc', 'avro', 'feather', 'arrow', 'ipc', 'sqlite', 'sqlite3', 'db', 'gpkg',
    'mbtiles', 'vscdb', 'sqlitedb', 'duckdb', 'h5', 'hdf5', 'hdf', 'nc', 'nc4',
    'gz', 'gzip', 'xz', 'bz2', 'zst', 'br', 'lz4', 'lz', 'lzma',
    'lzo', 'z', 'pdf', 'nib', 'car', 'tracev3', 'jpg', 'jpeg', 'jpe',
    'jfif', 'jif', 'jfi', 'thm', 'png', 'apng', 'gif', 'webp', 'svg',
    'svgz', 'tif', 'tiff', 'avif', 'heic', 'heif', 'jxl', 'jp2', 'j2k',
    'jpf', 'jpx', 'exr', 'dng', 'ico', 'icns', 'cur', 'bmp', 'dib',
    'tga', 'targa', 'pnm', 'ppm', 'pgm', 'pbm', 'pcx', 'dcx', 'xml',
    'json', 'geojson', 'ipynb', 'jsonl', 'ndjson', 'qgs', 'qgd', 'ui', 'map',
    'har', 'topojson', 'gltf', 'rels', 'swf', 'tgs', 'xhtml', 'kml', 'gpx',
    'dae', 'rss', 'atom', 'xmp', 'xsl', 'xslt', 'fb2', 'dcm', 'dicom',
    'dic', 'wmv', 'mp4', 'avi', 'asf', 'mkv', 'webm', 'mov', 'm4v',
    '3gp', 'ts', 'mts', 'm2ts', 'flac', 'm4a', 'm4b', 'wv', 'ape',
    'tta', 'oga', 'ogg', 'opus', 'mp3', 'woff', 'woff2', 'psd', 'psb',
    'ai', 'blend', 'fits', 'fit', 'fts', 'nrrd', 'ase', 'aseprite',
)

_COMPOUND_FAMILY = {
    'cpio.bz2': 'cpio.bz2',
    'tar.gzip': 'tar.gz',
    'tar.gz': 'tar.gz',
    'tar.bz2': 'tar.bz2',
    'tar.xz': 'tar.xz',
    'tar.zst': 'tar.zst',
    'tar.br': 'tar.br',
    'tar.lz4': 'tar.lz4',
    'tar.lzo': 'tar.lzo',
    'tar.lz': 'tar.lz',
    'tar.lzma': 'tar.lzma',
    'tar.z': 'tar.z',
}

_SPECIAL_FAMILY = {
    '7z': '7z',
    'cb7': '7z',
    'rar': 'rar',
    'cbr': 'rar',
    'tar': 'tar',
    'cbt': 'tar',
    'cpio': 'cpio',
    'cpbz2': 'cpio.bz2',
    'tgz': 'tar.gz',
    'taz': 'tar.z',
    'gem': 'tar',
    'crate': 'tar.gz',
    'unitypackage': 'tar.gz',
    'tbz': 'tar.bz2',
    'tbz2': 'tar.bz2',
    'txz': 'tar.xz',
    'tzst': 'tar.zst',
    'tlz': 'tar.lz',
    'tzo': 'tar.lzo',
    'cab': 'cab',
    'wim': 'wim',
}

_STANDALONE_ALIASES = {
    'gzip': 'gz',
    'rds': 'r-serialization',
    'rda': 'r-serialization',
    'rdata': 'r-serialization',
    'pt': 'checkpoint',
    'pth': 'checkpoint',
    'sav': 'spss',
    'zsav': 'spss',
    'doc': 'ole',
    'dot': 'ole',
    'xls': 'ole',
    'xlt': 'ole',
    'xla': 'ole',
    'ppt': 'ole',
    'pot': 'ole',
    'pps': 'ole',
    'msg': 'ole',
    'vsd': 'ole',
    'pub': 'ole',
    'mpp': 'ole',
    'msi': 'ole',
    'hwp': 'ole',
    'geojson': 'json',
    'ipynb': 'json',
    'map': 'json',
    'har': 'json',
    'topojson': 'json',
    'gltf': 'json',
    'ndjson': 'jsonl',
    'ui': 'xml',
    'rels': 'xml',
    'fit': 'fits',
    'fts': 'fits',
    'ase': 'aseprite',
    'dicom': 'dcm',
    'dic': 'dcm',
    'db': 'sqlite',
    'vscdb': 'sqlite',
    'sqlitedb': 'sqlite',
    'apng': 'png',
    'cur': 'ico',
    'jif': 'jpg',
    'jfi': 'jpg',
    'jfif': 'jpg',
    'jpe': 'jpg',
    'jpeg': 'jpg',
    'thm': 'jpg',
    'm4b': 'm4a',
    'dib': 'bmp',
    'targa': 'tga',
    'ppm': 'pnm',
    'pgm': 'pnm',
    'pbm': 'pnm',
    'dcx': 'pcx',
    'opus': 'ogg',
    'xhtml': 'xml',
    'kml': 'xml',
    'gpx': 'xml',
    'dae': 'xml',
    'rss': 'xml',
    'atom': 'xml',
    'xmp': 'xml',
    'xsl': 'xml',
    'xslt': 'xml',
    'fb2': 'xml',
}

FORMAT_REGISTRY: Dict[str, FormatDefinition] = {
    name: FormatDefinition(name, _SPECIAL_FAMILY.get(name, "zip"))
    for name in _ARCHIVE_NAMES
}
FORMAT_REGISTRY.update({
    name: FormatDefinition(name, "standalone",
                           _STANDALONE_ALIASES.get(name, name),
                           name in ("safetensors", "gguf", "onnx"))
    for name in _STANDALONE_NAMES
})
FORMAT_REGISTRY.update({name: FormatDefinition(name, family)
                        for name, family in _COMPOUND_FAMILY.items()})

ARCHIVE_EXTS = [name for name in _ARCHIVE_NAMES if FORMAT_REGISTRY[name].family != "standalone"]
STANDALONE_EXTS = [name for name in _STANDALONE_NAMES]
SUPPORTED_EXTS = ARCHIVE_EXTS + STANDALONE_EXTS
COMPOUND_FAMILY = {name: FORMAT_REGISTRY[name].family for name in _COMPOUND_FAMILY}
SPECIAL_FAMILY = {name: FORMAT_REGISTRY[name].family for name in _SPECIAL_FAMILY}
STANDALONE_ALIASES = {name: str(FORMAT_REGISTRY[name].packer) for name in _STANDALONE_ALIASES}
