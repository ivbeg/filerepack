# -*- coding: utf-8 -*-

"""Platform-specific install commands for external tools used by filerepack."""

import sys
from shutil import which
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# Package names (whitespace-separated if one tool needs several packages).
# Keys match ToolSpec.key in tools.py. Managers: brew, ports, apt, dnf, pacman,
# zypper, apk, choco, winget, scoop, npm, pip. `url` is a manual-download hint;
# optional `note` is prepended in doctor output.
PACKAGES: Dict[str, Dict[str, str]] = {
    'szip': {
        'brew': 'p7zip', 'ports': 'p7zip', 'apt': 'p7zip-full',
        'dnf': 'p7zip p7zip-plugins', 'pacman': 'p7zip', 'zypper': 'p7zip',
        'apk': 'p7zip', 'choco': '7zip', 'winget': '7zip.7zip', 'scoop': '7zip',
    },
    'zip': {
        'brew': 'zip', 'ports': 'zip', 'apt': 'zip', 'dnf': 'zip',
        'pacman': 'zip', 'zypper': 'zip', 'apk': 'zip', 'choco': 'zip',
        'scoop': 'zip',
    },
    'unrar': {
        'apt': 'unrar', 'dnf': 'unrar', 'pacman': 'unrar', 'zypper': 'unrar',
        'apk': 'unrar', 'ports': 'unrar', 'choco': 'unrar',
        'url': 'https://www.rarlab.com/download.htm',
    },
    'rar': {
        'apt': 'rar', 'choco': 'winrar', 'winget': 'RARLab.WinRAR',
        'url': 'https://www.rarlab.com/download.htm',
    },
    'jpegoptim': {
        'brew': 'jpegoptim', 'ports': 'jpegoptim', 'apt': 'jpegoptim',
        'dnf': 'jpegoptim', 'pacman': 'jpegoptim', 'zypper': 'jpegoptim',
        'apk': 'jpegoptim', 'choco': 'jpegoptim',
    },
    'pngquant': {
        'brew': 'pngquant', 'ports': 'pngquant', 'apt': 'pngquant',
        'dnf': 'pngquant', 'pacman': 'pngquant', 'zypper': 'pngquant',
        'apk': 'pngquant', 'choco': 'pngquant',
    },
    'oxipng': {
        'brew': 'oxipng', 'ports': 'oxipng', 'apt': 'oxipng', 'dnf': 'oxipng',
        'pacman': 'oxipng', 'choco': 'oxipng',
    },
    'optipng': {
        'brew': 'optipng', 'ports': 'optipng', 'apt': 'optipng',
        'dnf': 'optipng', 'pacman': 'optipng', 'zypper': 'optipng',
        'apk': 'optipng', 'choco': 'optipng',
    },
    'gifsicle': {
        'brew': 'gifsicle', 'ports': 'gifsicle', 'apt': 'gifsicle',
        'dnf': 'gifsicle', 'pacman': 'gifsicle', 'zypper': 'gifsicle',
        'apk': 'gifsicle', 'choco': 'gifsicle',
    },
    'dwebp': {
        'brew': 'webp', 'ports': 'webp', 'apt': 'webp', 'dnf': 'libwebp-tools',
        'pacman': 'libwebp', 'zypper': 'libwebp-tools', 'apk': 'libwebp-tools',
        'choco': 'webp', 'scoop': 'libwebp',
    },
    'cwebp': {
        'brew': 'webp', 'ports': 'webp', 'apt': 'webp', 'dnf': 'libwebp-tools',
        'pacman': 'libwebp', 'zypper': 'libwebp-tools', 'apk': 'libwebp-tools',
        'choco': 'webp', 'scoop': 'libwebp',
    },
    'svgo': {
        'brew': 'svgo', 'npm': 'svgo',
    },
    'scour': {
        'apt': 'python3-scour', 'dnf': 'python3-scour', 'pacman': 'python-scour',
        'zypper': 'python3-scour', 'pip': 'scour',
    },
    'convert': {
        'brew': 'imagemagick', 'ports': 'ImageMagick', 'apt': 'imagemagick',
        'dnf': 'ImageMagick', 'pacman': 'imagemagick', 'zypper': 'ImageMagick',
        'apk': 'imagemagick', 'choco': 'imagemagick',
        'winget': 'ImageMagick.ImageMagick', 'scoop': 'imagemagick',
    },
    'tiffcp': {
        'brew': 'libtiff', 'ports': 'tiff', 'apt': 'libtiff-tools',
        'dnf': 'libtiff', 'pacman': 'libtiff', 'zypper': 'tiff',
        'apk': 'tiff', 'choco': 'libtiff',
    },
    'gs': {
        'brew': 'ghostscript', 'ports': 'ghostscript', 'apt': 'ghostscript',
        'dnf': 'ghostscript', 'pacman': 'ghostscript', 'zypper': 'ghostscript',
        'apk': 'ghostscript', 'choco': 'ghostscript',
        'winget': 'ArtifexSoftware.GhostScript',
    },
    'qpdf': {
        'brew': 'qpdf', 'ports': 'qpdf', 'apt': 'qpdf', 'dnf': 'qpdf',
        'pacman': 'qpdf', 'zypper': 'qpdf', 'apk': 'qpdf', 'choco': 'qpdf',
        'scoop': 'qpdf',
    },
    'ffmpeg': {
        'brew': 'ffmpeg', 'ports': 'ffmpeg', 'apt': 'ffmpeg', 'dnf': 'ffmpeg',
        'pacman': 'ffmpeg', 'zypper': 'ffmpeg', 'apk': 'ffmpeg',
        'choco': 'ffmpeg', 'winget': 'Gyan.FFmpeg', 'scoop': 'ffmpeg',
    },
    'pigz': {
        'brew': 'pigz', 'ports': 'pigz', 'apt': 'pigz', 'dnf': 'pigz',
        'pacman': 'pigz', 'zypper': 'pigz', 'apk': 'pigz',
    },
    'xz': {
        'brew': 'xz', 'ports': 'xz', 'apt': 'xz-utils', 'dnf': 'xz',
        'pacman': 'xz', 'zypper': 'xz', 'apk': 'xz', 'choco': 'xz',
        'scoop': 'xz',
    },
    'bzip2': {
        'brew': 'bzip2', 'ports': 'bzip2', 'apt': 'bzip2', 'dnf': 'bzip2',
        'pacman': 'bzip2', 'zypper': 'bzip2', 'apk': 'bzip2',
    },
    'zstd': {
        'brew': 'zstd', 'ports': 'zstd', 'apt': 'zstd', 'dnf': 'zstd',
        'pacman': 'zstd', 'zypper': 'zstd', 'apk': 'zstd', 'scoop': 'zstd',
    },
    'brotli': {
        'brew': 'brotli', 'ports': 'brotli', 'apt': 'brotli', 'dnf': 'brotli',
        'pacman': 'brotli', 'zypper': 'brotli', 'apk': 'brotli', 'scoop': 'brotli',
    },
    'lz4': {
        'brew': 'lz4', 'ports': 'lz4', 'apt': 'lz4', 'dnf': 'lz4',
        'pacman': 'lz4', 'zypper': 'lz4', 'apk': 'lz4', 'choco': 'lz4',
        'scoop': 'lz4',
    },
    'lzip': {
        'brew': 'lzip', 'ports': 'lzip', 'apt': 'lzip', 'dnf': 'lzip',
        'pacman': 'lzip', 'zypper': 'lzip', 'apk': 'lzip',
    },
    'lzma': {
        'brew': 'xz', 'ports': 'xz', 'apt': 'xz-utils', 'dnf': 'xz',
        'pacman': 'xz', 'zypper': 'xz', 'apk': 'xz', 'choco': 'xz',
    },
    'lzop': {
        'brew': 'lzop', 'ports': 'lzop', 'apt': 'lzop', 'dnf': 'lzop',
        'pacman': 'lzop', 'zypper': 'lzop', 'apk': 'lzop',
    },
    'compress': {
        'brew': 'ncompress', 'ports': 'ncompress', 'apt': 'ncompress',
        'dnf': 'ncompress', 'pacman': 'ncompress', 'zypper': 'ncompress',
        'apk': 'ncompress',
    },
    'gzip': {
        'brew': 'gzip', 'ports': 'gzip', 'apt': 'gzip', 'dnf': 'gzip',
        'pacman': 'gzip', 'zypper': 'gzip', 'apk': 'gzip',
    },
    'avifenc': {
        'brew': 'libavif', 'ports': 'libavif', 'apt': 'libavif-bin',
        'dnf': 'libavif', 'pacman': 'libavif', 'apk': 'libavif-apps',
    },
    'avifdec': {
        'brew': 'libavif', 'ports': 'libavif', 'apt': 'libavif-bin',
        'dnf': 'libavif', 'pacman': 'libavif', 'apk': 'libavif-apps',
    },
    'cjxl': {
        'brew': 'jpeg-xl', 'ports': 'jpeg-xl', 'apt': 'libjxl-tools',
        'dnf': 'libjxl-utils', 'pacman': 'libjxl', 'apk': 'libjxl',
    },
    'djxl': {
        'brew': 'jpeg-xl', 'ports': 'jpeg-xl', 'apt': 'libjxl-tools',
        'dnf': 'libjxl-utils', 'pacman': 'libjxl', 'apk': 'libjxl',
    },
    'flac': {
        'brew': 'flac', 'ports': 'flac', 'apt': 'flac', 'dnf': 'flac',
        'pacman': 'flac', 'zypper': 'flac', 'apk': 'flac', 'choco': 'flac',
        'scoop': 'flac',
    },
    'h5repack': {
        'brew': 'hdf5', 'ports': 'hdf5', 'apt': 'hdf5-tools', 'dnf': 'hdf5',
        'pacman': 'hdf5', 'zypper': 'hdf5', 'apk': 'hdf5',
    },
    'nccopy': {
        'brew': 'netcdf', 'ports': 'netcdf', 'apt': 'netcdf-bin', 'dnf': 'netcdf',
        'pacman': 'netcdf', 'zypper': 'netcdf', 'apk': 'netcdf',
    },
    'mac': {
        'url': 'https://www.monkeysaudio.com/',
    },
    'woff2_compress': {
        'brew': 'woff2', 'ports': 'woff2', 'apt': 'woff2', 'dnf': 'woff2',
        'pacman': 'woff2',
    },
    'woff2_decompress': {
        'brew': 'woff2', 'ports': 'woff2', 'apt': 'woff2', 'dnf': 'woff2',
        'pacman': 'woff2',
    },
    'mp3packer': {
        'url': 'https://github.com/Snesnopic/mp3packer/releases',
        'note': 'not packaged; download the OS zip from',
    },
    'gdcmconv': {
        'brew': 'gdcm', 'ports': 'gdcm', 'apt': 'libgdcm-tools',
        'dnf': 'gdcm', 'pacman': 'gdcm', 'zypper': 'gdcm',
        'url': 'https://sourceforge.net/projects/gdcm/',
    },
    'dcmcjpls': {
        'brew': 'dcmtk', 'ports': 'dcmtk', 'apt': 'dcmtk',
        'dnf': 'dcmtk', 'pacman': 'dcmtk', 'zypper': 'dcmtk',
        'apk': 'dcmtk', 'choco': 'dcmtk',
        'url': 'https://dicom.offis.de/dcmtk',
    },
}

COMMAND_TEMPLATES = {
    'brew': 'brew install {pkgs}',
    'ports': 'sudo port install {pkgs}',
    'apt': 'sudo apt-get install {pkgs}',
    'dnf': 'sudo dnf install {pkgs}',
    'pacman': 'sudo pacman -S {pkgs}',
    'zypper': 'sudo zypper install {pkgs}',
    'apk': 'sudo apk add {pkgs}',
    'choco': 'choco install {pkgs} -y',
    'winget': 'winget install {pkgs}',
    'scoop': 'scoop install {pkgs}',
    'npm': 'npm install -g {pkgs}',
    'pip': 'pip install {pkgs}',
}

MANAGER_LABELS = {
    'brew': 'Homebrew',
    'ports': 'MacPorts',
    'apt': 'apt (Debian/Ubuntu)',
    'dnf': 'dnf (Fedora/RHEL)',
    'pacman': 'pacman (Arch)',
    'zypper': 'zypper (openSUSE)',
    'apk': 'apk (Alpine)',
    'choco': 'Chocolatey',
    'winget': 'winget',
    'scoop': 'Scoop',
    'npm': 'npm',
    'pip': 'pip',
}

_MANAGER_BINARIES = (
    ('brew', 'brew'),
    ('ports', 'port'),
    ('apt', 'apt-get'),
    ('dnf', 'dnf'),
    ('dnf', 'yum'),
    ('pacman', 'pacman'),
    ('zypper', 'zypper'),
    ('apk', 'apk'),
    ('choco', 'choco'),
    ('winget', 'winget'),
    ('scoop', 'scoop'),
)

_LINUX_DEFAULT = {
    'debian': 'apt',
    'fedora': 'dnf',
    'arch': 'pacman',
    'suse': 'zypper',
    'alpine': 'apk',
}

_OS_TITLES = {
    'macos': 'macOS',
    'linux': 'Linux',
    'windows': 'Windows',
}


def detect_system(platform_name: Optional[str] = None) -> str:
    name = (platform_name or sys.platform).lower()
    if name == 'darwin':
        return 'macos'
    if name.startswith('win'):
        return 'windows'
    if name.startswith('linux'):
        return 'linux'
    return 'other'


def linux_family(os_release_text: Optional[str] = None) -> str:
    text = os_release_text
    if text is None:
        try:
            with open('/etc/os-release', encoding='utf-8') as fh:
                text = fh.read()
        except OSError:
            return 'unknown'
    data: Dict[str, str] = {}
    for line in text.splitlines():
        if '=' not in line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        data[key] = value.strip().strip('"').strip("'")
    blob = f"{data.get('ID', '')} {data.get('ID_LIKE', '')}".lower()
    if any(token in blob for token in (
        'debian', 'ubuntu', 'mint', 'pop', 'elementary', 'raspbian', 'kali',
    )):
        return 'debian'
    if any(token in blob for token in (
        'fedora', 'rhel', 'centos', 'rocky', 'alma', 'nobara',
    )):
        return 'fedora'
    if any(token in blob for token in ('arch', 'manjaro', 'endeavouros', 'cachyos')):
        return 'arch'
    if any(token in blob for token in ('suse', 'opensuse', 'sles')):
        return 'suse'
    if 'alpine' in blob:
        return 'alpine'
    return 'unknown'


def _present_managers() -> List[str]:
    found: List[str] = []
    for manager, binary in _MANAGER_BINARIES:
        if manager not in found and which(binary):
            found.append(manager)
    return found


def choose_managers(
    system: Optional[str] = None,
    managers: Optional[Sequence[str]] = None,
) -> Tuple[Optional[str], List[str]]:
    """Return (primary_manager, alternative_managers) for this OS."""
    if managers:
        return managers[0], list(managers[1:])

    system = system or detect_system()
    present = _present_managers()

    if system == 'macos':
        if 'brew' in present:
            return 'brew', ['ports']
        if 'ports' in present:
            return 'ports', ['brew']
        return 'brew', ['ports']

    if system == 'windows':
        preferred = [m for m in ('winget', 'choco', 'scoop') if m in present]
        if not preferred:
            preferred = ['choco', 'winget', 'scoop']
        return preferred[0], preferred[1:]

    if system == 'linux':
        default = _LINUX_DEFAULT.get(linux_family())
        linux_mgrs = [m for m in present if m in (
            'apt', 'dnf', 'pacman', 'zypper', 'apk',
        )]
        if default and default in linux_mgrs:
            primary = default
        elif linux_mgrs:
            primary = linux_mgrs[0]
        else:
            primary = default or 'apt'
        alts = [m for m in linux_mgrs if m != primary]
        return primary, alts

    return None, []


def _pkg_names(tool_key: str, manager: str) -> List[str]:
    raw = PACKAGES.get(tool_key, {}).get(manager)
    if not raw:
        return []
    return raw.split()


def _unique(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _format_command(manager: str, packages: Sequence[str]) -> str:
    pkgs = ' '.join(_unique(packages))
    return COMMAND_TEMPLATES[manager].format(pkgs=pkgs)


def _manual_hint(pkgs: Dict[str, str]) -> str:
    url = (pkgs.get('url') or '').strip()
    note = (pkgs.get('note') or '').strip()
    if note and url:
        return f'{note} {url}'
    return note or url


def install_command(
    tool_key: str,
    *,
    system: Optional[str] = None,
    manager: Optional[str] = None,
) -> str:
    """One-line install command for a single tool on this platform."""
    system = system or detect_system()
    if manager is None:
        manager = choose_managers(system)[0]
    if manager:
        names = _pkg_names(tool_key, manager)
        if names:
            return _format_command(manager, names)
    pkgs = PACKAGES.get(tool_key, {})
    if pkgs.get('npm'):
        return _format_command('npm', pkgs['npm'].split())
    if pkgs.get('pip'):
        return _format_command('pip', pkgs['pip'].split())
    return _manual_hint(pkgs)


def _platform_title(system: str, primary: Optional[str] = None) -> str:
    if system == 'linux':
        from_mgr = {
            'apt': 'Linux (Debian/Ubuntu)',
            'dnf': 'Linux (Fedora/RHEL)',
            'pacman': 'Linux (Arch)',
            'zypper': 'Linux (openSUSE)',
            'apk': 'Linux (Alpine)',
        }
        if primary in from_mgr:
            return from_mgr[primary]
        family = linux_family()
        return from_mgr.get(_LINUX_DEFAULT.get(family, ''), 'Linux')
    return _OS_TITLES.get(system, system)


def _collect_packages(
    missing_keys: Sequence[str],
    primary: Optional[str],
    alternatives: Sequence[str],
) -> Tuple[Dict[str, List[str]], List[Tuple[str, str]]]:
    by_manager: Dict[str, List[str]] = {}
    manual: List[Tuple[str, str]] = []

    def add(manager: str, names: Sequence[str]) -> None:
        if not names:
            return
        by_manager.setdefault(manager, []).extend(names)

    for key in missing_keys:
        pkgs = PACKAGES.get(key, {})
        placed = False
        if primary:
            names = _pkg_names(key, primary)
            if names:
                add(primary, names)
                placed = True
        for alt in alternatives:
            names = _pkg_names(key, alt)
            if names:
                add(alt, names)
                placed = True
        if not placed:
            if pkgs.get('npm'):
                add('npm', pkgs['npm'].split())
                placed = True
            elif pkgs.get('pip'):
                add('pip', pkgs['pip'].split())
                placed = True
        if pkgs.get('url') and not (primary and _pkg_names(key, primary)):
            manual.append((key, _manual_hint(pkgs)))
        elif not placed and not pkgs.get('url'):
            manual.append((key, pkgs.get('note') or ''))
    return by_manager, manual


def _add_fallback_managers(
    missing_keys: Sequence[str],
    by_manager: Dict[str, List[str]],
) -> None:
    for manager in ('brew', 'apt', 'choco'):
        if manager in by_manager:
            continue
        names = [n for key in missing_keys for n in _pkg_names(key, manager)]
        if names:
            by_manager[manager] = names


def _manager_order(
    primary: Optional[str],
    alternatives: Sequence[str],
    by_manager: Dict[str, List[str]],
) -> List[str]:
    order: List[str] = []
    if primary:
        order.append(primary)
    order.extend(alternatives)
    for extra in ('npm', 'pip'):
        if extra not in order:
            order.append(extra)
    for manager in by_manager:
        if manager not in order:
            order.append(manager)
    return order


def _render_install_lines(
    system: str,
    primary: Optional[str],
    by_manager: Dict[str, List[str]],
    manual: List[Tuple[str, str]],
    order: Sequence[str],
) -> List[str]:
    lines: List[str] = []
    if system == 'other':
        lines.append('Install missing tools with your OS package manager:')
    else:
        lines.append(f'Install missing tools on {_platform_title(system, primary)}:')
    lines.append('')
    if system == 'macos' and primary == 'brew' and not which('brew'):
        lines.append('  Homebrew is not on PATH. Install it from https://brew.sh then:')
        lines.append('')
    for manager in order:
        packages = by_manager.get(manager)
        if not packages:
            continue
        label = MANAGER_LABELS.get(manager, manager)
        lines.append(f'  {label}:')
        lines.append(f'    {_format_command(manager, packages)}')
        lines.append('')
    if manual:
        lines.append('  Manual install:')
        for key, url in manual:
            suffix = f'  {url}' if url else ''
            lines.append(f'    {key}{suffix}')
        lines.append('')
    return lines


def format_install_instructions(
    missing_keys: Sequence[str],
    *,
    system: Optional[str] = None,
    managers: Optional[Sequence[str]] = None,
) -> str:
    """Human-readable install help for missing tools on this OS."""
    if not missing_keys:
        return ''

    system = system or detect_system()
    primary, alternatives = choose_managers(system, managers)
    by_manager, manual = _collect_packages(missing_keys, primary, alternatives)
    if system == 'other':
        primary = primary or 'apt'
        _add_fallback_managers(missing_keys, by_manager)

    order = _manager_order(primary, alternatives, by_manager)
    lines = _render_install_lines(system, primary, by_manager, manual, order)
    has_commands = any(by_manager.get(m) for m in order) or bool(manual)
    if not has_commands:
        return ''
    lines.append('  See docs/tools.md for full install notes.')
    return '\n'.join(lines).rstrip() + '\n'
