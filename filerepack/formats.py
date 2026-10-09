# -*- coding: utf-8 -*-

"""Identify supported files, including compound names like ``archive.tar.gz``."""

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Tuple

from .consts import ARCHIVE_EXTS, STANDALONE_EXTS, SUPPORTED_EXTS
from .format_registry import COMPOUND_FAMILY, SPECIAL_FAMILY, STANDALONE_ALIASES

# Longest first so ``tar.lzma`` wins over ``tar.lz`` / ``lzma``.
COMPOUND_SUFFIXES: Tuple[str, ...] = (
    'cpio.bz2', 'tar.lzma', 'tar.lz4', 'tar.zst', 'tar.bz2', 'tar.gzip', 'tar.gz',
    'tar.xz', 'tar.br', 'tar.lzo', 'tar.lz', 'tar.z',
)


# Short aliases and non-ZIP archive families.

# Standalone extension → packer key (so --include-ext dcm matches .dicom).

STREAM_PEEK_EXTS: FrozenSet[str] = frozenset({
    'gz', 'gzip', 'xz', 'bz2', 'zst', 'br', 'lz4', 'lz', 'lzma', 'lzo', 'z',
})

_STREAM_TO_TAR_FAMILY = {
    'gz': 'tar.gz',
    'gzip': 'tar.gz',
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


def _r_suffix(name: str) -> Optional[str]:
    base = _basename_lower(name)
    for extension in ('rds', 'rda', 'rdata'):
        for codec in ('gz', 'gzip', 'bz2', 'xz'):
            suffix = extension + '.' + codec
            if base.endswith('.' + suffix):
                return suffix
    return None


def filename_exts(name: str) -> List[str]:
    """Extension keys that filters like ``--include-ext`` may match."""
    keys: List[str] = []
    if _basename_lower(name).endswith(('.warc.gz', '.warc.gzip')):
        keys.extend(['warc.gz', 'warc'])
    r_suffix = _r_suffix(name)
    if r_suffix:
        keys.extend([r_suffix, r_suffix.split(".")[0], "r-serialization"])
    compound = compound_suffix(name)
    if compound:
        keys.append(compound)
        if compound == 'tar.gzip':
            keys.append('tar.gz')
        if compound == 'cpio.bz2':
            keys.extend(['cpio', 'cpbz2', 'bz2'])
        aliased = SPECIAL_FAMILY.get(_last_ext(name))
        if aliased and aliased not in keys:
            keys.append(aliased)
    ext = _last_ext(name)
    if ext and ext not in keys:
        keys.append(ext)
        mapped = SPECIAL_FAMILY.get(ext)
        if mapped and mapped not in keys:
            keys.append(mapped)
        if ext == 'cpbz2' and 'bz2' not in keys:
            keys.append('bz2')
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
    import subprocess
    import sys
    from .commands import capture_prefix
    try:
        if codec in ('gz', 'bz2', 'xz', 'lzma'):
            return _looks_like_tar(capture_prefix(
                [sys.executable, '-m', 'filerepack.peek_worker', codec, path],
            ))
    except (OSError, EOFError, ValueError, subprocess.TimeoutExpired):
        return False
    return _peek_cli_tar(path, codec)


def _peek_cli_tar(path: str, codec: str) -> bool:
    """Decompress the first 512 bytes via CLI; do not read the whole stream."""
    import subprocess
    from .commands import capture_prefix
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
        return _looks_like_tar(capture_prefix([tool] + flags + [path]))
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def _is_odf_zip(path: str) -> bool:
    """True when path is a ZIP (ODF formula templates share .otf with OpenType)."""
    import zipfile
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def identify_filename(  # noqa: C901
    name: str, peek_path: Optional[str] = None,
) -> Optional[FileKind]:
    """Return how *name* should be processed, or None if unsupported."""
    if peek_path:
        from .checkpoint import looks_like_checkpoint
        if looks_like_checkpoint(peek_path):
            return FileKind(key=_last_ext(name) or 'checkpoint', family='standalone',
                            packer='checkpoint')
    if _basename_lower(name).endswith(('.warc.gz', '.warc.gzip')):
        return FileKind(key='warc.gz', family='standalone', packer='warc')
    r_suffix = _r_suffix(name)
    if r_suffix:
        return FileKind(key=r_suffix, family="standalone", packer="r-serialization")
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
        if peek_path and ext in ('gz', 'gzip') and peek_gzip_is_warc(peek_path):
            return FileKind(key=ext, family='standalone', packer='warc')
        if peek_path and ext == 'bz2':
            from .cpio import cpio_magic

            if cpio_magic(peek_path, compressed=True):
                return FileKind(key='cpio.bz2', family='cpio.bz2')
        if peek_path and ext in STREAM_PEEK_EXTS:
            if peek_stream_is_tar(peek_path, ext):
                tar_family = _STREAM_TO_TAR_FAMILY.get(ext)
                if tar_family:
                    return FileKind(key=ext, family=tar_family)
        packer = STANDALONE_ALIASES.get(ext, ext)
        return FileKind(key=ext, family='standalone', packer=packer)

    return None


def peek_gzip_is_warc(path: str) -> bool:
    """Identify WARC-bearing gzip files even when their name omits `.warc`."""
    import subprocess
    import sys
    from .commands import capture_prefix

    try:
        return capture_prefix([sys.executable, '-m', 'filerepack.peek_worker', 'gz', path],
                              maximum=5).startswith(b'WARC/')
    except (OSError, EOFError, ValueError, subprocess.TimeoutExpired):
        return False


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
