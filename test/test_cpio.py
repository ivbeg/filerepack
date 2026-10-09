"""Preserving CPIO member optimization across supported header profiles."""

import bz2
import json
from pathlib import Path

import pytest

from filerepack import FileRepacker
from filerepack.cpio import parse_cpio, verify_cpio_pair
from filerepack.formats import identify_filename
from filerepack.verification import validate_output


def _newc_entry(name, payload=b'', *, profile='newc', mode=0o100640, inode=1, links=1):
    name_bytes = name.encode() + b'\0'
    crc = sum(payload) & 0xFFFFFFFF if profile == 'crc-newc' else 0
    fields = (inode, mode, 501, 20, links, 1234567890, len(payload),
              0, 0, 0, 0, len(name_bytes), crc)
    magic = b'070702' if profile == 'crc-newc' else b'070701'
    header = magic + ''.join(f'{value:08x}' for value in fields).encode() + name_bytes
    return header + b'\0' * (-len(header) % 4) + payload + b'\0' * (-len(payload) % 4)


def _odc_entry(name, payload=b'', *, mode=0o100640, inode=1):
    name_bytes = name.encode() + b'\0'
    values = (1, inode, mode, 501, 20, 1, 0, 1234567890,
              len(name_bytes), len(payload))
    widths = (6, 6, 6, 6, 6, 6, 6, 11, 6, 11)
    header = b'070707' + b''.join(
        f'{value:0{width}o}'.encode() for value, width in zip(values, widths)
    ) + name_bytes
    return header + payload


def _binary_entry(name, payload=b'', *, byteorder='big', mode=0o100640, inode=1):
    name_bytes = name.encode() + b'\0'
    size_high, size_low = divmod(len(payload), 0x10000)
    mtime_high, mtime_low = divmod(1234567890, 0x10000)
    words = (0x71C7, 1, inode, mode, 501, 20, 1, 0, mtime_high,
             mtime_low, len(name_bytes), size_high, size_low)
    header = b''.join(value.to_bytes(2, byteorder) for value in words)
    framed_name = header + name_bytes
    framed_name += b'\0' * (-len(framed_name) % 2)
    return framed_name + payload + b'\0' * (-len(payload) % 2)


def _archive(profile, name, payload):
    if profile in ('newc', 'crc-newc'):
        def make_entry(member, data=b'', mode=0o100640):
            return _newc_entry(member, data, profile=profile, mode=mode)
    elif profile == 'odc':
        make_entry = _odc_entry
    else:
        byteorder = 'big' if profile == 'binary-be' else 'little'
        def make_entry(member, data=b'', mode=0o100640):
            return _binary_entry(member, data, byteorder=byteorder, mode=mode)
    raw = make_entry(name, payload) + make_entry('TRAILER!!!', mode=0)
    return raw + b'\0' * (-len(raw) % 512)


@pytest.mark.parametrize('profile', ['newc', 'crc-newc', 'odc', 'binary-be', 'binary-le'])
def test_deep_member_optimization_preserves_cpio_profile_and_metadata(tmp_path, profile):
    pretty_json = json.dumps(
        {'items': ['compressible repeated text ' * 10 for _ in range(80)]}, indent=2,
    ).encode()
    path = tmp_path / 'archive.cpio'
    path.write_bytes(_archive(profile, 'data/config.json', pretty_json))
    original = path.read_bytes()

    summary = FileRepacker().repack(str(path))

    assert summary.results and summary.inner_count == 1
    assert summary.total_outsize < len(original)
    assert validate_output(str(path), 'cpio').ok
    before = parse_cpio_from_bytes(tmp_path, original)
    after = parse_cpio(str(path))
    assert [entry.name for entry in before.entries] == [entry.name for entry in after.entries]
    assert before.entries[0].fields_without_payload == after.entries[0].fields_without_payload
    assert before.entries[0].mode == after.entries[0].mode
    assert before.entries[0].mtime == after.entries[0].mtime
    assert after.entries[0].size < before.entries[0].size
    assert verify_cpio_pair(str(tmp_path / 'source.cpio'), str(path), ['data/config.json'])


def parse_cpio_from_bytes(tmp_path, payload):
    path = tmp_path / 'source.cpio'
    path.write_bytes(payload)
    return parse_cpio(str(path))


def test_cpbz2_optimizes_members_and_keeps_bzip2_wrapper(tmp_path):
    payload = json.dumps({'values': ['same content ' * 20 for _ in range(40)]}, indent=2).encode()
    raw = _archive('crc-newc', 'config.json', payload)
    path = tmp_path / 'backup.cpbz2'
    path.write_bytes(bz2.compress(raw, compresslevel=1))
    original_size = path.stat().st_size

    summary = FileRepacker().repack(str(path))

    assert summary.inner_count == 1
    assert path.read_bytes().startswith(b'BZh')
    assert path.stat().st_size < original_size
    decoded = tmp_path / 'decoded.cpio'
    decoded.write_bytes(bz2.decompress(path.read_bytes()))
    updated = parse_cpio(str(decoded))
    assert updated.entries[0].size < len(payload)
    assert validate_output(str(path), 'cpbz2').ok


def test_cpbz2_candidate_must_match_the_verified_member_output(tmp_path, monkeypatch):
    payload = json.dumps(
        {'values': [f'unique entry {index}' for index in range(250)]}, indent=2,
    ).encode()
    raw = _archive('newc', 'config.json', payload)
    path = tmp_path / 'backup.cpbz2'
    path.write_bytes(bz2.compress(raw, compresslevel=1))
    bad_candidate = bz2.compress(_archive('newc', 'other.json', b'{"different":true}'))

    def faulty_compressor(source, output, codec, debug):
        Path(output).write_bytes(bad_candidate)
        return True

    monkeypatch.setattr('filerepack.cpio._compress_file', faulty_compressor)
    FileRepacker().repack(str(path), options={'max_extract_ratio': 0})

    assert bz2.decompress(path.read_bytes()) == raw


def test_unsafe_path_skips_member_extraction(tmp_path):
    payload = b'{\n  "safe": true\n}'
    path = tmp_path / 'unsafe.cpio'
    original = _archive('newc', '../outside.json', payload)
    path.write_bytes(original)

    summary = FileRepacker().repack(str(path))

    assert summary.total_outsize == len(original)
    assert path.read_bytes() == original
    assert not (tmp_path / 'outside.json').exists()


def test_links_and_special_records_remain_untouched_during_member_edit(tmp_path):
    payload = json.dumps({'values': ['repeat ' * 30 for _ in range(30)]}, indent=2).encode()
    entries = (
        _newc_entry('item.json', payload, inode=2) +
        _newc_entry('shortcut', b'item.json', mode=0o120777, inode=3) +
        _newc_entry('hard-one', b'linked bytes', inode=4, links=2) +
        _newc_entry('hard-two', inode=4, links=2) +
        _newc_entry('TRAILER!!!', mode=0, inode=0)
    )
    original = entries + b'\0' * (-len(entries) % 512)
    source_path = tmp_path / 'source.cpio'
    path = tmp_path / 'links.cpio'
    source_path.write_bytes(original)
    path.write_bytes(original)

    summary = FileRepacker().repack(str(path))

    before = parse_cpio(str(source_path))
    after = parse_cpio(str(path))
    assert summary.inner_count == 1
    assert [entry.name for entry in before.entries] == [entry.name for entry in after.entries]
    for index in (1, 2, 3):
        assert (before.entries[index].fields_without_payload ==
                after.entries[index].fields_without_payload)
        assert before.entries[index].digest == after.entries[index].digest
    assert verify_cpio_pair(str(source_path), str(path), ['item.json'])


def test_nested_cpio_is_not_reentered(tmp_path):
    payload = b'{\n "nested": true\n}'
    nested = _archive('newc', 'inside.json', payload)
    parent = tmp_path / 'parent.cpio'
    parent.write_bytes(_archive('newc', 'nested.cpio', nested))
    original = parent.read_bytes()

    FileRepacker().repack(str(parent))

    assert parent.read_bytes() == original


def test_generic_bz2_is_identified_by_cpio_magic(tmp_path):
    path = tmp_path / 'archive.bz2'
    path.write_bytes(bz2.compress(_archive('newc', 'file.bin', b'data')))

    kind = identify_filename(path.name, peek_path=str(path))

    assert kind is not None and kind.family == 'cpio.bz2'
