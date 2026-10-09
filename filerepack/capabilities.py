"""Typed capability view joining routing, validators and optional prerequisites."""

import importlib.util
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

from .dispatch import _PACKERS
from .formats import FileKind
from .verification import VALIDATORS, _ALIASES
from .tools import resolve_tool
from .format_registry import FORMAT_REGISTRY

REGISTRY_VERSION = 1
_NATIVE = {
    'arrow': ('data', 'pyarrow'), 'ipc': ('data', 'pyarrow'), 'feather': ('data', 'pyarrow'),
    'orc': ('data', 'pyarrow'), 'avro': ('data', 'fastavro'), 'parquet': ('data', 'pyarrow'),
    'tracev3': ('tracev3', 'lz4'), 'ole': ('ole', 'olefile'), 'car': ('', ''),
    'pdf': ('pdf', 'pikepdf'), 'tiff': ('scientific', 'tifffile'),
    'tif': ('scientific', 'tifffile'),
    'h5': ('scientific', 'h5py'), 'hdf5': ('scientific', 'h5py'), 'hdf': ('scientific', 'h5py'),
    'nc': ('scientific', 'netCDF4'), 'nc4': ('scientific', 'netCDF4'),
    'checkpoint': ('serialization', 'psutil'), 'r-serialization': ('serialization', 'psutil'),
    'mat': ('scientific', 'h5py'), 'spss': ('scientific', 'pyreadstat'),
    'woff': ('fonts', 'fontTools'), 'woff2': ('fonts', 'fontTools'),
}
_TOOLS = {
    'jpg': ('jpegtran',), 'png': ('oxipng', 'optipng'), 'gif': ('gifsicle',),
    'webp': ('dwebp', 'cwebp'), 'jxl': ('djxl', 'cjxl'), 'avif': ('avifdec', 'avifenc'),
    'svg': ('svgo', 'scour'), 'mp3': ('mp3packer',), 'flac': ('flac',),
}
_VALIDATOR = {'ipc': 'arrow', 'r-serialization': 'r-serialization', 'car': 'car'}
_INSPECTION_ONLY = frozenset(('safetensors', 'gguf', 'onnx'))


@dataclass(frozen=True)
class FormatCapability:
    key: str
    family: str
    packer: Optional[str]
    category: str
    writer: bool
    validator: bool
    inspection_only: bool
    tools: Tuple[str, ...] = ()
    extra: Optional[str] = None
    missing: Tuple[str, ...] = ()
    experimental: bool = False
    extension: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), 'registry_version': REGISTRY_VERSION}


def capability(kind: FileKind) -> FormatCapability:
    key = kind.packer or kind.key
    spec = _PACKERS.get(key)
    category = spec.category if spec else 'archive'
    inspection_only = key in _INSPECTION_ONLY
    validator_key = _VALIDATOR.get(key, _ALIASES.get(key, key))
    if kind.is_archive:
        validator_key = 'tar' if kind.family.startswith('tar') else kind.family
    tools = _TOOLS.get(key, ())
    if category == 'video':
        tools = ('ffmpeg', 'ffprobe')
    if kind.is_archive:
        tools = ('szip',)
    extra, module = _NATIVE.get(key, ('', ''))
    missing = []
    # Some adapters have proven alternative encoders; record that distinction.
    alternatives = key in ('png', 'svg', 'jpg')
    unavailable = [name for name in tools if resolve_tool(name) is None]
    if unavailable and (not alternatives or len(unavailable) == len(tools)):
        missing.extend(unavailable)
    if module and not _module_available(module):
        missing.append('filerepack[' + extra + ']')
    if category == 'image' and key not in ('dcm', 'dicom', 'dic', 'tif', 'tiff'):
        if not _module_available('PIL'):
            missing.append('filerepack[validation]')
    if key in ('dcm', 'dicom', 'dic') and not _module_available('pydicom'):
        missing.append('filerepack[dicom]')
    writer = bool(spec or kind.is_archive) and not inspection_only and kind.family != 'cab'
    return FormatCapability(key, kind.family, kind.packer, category, writer,
                            validator_key in VALIDATORS, inspection_only,
                            tools, extra or None, tuple(missing), key in ('mat', 'spss'), kind.key)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def format_capabilities() -> Tuple[FormatCapability, ...]:
    return tuple(capability(FileKind(item.extension, item.family, item.packer))
                 for _, item in sorted(FORMAT_REGISTRY.items()))
