# -*- coding: utf-8 -*-

"""Identify supported files, including compound names like ``archive.tar.gz``."""

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Tuple

from .consts import ARCHIVE_EXTS, STANDALONE_EXTS, SUPPORTED_EXTS

# Longest first so ``tar.lzma`` wins over ``tar.lz`` / ``lzma``.
COMPOUND_SUFFIXES: Tuple[str, ...] = (
    'tar.lzma', 'tar.lz4', 'tar.zst', 'tar.bz2', 'tar.gz',
    'tar.xz', 'tar.br', 'tar.lzo', 'tar.lz', 'tar.z',
)

COMPOUND_FAMILY = {
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

# Short aliases and non-ZIP archive families.
SPECIAL_FAMILY = {
    '7z': '7z', 'cb7': '7z',
    'rar': 'rar', 'cbr': 'rar',
    'tar': 'tar', 'cbt': 'tar',
    'tgz': 'tar.gz', 'taz': 'tar.gz', 'gem': 'tar.gz', 'crate': 'tar.gz',
    'unitypackage': 'tar.gz',
    'tbz': 'tar.bz2', 'tbz2': 'tar.bz2',
    'txz': 'tar.xz',
    'tzst': 'tar.zst',
    'tlz': 'tar.lz',
    'tzo': 'tar.lzo',
    'cab': 'cab',
    'wim': 'wim',
}

# Standalone extension → packer key (so --include-ext dcm matches .dicom).
STANDALONE_ALIASES = {
    'dicom': 'dcm',
    'dic': 'dcm',
}

STREAM_PEEK_EXTS: FrozenSet[str] = frozenset({
    'gz', 'xz', 'bz2', 'zst', 'br', 'lz4', 'lz', 'lzma', 'lzo', 'z',
})

_STREAM_TO_TAR_FAMILY = {
    'gz': 'tar.gz',
    'xz': 'tar.xz',
    'bz2': 'tar.bz2',
    'zst': 'tar.zst',
    'br': 'tar.br',
    'lz4': 'tar.lz4',
    'lz': 'tar.lz',
    'lzma': 'tar.lzma',
    'z': 'tar.z',
}


@dataclass(frozen=True)
class FileKind:
    """How a path should be handled."""

    key: str
    family: str
    packer: Optional[str] = None

    @property
    def is_archive(self) -> bool:
        return self.family != 'standalone'


def _last_ext(name: str) -> str:
    base = name.replace('\\', '/').rsplit('/', 1)[-1].lower()
    if '.' not in base:
        return ''
    return base.rsplit('.', 1)[-1]


def _basename_lower(name: str) -> str:
    return name.replace('\\', '/').rsplit('/', 1)[-1].lower()


def compound_suffix(name: str) -> Optional[str]:
    """Return ``tar.gz`` (etc.) when *name* uses a compound archive suffix."""
    base = _basename_lower(name)
    for suffix in COMPOUND_SUFFIXES:
        if base.endswith('.' + suffix):
            return suffix
    return None


def filename_exts(name: str) -> List[str]:
    """Extension keys that filters like ``--include-ext`` may match."""
    keys: List[str] = []
    compound = compound_suffix(name)
    if compound:
        keys.append(compound)
        aliased = SPECIAL_FAMILY.get(_last_ext(name))
        if aliased and aliased not in keys:
            keys.append(aliased)
    ext = _last_ext(name)
    if ext and ext not in keys:
        keys.append(ext)
        mapped = SPECIAL_FAMILY.get(ext)
        if mapped and mapped not in keys:
            keys.append(mapped)
        alias = STANDALONE_ALIASES.get(ext)
        if alias and alias not in keys:
            keys.append(alias)
    return keys


def archive_family(key: str) -> Optional[str]:
    """Container rewrite family for an extension or compound suffix."""
    if key in COMPOUND_FAMILY:
        return COMPOUND_FAMILY[key]
    if key in SPECIAL_FAMILY:
        return SPECIAL_FAMILY[key]
    if key in ARCHIVE_EXTS:
        return 'zip'
    return None


def _looks_like_tar(header: bytes) -> bool:
    if len(header) < 262:
        return False
    return header[257:262] == b'ustar'


def peek_stream_is_tar(path: str, codec: str) -> bool:
    """True when a compressed stream's payload starts with a tar header."""
    try:
        if codec == 'gz':
            import gzip
            with gzip.open(path, 'rb') as fh:
                return _looks_like_tar(fh.read(512))
        if codec == 'bz2':
            import bz2
            with bz2.open(path, 'rb') as fh:
                return _looks_like_tar(fh.read(512))
        if codec == 'xz' or codec == 'lzma':
            import lzma
            fmt = None if codec == 'xz' else lzma.FORMAT_ALONE
            with lzma.open(path, 'rb', format=fmt) as fh:
                return _looks_like_tar(fh.read(512))
    except (OSError, EOFError, ValueError):
        return False
    return _peek_cli_tar(path, codec)


def _peek_cli_tar(path: str, codec: str) -> bool:
    """Decompress the first 512 bytes via CLI; do not read the whole stream."""
    import subprocess
    from .tools import resolve_tool

    decode = {
        'zst': ('zstd', ['-d', '-c']),
        'br': ('brotli', ['-d', '-c']),
        'lz4': ('lz4', ['-d', '-c']),
        'lz': ('lzip', ['-d', '-c']),
        'lzo': ('lzop', ['-d', '-c']),
        'z': ('gzip', ['-d', '-c']),
    }.get(codec)
    if decode is None:
        return False
    key, flags = decode
    tool = resolve_tool(key)
    if tool is None and key == 'gzip':
        tool = resolve_tool('pigz')
    if tool is None:
        return False
    try:
        proc = subprocess.Popen(
            [tool] + flags + [path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            header = proc.stdout.read(512) if proc.stdout else b''
        finally:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.wait()
        return _looks_like_tar(header)
    except (OSError, subprocess.SubprocessError):
        return False


def _is_odf_zip(path: str) -> bool:
    """True when path is a ZIP (ODF formula templates share .otf with OpenType)."""
    import zipfile
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def identify_filename(
    name: str, peek_path: Optional[str] = None,
) -> Optional[FileKind]:
    """Return how *name* should be processed, or None if unsupported."""
    compound = compound_suffix(name)
    if compound:
        return FileKind(key=compound, family=COMPOUND_FAMILY[compound])

    ext = _last_ext(name)
    if not ext:
        return None

    family = archive_family(ext)
    if family:
        return FileKind(key=ext, family=family)

    # .otf is ODF formula-template or OpenType font; only ZIP is ODF.
    if ext == 'otf':
        if peek_path and _is_odf_zip(peek_path):
            return FileKind(key='otf', family='zip')
        return None

    if ext in STANDALONE_EXTS:
        if peek_path and ext in STREAM_PEEK_EXTS:
            if peek_stream_is_tar(peek_path, ext):
                tar_family = _STREAM_TO_TAR_FAMILY.get(ext)
                if tar_family:
                    return FileKind(key=ext, family=tar_family)
        packer = STANDALONE_ALIASES.get(ext, ext)
        return FileKind(key=ext, family='standalone', packer=packer)

    return None


def is_supported_filename(name: str, peek_path: Optional[str] = None) -> bool:
    if compound_suffix(name):
        return True
    ext = _last_ext(name)
    if ext == 'otf':
        return peek_path is not None and _is_odf_zip(peek_path)
    return ext in SUPPORTED_EXTS


def matches_ext_filter(name: str, include: Optional[List[str]]) -> bool:
    if not include:
        return True
    wanted = {e.lower().lstrip('.') for e in include}
    return any(key in wanted for key in filename_exts(name))


def excluded_by_ext_filter(name: str, exclude: Optional[List[str]]) -> bool:
    if not exclude:
        return False
    blocked = {e.lower().lstrip('.') for e in exclude}
    return any(key in blocked for key in filename_exts(name))
