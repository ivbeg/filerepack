"""Exact CPIO bytes and publication policies for bzip2-wrapped CPIO archives."""

import bz2
import json
import os
import zipfile

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker
from filerepack.__main__ import app
from filerepack.consts import ARCHIVE_EXTS, STANDALONE_EXTS, SUPPORTED_EXTS
from filerepack.formats import identify_filename, is_supported_filename, matches_ext_filter
from filerepack.tools import resolve_szip, resolve_tool
from filerepack.verification import validate_output, verify_preservation


def _newc_entry(name, payload=b'', *, mode=0o100640, inode=1, links=1):
    name_bytes = name.encode() + b'\0'
    fields = (inode, mode, 501, 20, links, 1234567890, len(payload),
              0, 0, 0, 0, len(name_bytes), 0)
    header = b'070701' + ''.join(f'{value:08x}' for value in fields).encode() + name_bytes
    return header + b'\0' * (-len(header) % 4) + payload + b'\0' * (-len(payload) % 4)


@pytest.fixture(scope='module')
def cpio_payload():
    # A real newc archive with regular, directory, symlink and hard-link entries.
    raw = (
        _newc_entry('data', mode=0o40750) +
        _newc_entry('data/payload.bin', bytes(range(256)) * 4000, inode=2) +
        _newc_entry('shortcut', b'data/payload.bin', mode=0o120777, inode=3) +
        _newc_entry('first-link', inode=4, links=2) +
        _newc_entry('second-link', b'linked bytes', inode=4, links=2) +
        _newc_entry('TRAILER!!!', mode=0, inode=0)
    )
    return raw + b'\0' * (-len(raw) % 512)


@pytest.fixture
def cpbz2_file(tmp_path, cpio_payload):
    path = tmp_path / 'archive.cpbz2'
    path.write_bytes(bz2.compress(cpio_payload, compresslevel=1))
    return path


@pytest.mark.parametrize('name', ['archive.cpbz2', 'ARCHIVE.CPBZ2', 'archive.cpio.bz2'])
def test_identification_and_filters(name):
    kind = identify_filename(name)
    assert kind is not None and kind.is_archive and kind.family == 'cpio.bz2'
    assert is_supported_filename(name)
    assert matches_ext_filter(name, ['bz2'])
    if name.lower().endswith('.cpbz2'):
        assert matches_ext_filter(name, ['cpbz2'])
    assert 'cpbz2' in SUPPORTED_EXTS and 'cpbz2' in ARCHIVE_EXTS
    assert 'cpbz2' not in STANDALONE_EXTS
    raw_kind = identify_filename('archive.cpio')
    assert raw_kind is not None and raw_kind.family == 'cpio'


@pytest.mark.parametrize('external_tool', [False, True])
def test_recompression_keeps_cpio_and_filesystem_metadata(
    cpbz2_file, cpio_payload, monkeypatch, external_tool,
):
    tool = resolve_tool('bzip2') if external_tool else None
    if external_tool and not tool:
        pytest.skip('bzip2 executable unavailable')
    monkeypatch.setattr('filerepack.streams.resolve_tool', lambda key: tool)
    original = cpbz2_file.read_bytes()
    cpbz2_file.chmod(0o640)
    os.utime(cpbz2_file, (1234567890, 1234567890))
    before = cpbz2_file.stat()
    summary = FileRepacker().repack(str(cpbz2_file))
    assert summary.total_outsize < len(original)
    assert summary.filepath == str(cpbz2_file) and summary.inner_count == 0
    assert cpbz2_file.read_bytes().startswith(b'BZh9')
    assert cpbz2_file.stat().st_size < len(original)
    assert bz2.decompress(cpbz2_file.read_bytes()) == cpio_payload
    assert cpbz2_file.stat().st_mtime_ns == before.st_mtime_ns
    assert cpbz2_file.stat().st_mode == before.st_mode
    assert list(cpbz2_file.parent.iterdir()) == [cpbz2_file]


@pytest.mark.parametrize('options', [{'dryrun': True}, {'min_savings': 100}])
def test_dryrun_and_savings_retain_source(cpbz2_file, options):
    original = cpbz2_file.read_bytes()
    FileRepacker().repack(str(cpbz2_file), options=options)
    assert cpbz2_file.read_bytes() == original


def test_already_optimized_stream_is_retained(cpbz2_file, cpio_payload, monkeypatch):
    monkeypatch.setattr('filerepack.streams.resolve_tool', lambda key: None)
    original = bz2.compress(cpio_payload, compresslevel=9)
    cpbz2_file.write_bytes(original)
    summary = FileRepacker().repack(str(cpbz2_file))
    assert summary.total_outsize == len(original)
    assert cpbz2_file.read_bytes() == original


def test_distinct_output_keeps_original(cpbz2_file, cpio_payload):
    original = cpbz2_file.read_bytes()
    output = cpbz2_file.parent / 'out' / 'repacked.cpbz2'
    summary = FileRepacker().repack(str(cpbz2_file), outfile=str(output))
    assert summary.filepath == str(output)
    assert cpbz2_file.read_bytes() == original
    assert output.stat().st_size < len(original)
    assert bz2.decompress(output.read_bytes()) == cpio_payload


@pytest.mark.parametrize('fault', ['truncated', 'garbage'])
def test_invalid_input_is_not_replaced(cpbz2_file, fault):
    original = cpbz2_file.read_bytes()[:-8] if fault == 'truncated' else b'BZh9garbage'
    cpbz2_file.write_bytes(original)
    summary = FileRepacker().repack(str(cpbz2_file))
    assert summary.total_insize == summary.total_outsize == len(original)
    assert cpbz2_file.read_bytes() == original


@pytest.mark.parametrize('candidate', [b'BZh9garbage', bz2.compress(b'changed CPIO bytes')])
def test_invalid_or_changed_candidate_is_not_published(cpbz2_file, monkeypatch, candidate):
    original = cpbz2_file.read_bytes()
    monkeypatch.setattr('filerepack.streams.resolve_tool', lambda key: '/fake/bzip2')

    def faulty_encoder(command, output, debug):
        with open(output, 'wb') as target:
            target.write(candidate)
        return True

    monkeypatch.setattr('filerepack.streams._run_to_file', faulty_encoder)
    summary = FileRepacker().repack(str(cpbz2_file))
    assert summary.total_outsize == len(original)
    assert cpbz2_file.read_bytes() == original


def test_validator_alias_requires_full_decode_and_exact_payload(cpbz2_file, cpio_payload):
    candidate = cpbz2_file.parent / 'candidate.cpbz2'
    candidate.write_bytes(bz2.compress(cpio_payload, compresslevel=9))
    assert validate_output(str(candidate), 'cpbz2').ok
    assert verify_preservation(str(cpbz2_file), str(candidate), 'cpbz2')
    candidate.write_bytes(bz2.compress(b'different archive'))
    assert not verify_preservation(str(cpbz2_file), str(candidate), 'cpbz2')
    candidate.write_bytes(b'BZh9')
    assert not validate_output(str(candidate), 'cpbz2').ok


@pytest.mark.parametrize('command,extension', [('repack', None), ('bulk', 'cpbz2'),
                                              ('bulk', 'bz2')])
def test_cli_and_bulk_recompression(cpbz2_file, cpio_payload, command, extension):
    original = cpbz2_file.read_bytes()
    args = ['repack', str(cpbz2_file), '--json', '--no-progress']
    if command == 'bulk':
        args = ['bulk', str(cpbz2_file.parent), '--include-ext', extension,
                '--jobs', '1', '--json']
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)
    assert cpbz2_file.stat().st_size < len(original)
    assert bz2.decompress(cpbz2_file.read_bytes()) == cpio_payload


def test_nested_cpbz2_retains_member_name_and_cpio_bytes(tmp_path, cpio_payload):
    if not resolve_szip():
        pytest.skip('7zz/7z required for archive rewriting')
    path = tmp_path / 'parent.zip'
    original = bz2.compress(cpio_payload, compresslevel=1)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('backup.cpbz2', original)
    summary = FileRepacker().repack(str(path))
    assert summary.inner_count == 1
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ['backup.cpbz2']
        candidate = archive.read('backup.cpbz2')
    assert len(candidate) < len(original)
    assert bz2.decompress(candidate) == cpio_payload
