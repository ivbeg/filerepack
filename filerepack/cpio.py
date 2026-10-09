"""Bounded CPIO inspection, member staging, preservation and rewriting."""

import bz2
import hashlib
import logging
import os
import stat
import unicodedata
from dataclasses import dataclass
from typing import Any, BinaryIO, Dict, Iterable, List, Literal, Optional, Tuple, Union, cast

from .archive_manifest import ArchivePreservationError, member_path
from .candidates import make_temp as _make_temp, remove_quietly as _remove_quietly
from .candidates import commit_output as _commit_output
from .models import PackResult, ProgressHook, RepackSummary
from .streams import _compress_file, pack_bz2

_COPY = 1024 * 1024
_MAGICS = (b'070701', b'070702', b'070707')


class CpioError(ArchivePreservationError):
    """CPIO input is outside the fully parsed, verified archive profile."""


@dataclass(frozen=True)
class CpioProfile:
    name: str
    header_size: int
    alignment: int
    byteorder: str = ''
    crc: bool = False


@dataclass(frozen=True)
class CpioEntry:
    offset: int
    data_offset: int
    end: int
    profile: CpioProfile
    header: bytes
    name_bytes: bytes
    name: str
    path: Optional[str]
    fields: Tuple[int, ...]
    size_field: int
    name_field: int
    check_field: Optional[int]
    size: int
    checksum: int
    digest: str
    mode: int
    mtime: int
    links: int
    inode_key: Tuple[object, ...]
    kind: str

    @property
    def trailer(self) -> bool:
        return self.name_bytes == b'TRAILER!!!\0'

    @property
    def regular(self) -> bool:
        return self.kind == 'file'

    @property
    def fields_without_payload(self) -> Tuple[int, ...]:
        if self.profile.name in ('newc', 'crc-newc'):
            return self.fields[:6] + self.fields[7:11]
        if self.profile.name == 'odc':
            return self.fields[:8]
        return self.fields[:10]


@dataclass(frozen=True)
class CpioArchive:
    entries: Tuple[CpioEntry, ...]
    trailer_padding_offset: int
    trailer_padding_size: int
    size: int
    safe_paths: bool
    hardlinks_safe: bool
    concatenated: bool

    @property
    def can_walk(self) -> bool:
        return self.safe_paths and self.hardlinks_safe and not self.concatenated


def _profile(prefix: bytes) -> CpioProfile:
    if prefix.startswith(b'070701'):
        return CpioProfile('newc', 110, 4)
    if prefix.startswith(b'070702'):
        return CpioProfile('crc-newc', 110, 4, crc=True)
    if prefix.startswith(b'070707'):
        return CpioProfile('odc', 76, 1)
    if prefix.startswith(b'\x71\xc7'):
        return CpioProfile('binary-be', 26, 2, 'big')
    if prefix.startswith(b'\xc7\x71'):
        return CpioProfile('binary-le', 26, 2, 'little')
    raise CpioError('unrecognized CPIO record magic')


def _read_ascii_fields(header: bytes, widths: Tuple[int, ...], base: int) -> Tuple[int, ...]:
    values = []
    offset = base
    for width in widths:
        encoded = header[offset:offset + width]
        if len(encoded) != width or not encoded or any(
            byte not in b'0123456789abcdefABCDEF' for byte in encoded
        ):
            raise CpioError('malformed CPIO hexadecimal field')
        values.append(int(encoded, 16))
        offset += width
    return tuple(values)


def _read_odc_fields(header: bytes) -> Tuple[int, ...]:
    widths = (6, 6, 6, 6, 6, 6, 6, 11, 6, 11)
    values = []
    offset = 6
    for width in widths:
        encoded = header[offset:offset + width]
        if len(encoded) != width or any(byte not in b'01234567' for byte in encoded):
            raise CpioError('malformed CPIO octal field')
        values.append(int(encoded, 8))
        offset += width
    return tuple(values)


def _read_binary_words(header: bytes, profile: CpioProfile) -> Tuple[int, ...]:
    byteorder = cast(Literal['little', 'big'], profile.byteorder)
    return tuple(
        int.from_bytes(header[offset:offset + 2], byteorder)
        for offset in range(0, len(header), 2)
    )


def _fields(profile: CpioProfile, header: bytes) -> Tuple[int, ...]:
    if profile.name in ('newc', 'crc-newc'):
        return _read_ascii_fields(header, (8,) * 13, 6)
    if profile.name == 'odc':
        return _read_odc_fields(header)
    return _read_binary_words(header, profile)


def _entry_values(
    profile: CpioProfile, fields: Tuple[int, ...],
) -> Tuple[
    int, int, int, int, int, int, int, Union[int, Tuple[int, ...]],
    Union[int, Tuple[int, ...]], int, int, Tuple[object, ...], int, int,
    Optional[int],
]:
    dev: Union[int, Tuple[int, ...]]
    rdev: Union[int, Tuple[int, ...]]
    stable: Tuple[object, ...]
    if profile.name in ('newc', 'crc-newc'):
        ino, mode, uid, gid, links, mtime, size = fields[:7]
        dev = fields[7:9]
        rdev = fields[9:11]
        name_size, check = fields[11:13]
        stable = (ino, mode, uid, gid, links, mtime, dev, rdev)
        size_field, name_field, check_field = 6, 11, 12
    elif profile.name == 'odc':
        dev, ino, mode, uid, gid, links, rdev, mtime, name_size, size = fields
        check = 0
        stable = (dev, ino, mode, uid, gid, links, rdev, mtime)
        size_field, name_field, check_field = 9, 8, None
    else:
        words = fields
        mtime = (words[8] << 16) | words[9]
        size = (words[11] << 16) | words[12]
        dev, ino, mode, uid, gid, links, rdev = words[1:8]
        name_size, check = words[10], 0
        stable = (dev, ino, mode, uid, gid, links, rdev, mtime)
        size_field, name_field, check_field = 11, 10, None
    return (ino, mode, uid, gid, links, mtime, size, dev, rdev, name_size, check,
            stable, size_field, name_field, check_field)


def _aligned(value: int, alignment: int) -> int:
    return value + (-value % alignment)


def _hash_payload(stream: BinaryIO, size: int) -> Tuple[str, int]:
    digest = hashlib.sha256()
    checksum = 0
    left = size
    while left:
        block = stream.read(min(_COPY, left))
        if not block:
            raise CpioError('truncated CPIO member payload')
        digest.update(block)
        checksum = (checksum + sum(block)) & 0xFFFFFFFF
        left -= len(block)
    return digest.hexdigest(), checksum


def _skip_zero_padding(source: BinaryIO, start: int, size: int) -> Optional[int]:
    source.seek(start)
    position = start
    while position < size:
        block = source.read(min(_COPY, size - position))
        if not block:
            return None
        for index, byte in enumerate(block):
            if byte:
                return position + index
        position += len(block)
    return None


def _member_path(name: str, kind: str) -> Optional[str]:
    try:
        if name == 'TRAILER!!!':
            return None
        if name.endswith('/') and kind == 'directory':
            name = name.rstrip('/')
        return member_path(name)
    except (ArchivePreservationError, ValueError):
        return None


def _validate_hardlinks(entries: Iterable[CpioEntry]) -> bool:
    groups: Dict[Tuple[object, ...], List[CpioEntry]] = {}
    for entry in entries:
        if entry.regular and entry.links > 1:
            groups.setdefault(entry.inode_key, []).append(entry)
    for members in groups.values():
        first = members[0]
        if len(members) > first.links or sum(member.size > 0 for member in members) > 1:
            return False
        if any(
            member.fields_without_payload != first.fields_without_payload
            for member in members[1:]
        ):
            return False
    return True


def parse_cpio(path: str, *, max_entries: int = 100000) -> CpioArchive:  # noqa: C901
    """Parse complete concatenated CPIO archives and verify per-record framing."""
    total_size = os.path.getsize(path)
    entries: List[CpioEntry] = []
    seen_paths: Dict[str, str] = {}
    path_kinds: Dict[str, str] = {}
    position = 0
    after_trailer = False
    archive_count = 0
    trailer_count = 0
    last_trailer_end = 0
    paths_unique = True

    with open(path, 'rb') as source:
        while position < total_size:
            source.seek(position)
            prefix = source.read(6)
            if not prefix:
                break
            if not any(prefix):
                if not after_trailer:
                    raise CpioError('unexpected zero padding before CPIO trailer')
                next_record = _skip_zero_padding(source, position, total_size)
                if next_record is None:
                    position = total_size
                    break
                position = next_record
                after_trailer = False
                archive_count += 1
                continue

            try:
                profile = _profile(prefix)
            except CpioError:
                if after_trailer:
                    raise CpioError('nonzero data after CPIO trailer')
                raise
            if position + profile.header_size > total_size:
                raise CpioError('truncated CPIO header')
            source.seek(position)
            header = source.read(profile.header_size)
            if len(header) != profile.header_size:
                raise CpioError('truncated CPIO header')
            fields = _fields(profile, header)
            (ino, mode, uid, gid, links, mtime, data_size, dev, rdev,
             name_size, check, _stable, size_field, name_field, check_field) = (
                _entry_values(profile, fields)
            )
            if not name_size or name_size > 1024 * 1024:
                raise CpioError('invalid CPIO member name length')
            name_bytes = source.read(name_size)
            if len(name_bytes) != name_size or name_bytes[-1:] != b'\0' or b'\0' in name_bytes[:-1]:
                raise CpioError('invalid CPIO member name')
            name = os.fsdecode(name_bytes[:-1])
            name_end = source.tell()
            data_offset = _aligned(name_end, profile.alignment)
            end_data = data_offset + data_size
            end = _aligned(end_data, profile.alignment)
            if end_data > total_size or end > total_size:
                raise CpioError('truncated CPIO record')
            mode_type = stat.S_IFMT(mode)
            kind = ('trailer' if name_bytes == b'TRAILER!!!\0' else
                    'file' if mode_type == stat.S_IFREG else
                    'directory' if mode_type == stat.S_IFDIR else
                    'symlink' if mode_type == stat.S_IFLNK else 'special')
            if kind == 'trailer' and data_size:
                raise CpioError('CPIO trailer carries a payload')
            source.seek(data_offset)
            digest, computed_check = _hash_payload(source, data_size)
            if profile.crc and computed_check != check:
                raise CpioError('CRC-newc member checksum mismatch')
            if not profile.crc and profile.name in ('newc', 'crc-newc') and check:
                raise CpioError('newc member has a nonzero reserved checksum')
            path_value = _member_path(name, kind)
            entry = CpioEntry(
                position, data_offset, end, profile, header, name_bytes, name,
                path_value, fields, size_field, name_field, check_field, data_size,
                check, digest, mode, mtime, links,
                (archive_count, profile.name, profile.byteorder, dev, ino), kind,
            )
            entries.append(entry)
            if len(entries) > max_entries:
                raise CpioError('CPIO member count exceeds configured limit')
            if kind != 'trailer':
                if path_value is None:
                    # Unsafe member names are retained but disable extraction.
                    pass
                else:
                    identity = unicodedata.normalize('NFC', path_value).casefold()
                    if not path_value and kind != 'directory':
                        paths_unique = False
                    if identity in seen_paths:
                        paths_unique = False
                    else:
                        seen_paths[identity] = path_value
                        path_kinds[identity] = kind
            position = end
            if kind == 'trailer':
                after_trailer = True
                trailer_count += 1
                last_trailer_end = end

    if not entries or not trailer_count or not after_trailer and position == total_size:
        raise CpioError('CPIO trailer is missing')

    safe_paths = paths_unique and all(
        entry.kind == 'trailer' or entry.path is not None for entry in entries
    )
    if safe_paths:
        for entry in entries:
            if entry.path is None:
                continue
            parents = entry.path.split('/')[:-1]
            if any(path_kinds.get(
                unicodedata.normalize('NFC', '/'.join(parents[:index + 1])).casefold(),
                'directory',
            ) != 'directory' for index in range(len(parents))):
                safe_paths = False
                break
    hardlinks_safe = _validate_hardlinks(entries)
    concatenated = trailer_count > 1
    return CpioArchive(
        tuple(entries), last_trailer_end, total_size - last_trailer_end, total_size,
        safe_paths, hardlinks_safe, concatenated,
    )


def cpio_magic(path: str, *, compressed: bool = False) -> bool:
    try:
        with open(path, 'rb') as source:
            prefix = source.read(6)
        if compressed:
            decompressor = bz2.BZ2Decompressor()
            with open(path, 'rb') as source:
                prefix = decompressor.decompress(source.read(64 * 1024), max_length=6)
        _profile(prefix)
        return True
    except (OSError, EOFError, ValueError):
        return False


def _copy_range(source: BinaryIO, target: BinaryIO, start: int, end: int) -> None:
    source.seek(start)
    left = end - start
    while left:
        block = source.read(min(_COPY, left))
        if not block:
            raise CpioError('source CPIO changed during rewriting')
        target.write(block)
        left -= len(block)


def _safe_file_path(root: str, path: str) -> str:
    target = os.path.abspath(os.path.join(root, *path.split('/')))
    if os.path.commonpath((os.path.abspath(root), target)) != os.path.abspath(root):
        raise CpioError('member escapes the staging directory')
    return target


def _extract_regular_members(source_path: str, archive: CpioArchive, root: str) -> int:
    os.makedirs(root, exist_ok=True)
    count = 0
    with open(source_path, 'rb') as source:
        for entry in archive.entries:
            if not entry.regular or entry.links != 1 or not entry.size:
                continue
            if entry.path is None:
                raise CpioError('unsafe file member path')
            target = _safe_file_path(root, entry.path)
            parent = os.path.dirname(target)
            os.makedirs(parent, mode=0o700, exist_ok=True)
            cursor = os.path.abspath(root)
            for component in entry.path.split('/')[:-1]:
                cursor = os.path.join(cursor, component)
                if not stat.S_ISDIR(os.lstat(cursor).st_mode):
                    raise CpioError('member parent is not a private directory')
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, 'O_NOFOLLOW'):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(target, flags, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                source.seek(entry.data_offset)
                left = entry.size
                while left:
                    block = source.read(min(_COPY, left))
                    if not block:
                        raise CpioError('source CPIO changed during extraction')
                    output.write(block)
                    left -= len(block)
            os.chmod(target, entry.mode & 0o7777)
            os.utime(target, ns=(entry.mtime * 1000000000,) * 2)
            count += 1
    return count


def _payload_checksum(path: str) -> Tuple[int, int]:
    size = checksum = 0
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(_COPY), b''):
            size += len(block)
            checksum = (checksum + sum(block)) & 0xFFFFFFFF
    return size, checksum


def _encode_header(entry: CpioEntry, size: int, checksum: int) -> bytes:
    header = bytearray(entry.header)
    profile = entry.profile
    if profile.name in ('newc', 'crc-newc'):
        if size > 0xFFFFFFFF:
            raise CpioError('newc file exceeds its 32-bit size limit')
        header[54:62] = ('%08x' % size).encode()
        if profile.crc:
            header[102:110] = ('%08x' % checksum).encode()
    elif profile.name == 'odc':
        encoded = ('%011o' % size).encode()
        if len(encoded) != 11:
            raise CpioError('odc file exceeds its size limit')
        header[65:76] = encoded
    else:
        if size > 0xFFFFFFFF:
            raise CpioError('binary CPIO file exceeds its size limit')
        high, low = divmod(size, 0x10000)
        endian = cast(Literal['little', 'big'], profile.byteorder)
        header[22:24] = high.to_bytes(2, endian)
        header[24:26] = low.to_bytes(2, endian)
    return bytes(header)


def _copy_candidate(
    source_path: str, output_path: str, archive: CpioArchive, root: str,
    changed: Dict[str, PackResult],
) -> None:
    by_path = {entry.path: entry for entry in archive.entries if entry.regular}
    authorized: Dict[str, str] = {}
    for filepath, result in changed.items():
        if not result.replaced:
            continue
        relative = os.path.relpath(filepath, root).replace(os.sep, '/')
        if relative not in by_path:
            raise CpioError('inner packer result has no unique CPIO regular member')
        entry = by_path[relative]
        if entry.links != 1 or entry.path is None:
            raise CpioError('inner packer altered an ineligible CPIO member')
        authorized[relative] = filepath

    with open(source_path, 'rb') as source, open(output_path, 'wb') as target:
        for entry in archive.entries:
            member_file = authorized.get(entry.path or '')
            if member_file is None:
                _copy_range(source, target, entry.offset, entry.end)
                continue
            mode = os.lstat(member_file).st_mode
            if not stat.S_ISREG(mode):
                raise CpioError('inner packer output is not a regular file')
            size, checksum = _payload_checksum(member_file)
            header = _encode_header(entry, size, checksum)
            prefix_size = entry.data_offset - entry.offset
            source.seek(entry.offset)
            prefix = source.read(prefix_size)
            if len(prefix) != prefix_size or len(entry.header) != entry.profile.header_size:
                raise CpioError('source CPIO prefix changed during rewriting')
            target.write(header)
            target.write(prefix[len(entry.header):])
            with open(member_file, 'rb') as payload:
                for block in iter(lambda: payload.read(_COPY), b''):
                    target.write(block)
            padding = _aligned(size, entry.profile.alignment) - size
            if padding:
                target.write(b'\0' * padding)
        _copy_range(source, target, archive.trailer_padding_offset, archive.size)


def verify_cpio_pair(
    source_path: str, candidate_path: str, authorized_paths: Iterable[str] = (),
) -> bool:
    """Verify archive framing, member metadata/order and authorized payload edits."""
    source = parse_cpio(source_path)
    candidate = parse_cpio(candidate_path)
    if (source.concatenated or candidate.concatenated
            or len(source.entries) != len(candidate.entries)):
        return False
    authorized = set(authorized_paths)
    for original, updated in zip(source.entries, candidate.entries):
        if (original.profile != updated.profile or original.name_bytes != updated.name_bytes
                or original.kind != updated.kind or original.fields_without_payload !=
                updated.fields_without_payload):
            return False
        if original.trailer:
            if original.size != updated.size:
                return False
            continue
        if original.size == updated.size and original.digest == updated.digest:
            continue
        if (not original.regular or original.links != 1 or original.path not in authorized
                or updated.links != 1):
            return False
    return True


def validate_cpio(path: str) -> bool:
    parse_cpio(path)
    return True


def validate_cpbz2(path: str) -> bool:
    with bz2.open(path, 'rb') as source:
        # Inventory into a private file so every compressed block, final CRC and
        # CPIO record can be checked without holding the archive in memory.
        temp = _make_temp('.cpio')
        try:
            size = 0
            with open(temp, 'wb') as target:
                for block in iter(lambda: source.read(_COPY), b''):
                    size += len(block)
                    if size > 512 * 1024 * 1024:
                        raise CpioError('decoded CPIO exceeds the validation limit')
                    target.write(block)
            parse_cpio(temp)
            return True
        finally:
            _remove_quietly(temp)


def _decode_bzip2(
    filename: str, output: str, options: Dict[str, object],
) -> bool:
    from .archives import _extract_limits

    max_bytes, _ratio = _extract_limits(options)
    size = 0
    try:
        with bz2.open(filename, 'rb') as source, open(output, 'wb') as target:
            for block in iter(lambda: source.read(_COPY), b''):
                size += len(block)
                if size > max_bytes:
                    return False
                target.write(block)
    except (OSError, EOFError, ValueError):
        return False
    return size <= max_bytes


def _bzip2_matches_cpio(filename: str, expected_path: str) -> bool:
    """Check bzip2 integrity and require its decoded bytes to match the CPIO candidate."""
    expected_size = os.path.getsize(expected_path)
    size = 0
    try:
        with bz2.open(filename, 'rb') as source, open(expected_path, 'rb') as expected:
            while True:
                block = source.read(_COPY)
                if not block:
                    break
                size += len(block)
                if size > expected_size or expected.read(len(block)) != block:
                    return False
            return size == expected_size and not expected.read(1)
    except (OSError, EOFError, ValueError):
        return False


def repack_cpio(  # noqa: C901
    repacker: Any, filename: str, dest: str, f_insize: int, family: str,
    options: Dict[str, Any], on_progress: Optional[ProgressHook] = None,
) -> RepackSummary:
    """Deep-optimize a checked private CPIO tree, then publish via normal transactions."""
    from .archives import _notify, _extract_limits, _extract_over_limit
    from .candidates import make_temp_dir

    summary = RepackSummary(filepath=filename, total_insize=f_insize, total_outsize=f_insize)
    if _extract_over_limit(os.path.getsize(filename), f_insize, options, filename):
        return summary
    compressed = family == 'cpio.bz2'
    if options.get('_cpio_inner_disabled'):
        if not compressed:
            return summary
        fallback = pack_bz2(
            filename, dryrun=False,
            keep_if_larger=bool(options.get('keep_if_larger', True)),
            min_savings=options.get('min_savings'),
        )
        if fallback and fallback.replaced:
            summary.filepath = dest
            summary.total_outsize = fallback.outsize
        return summary
    cpio_input = _make_temp('.cpio') if compressed else filename
    unpack = make_temp_dir(prefix='filerepack-cpio-')
    candidate_cpio = _make_temp('.cpio')
    candidate = _make_temp('.cpbz2' if compressed else '.cpio')
    try:
        _notify(on_progress, 'extract', name=filename)
        if compressed and not _decode_bzip2(filename, cpio_input, options):
            return summary
        decoded_size = os.path.getsize(cpio_input)
        max_bytes, ratio = _extract_limits(options)
        if decoded_size > max_bytes:
            return summary
        # A high compression ratio blocks member extraction, but the old safe
        # outer-stream recompression route remains available for these inputs.
        if compressed and ratio and decoded_size > f_insize * ratio:
            fallback = pack_bz2(
                filename, dryrun=False,
                keep_if_larger=bool(options.get('keep_if_larger', True)),
                min_savings=options.get('min_savings'),
            )
            if fallback and fallback.replaced:
                summary.filepath = dest
                summary.total_outsize = fallback.outsize
            return summary
        max_entries = options.get('format_max_nodes', 100000)
        if not isinstance(max_entries, int):
            max_entries = 100000
        archive = parse_cpio(cpio_input, max_entries=max_entries)
        can_walk = archive.can_walk and options.get('deep_walking', True)
        if compressed and not can_walk:
            fallback = pack_bz2(
                filename, dryrun=False,
                keep_if_larger=bool(options.get('keep_if_larger', True)),
                min_savings=options.get('min_savings'),
            )
            if fallback and fallback.replaced:
                summary.filepath = dest
                summary.total_outsize = fallback.outsize
            return summary
        if can_walk:
            regular_bytes = sum(
                entry.size for entry in archive.entries
                if entry.regular and entry.links == 1
            )
            if regular_bytes > max_bytes or _extract_over_limit(
                regular_bytes, f_insize, options, filename,
            ):
                can_walk = False
        if can_walk:
            _extract_regular_members(cpio_input, archive, unpack)
            _notify(on_progress, 'files', current=0, total=sum(
                entry.regular and entry.links == 1 and entry.size > 0
                for entry in archive.entries
            ))
            walk_options = {**options, '_nested_member': True, '_cpio_inner_disabled': True}
            if options.get('dryrun'):
                walk_options['dryrun'] = False
            repacker._deep_walk(unpack, walk_options, summary, on_progress=on_progress)
        changed = {
            result.filepath: result for result in summary.results if result.replaced
        }
        _copy_candidate(cpio_input, candidate_cpio, archive, unpack, changed)
        allowed = [os.path.relpath(path, unpack).replace(os.sep, '/') for path in changed]
        if not verify_cpio_pair(cpio_input, candidate_cpio, allowed):
            raise CpioError('rewritten CPIO changed protected entries or payloads')
        if compressed:
            debug = bool(options.get('debug', False))
            if not _compress_file(candidate_cpio, candidate, 'bz2', debug):
                return summary
            if not _bzip2_matches_cpio(candidate, candidate_cpio):
                raise CpioError('bzip2 candidate does not match the verified CPIO output')
            verify = 'cpbz2'
        else:
            candidate = candidate_cpio
            verify = 'cpio'
        # Work files are private staging copies. Commit their verified candidate
        # even in dry-run so the caller can report projected archive savings.
        packed = _commit_output(
            candidate, dest, f_insize, verify=verify, lossless=False,
            dryrun=False, keep_if_larger=bool(options.get('keep_if_larger', True)),
            min_savings=options.get('min_savings'),
        )
        if packed is not None:
            summary.total_outsize = packed.outsize
            if packed.replaced:
                summary.filepath = dest
        return summary
    except (CpioError, OSError, ValueError) as exc:
        logging.warning('CPIO preservation skipped %s: %s', filename, exc)
        summary.results.clear()
        summary.inner_count = 0
        summary.inner_insize = 0
        summary.inner_outsize = 0
        if compressed and os.path.exists(filename):
            # Preserve the earlier outer-stream route for unusual but valid
            # CPIO profiles that the member writer cannot safely represent.
            fallback = pack_bz2(
                filename, dryrun=False,
                keep_if_larger=bool(options.get('keep_if_larger', True)),
                min_savings=options.get('min_savings'),
            )
            if fallback and fallback.replaced:
                summary.filepath = dest
                summary.total_outsize = fallback.outsize
        return summary
    finally:
        if compressed and cpio_input != filename:
            _remove_quietly(cpio_input)
        _remove_quietly(unpack)
        if candidate_cpio != candidate:
            _remove_quietly(candidate_cpio)
        _remove_quietly(candidate)
