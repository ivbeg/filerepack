"""Record access, exact capture preservation and WARC publication regressions."""

import gzip
import hashlib
import io
import json
import os
import threading
import zlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, candidates, verification
from filerepack.__main__ import app
from filerepack.containers import pack_members
from filerepack.dispatch import dispatch_packer
from filerepack.formats import filename_exts, identify_filename, matches_ext_filter
from filerepack.models import RepackOptions, RepackSummary
from filerepack.streams import pack_gzip
from filerepack.warc import pack_warc, validate_warc_gzip, warc_fingerprint


def _record(payload=b'captured content\r\n' * 10000, *, version=b'1.1', kind=b'resource',
            extra=b''):
    return (
        b'WARC/' + version + b'\r\nWARC-Type: ' + kind +
        b'\r\nWARC-Record-ID: <urn:uuid:01234567-89ab-cdef-0123-456789abcdef>\r\n'
        b'WARC-Date: 2026-10-05T10:00:00Z\r\n'
        b'WARC-Target-URI: https://example.org/\r\n'
        b'WARC-Block-Digest: sha1:' + hashlib.sha1(payload).hexdigest().encode() + b'\r\n' +
        extra + b'Content-Length: ' + str(len(payload)).encode() +
        b'\r\n\r\n' + payload + b'\r\n\r\n'
    )


def _compress(records, level=1):
    return b''.join(gzip.compress(record, compresslevel=level, mtime=0) for record in records)


def _members(data):
    """Independent decoder proves member boundaries and records are seekable."""
    records = []
    offsets = []
    while data:
        offsets.append(data)
        decoder = zlib.decompressobj(31)
        records.append(decoder.decompress(data) + decoder.flush())
        assert decoder.eof
        data = decoder.unused_data
    # A reader starting at every member offset must independently decode a record.
    for remaining, record in zip(offsets, records):
        assert zlib.decompress(remaining, 31) == record
    return records


@pytest.fixture
def captures():
    response = (
        b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Encoding: gzip\r\n\r\n' +
        gzip.compress(b'web page', mtime=0) + bytes(range(256)) * 1000
    )
    return [
        _record(extra=b'X-Unknown: caf\xc3\xa9\r\n\tfolded value\r\n', version=b'1.0'),
        _record(response, kind=b'response'),
        _record(b'HTTP/1.1 200 OK\r\n\r\n', kind=b'revisit',
                extra=b'WARC-Refers-To: <urn:uuid:other>\r\n'),
        _record(b'', kind=b'metadata'),
    ]


def test_recompression_keeps_exact_captures_and_separate_members(tmp_path, captures):
    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    path.write_bytes(original)
    result = FileRepacker().repack(str(path))
    assert result.results[0].replaced
    assert len(path.read_bytes()) < len(original)
    assert gzip.decompress(path.read_bytes()) == b''.join(captures)
    assert _members(path.read_bytes()) == captures
    assert result.results[0].details['records'] == len(captures)
    validate_warc_gzip(str(path))


@pytest.mark.parametrize('layout', ['whole-file', 'split-record', 'groups'])
def test_noncanonical_source_layout_becomes_one_record_per_member(tmp_path, captures, layout):
    path = tmp_path / 'archive.warc.gz'
    raw = b''.join(captures)
    if layout == 'whole-file':
        original = gzip.compress(raw, compresslevel=1, mtime=0)
    elif layout == 'split-record':
        original = _compress([raw[:7], raw[7:101], raw[101:]])
    else:
        original = _compress([b''.join(captures[:2]), b''.join(captures[2:])])
    path.write_bytes(original)
    result = pack_warc(str(path), keep_if_larger=False)
    assert result.replaced
    assert _members(path.read_bytes()) == captures


@pytest.mark.parametrize('name', ['archive.warc.gz', 'ARCHIVE.WARC.GZ', 'archive.gz'])
def test_detection_and_generic_gzip_use_warc_handler(tmp_path, name, captures):
    path = tmp_path / name
    path.write_bytes(_compress(captures))
    kind = identify_filename(name, str(path))
    assert not kind.is_archive and kind.packer == 'warc'
    assert pack_gzip(str(path)).replaced
    assert _members(path.read_bytes()) == captures


def test_warc_extension_filters_cover_plain_and_compound_names():
    for name in ('archive.warc', 'archive.WARC.GZ'):
        assert matches_ext_filter(name, ['warc'])
    assert matches_ext_filter('archive.warc.gz', ['gz'])
    assert matches_ext_filter('archive.warc.gz', ['warc.gz'])
    assert filename_exts('archive.warc.gz') == ['warc.gz', 'warc', 'gz']


def test_unsupported_warc_in_generic_gzip_is_not_flattened(tmp_path):
    path = tmp_path / 'archive.gz'
    raw = _record(version=b'2.0')
    original = _compress([raw, raw])
    path.write_bytes(original)
    assert identify_filename(str(path), str(path)).packer == 'warc'
    assert not pack_gzip(str(path)).replaced
    assert path.read_bytes() == original


def test_folded_length_and_many_unknown_fields_keep_exact_bytes(tmp_path):
    path = tmp_path / 'archive.warc.gz'
    raw = _record(extra=b'X-Repeated: keep\r\n' * 10000).replace(
        b'Content-Length: 180000', b'content-length:\r\n\t180000',
    )
    path.write_bytes(_compress([raw]))
    assert pack_warc(str(path)).replaced
    assert _members(path.read_bytes()) == [raw]


@pytest.mark.parametrize('direct', [False, True])
def test_plain_warc_converts_to_planned_gzip_name(tmp_path, captures, direct):
    path = tmp_path / 'archive.warc'
    path.write_bytes(b''.join(captures))
    result = pack_warc(str(path)) if direct else FileRepacker().repack(str(path))
    output = tmp_path / 'archive.warc.gz'
    assert Path(result.filepath) == output
    assert not path.exists()
    assert _members(output.read_bytes()) == captures


@pytest.mark.parametrize('output_name', ['other.warc', 'other.warc.gz'])
def test_plain_distinct_output_and_backup_preserve_original(tmp_path, output_name, captures):
    source = tmp_path / 'archive.warc'
    raw = b''.join(captures)
    source.write_bytes(raw)
    summary = FileRepacker().repack(
        str(source), str(tmp_path / output_name), RepackOptions(backup=True),
    )
    output = tmp_path / (output_name if output_name.endswith('.gz') else output_name + '.gz')
    assert Path(summary.filepath) == output
    assert source.read_bytes() == raw
    assert (tmp_path / 'archive.warc.bak').read_bytes() == raw
    assert _members(output.read_bytes()) == captures


def test_plain_distinct_dryrun_ignores_source_sibling_collision(tmp_path, captures):
    source = tmp_path / 'archive.warc'
    source.write_bytes(b''.join(captures))
    sibling = tmp_path / 'archive.warc.gz'
    sibling.write_bytes(b'an existing compressed archive')
    output = tmp_path / 'other.warc.gz'
    result = FileRepacker().repack(str(source), str(output), RepackOptions(dryrun=True))
    assert result.results[0].outsize < result.results[0].insize
    assert source.read_bytes() == b''.join(captures)
    assert sibling.read_bytes() == b'an existing compressed archive'
    assert not output.exists()


@pytest.mark.parametrize('direct', [False, True])
@pytest.mark.parametrize('compressed', [False, True])
def test_dryrun_keeps_source_and_does_not_create_output(tmp_path, captures, compressed, direct):
    path = tmp_path / ('archive.warc.gz' if compressed else 'archive.warc')
    original = _compress(captures) if compressed else b''.join(captures)
    path.write_bytes(original)
    if direct:
        result = pack_warc(str(path), dryrun=True)
    else:
        result = FileRepacker().repack(str(path), options=RepackOptions(dryrun=True)).results[0]
    assert not result.replaced and result.outsize < result.insize
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('direct', [False, True])
def test_plain_conversion_refuses_destination_collision(tmp_path, captures, direct):
    path = tmp_path / 'archive.warc'
    path.write_bytes(b''.join(captures))
    output = tmp_path / 'archive.warc.gz'
    output.write_bytes(b'existing output')
    with pytest.raises(FileExistsError):
        if direct:
            pack_warc(str(path))
        else:
            FileRepacker().repack(str(path))
    assert output.read_bytes() == b'existing output'
    assert path.read_bytes() == b''.join(captures)


def test_conversion_disabled_and_nested_plain_members_are_unchanged(tmp_path, captures):
    path = tmp_path / 'archive.warc'
    raw = b''.join(captures)
    path.write_bytes(raw)
    summary = FileRepacker().repack(str(path), options=RepackOptions(convert_container=False))
    assert not summary.results[0].replaced
    assert 'disabled' in summary.results[0].reason
    packed = pack_members({'capture': str(path)})
    assert not packed['capture'].shrank
    repacker = FileRepacker()
    nested = RepackSummary(filepath='container.zip')
    repacker._process_walk_item(str(path), identify_filename(str(path)), {}, nested)
    assert path.read_bytes() == raw and not path.with_suffix('.warc.gz').exists()


def test_nested_compressed_warc_keeps_member_path(tmp_path, captures):
    path = tmp_path / 'archive.warc.gz'
    path.write_bytes(_compress(captures))
    result = pack_members({'capture': str(path)})
    assert result['capture'].shrank and result['capture'].path == str(path)
    assert _members(path.read_bytes()) == captures


@pytest.mark.parametrize('suffix', ['.warc.gz.cdx', '.warc.cdxj', '.cdx.gz', '.cdxj.gz'])
def test_adjacent_indexes_skip_inplace_but_allow_distinct_output(tmp_path, captures, suffix):
    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    path.write_bytes(original)
    index = tmp_path / ('archive' + suffix)
    index.write_bytes(b'old offsets')
    summary = FileRepacker().repack(str(path))
    assert not summary.results[0].replaced and 'index' in summary.results[0].reason
    assert path.read_bytes() == original and index.read_bytes() == b'old offsets'
    output = tmp_path / 'other.warc.gz'
    summary = FileRepacker().repack(str(path), str(output))
    assert summary.results[0].replaced and _members(output.read_bytes()) == captures
    assert path.read_bytes() == original and index.read_bytes() == b'old offsets'


def test_indexed_destination_is_not_overwritten_on_skip(tmp_path, captures):
    source, output = tmp_path / 'archive.warc.gz', tmp_path / 'other.warc.gz'
    source.write_bytes(_compress(captures))
    output.write_bytes(b'existing indexed capture')
    index = tmp_path / 'other.cdx'
    index.write_bytes(b'existing index')
    summary = FileRepacker().repack(str(source), str(output), RepackOptions(overwrite=True))
    assert not summary.results[0].replaced
    assert output.read_bytes() == b'existing indexed capture'
    assert index.read_bytes() == b'existing index'


def test_minimum_savings_and_larger_policy_leave_original(tmp_path, captures):
    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    path.write_bytes(original)
    result = pack_warc(str(path), min_savings=100)
    assert not result.replaced and 'required' in result.reason
    assert path.read_bytes() == original
    # A tiny whole-file member is smaller than many independent members.
    tiny = [_record(b'', kind=b'metadata')] * 10
    original = gzip.compress(b''.join(tiny), compresslevel=9, mtime=0)
    path.write_bytes(original)
    result = pack_warc(str(path))
    assert not result.replaced and 'No size reduction' in result.reason
    assert path.read_bytes() == original


_BAD_RECORDS = [
    b'', b'WARC/1.1\r\n', _record()[:-1], _record().replace(b'WARC/1.1', b'WARC/2.0'),
    _record().replace(b'Content-Length: 180000', b'Content-Length: -1'),
    _record().replace(b'Content-Length:', b'Content-Length: 1\r\nContent-Length:'),
    _record().replace(b'WARC-Type:', b'Bad Name:'),
    _record().replace(b'WARC-Date:', b'WARC-Type:'),
    _record().replace(b'\r\n', b'\n'),
    _record().replace(b'Content-Length: 180000', b'Content-Length: 179999'),
    _record().replace(b'WARC-Type: resource', b'WARC-Type: res\x00ource'),
    _record() + b'trailing garbage',
]


@pytest.mark.parametrize('raw', _BAD_RECORDS, ids=range(len(_BAD_RECORDS)))
def test_invalid_records_never_publish_or_leak_scratch(tmp_path, monkeypatch, raw):
    path = tmp_path / 'archive.warc.gz'
    original = gzip.compress(raw, mtime=0)
    path.write_bytes(original)
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(candidates, 'TEMP_PATH', str(scratch))
    result = pack_warc(str(path), keep_if_larger=False)
    assert not result.replaced
    assert path.read_bytes() == original
    assert list(scratch.iterdir()) == []


@pytest.mark.parametrize('fault', ['crc', 'size', 'truncated', 'trailing', 'second-member'])
def test_gzip_corruption_is_detected_in_all_members(tmp_path, captures, fault):
    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    if fault == 'crc':
        original = original[:-8] + bytes([original[-8] ^ 1]) + original[-7:]
    elif fault == 'size':
        original = original[:-4] + b'\0' * 4
    elif fault == 'truncated':
        original = original[:-1]
    elif fault == 'trailing':
        original += b'\0' * 16
    else:
        original += b'\x1f\x8b'
    path.write_bytes(original)
    assert not pack_warc(str(path), keep_if_larger=False).replaced
    assert path.read_bytes() == original
    assert not verification.validate_output(str(path), 'warc').ok


def test_verifier_refuses_multiple_records_in_one_member_or_changed_bytes(tmp_path, captures):
    source, candidate = tmp_path / 'source.warc.gz', tmp_path / 'candidate.warc.gz'
    original = _compress(captures)
    source.write_bytes(original)
    candidate.write_bytes(gzip.compress(b''.join(captures), mtime=0))
    assert not verification.validate_output(str(candidate), 'warc').ok
    candidate.write_bytes(_compress([_record(b'changed content')]))
    assert verification.validate_output(str(candidate), 'warc').ok
    assert candidates.commit_output(str(candidate), str(source), len(original),
                                    verify='warc', lossless=True) is None
    assert source.read_bytes() == original and not candidate.exists()


@pytest.mark.parametrize('limit,value', [
    ('format_max_decoded_bytes', 128), ('format_max_memory_bytes', 1024),
    ('format_max_nodes', 1), ('format_max_scratch_bytes', 1), ('format_timeout', 0.001),
])
def test_budget_exhaustion_keeps_source(tmp_path, captures, monkeypatch, limit, value):
    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    path.write_bytes(original)
    if limit == 'format_timeout':
        # Make the deadline deterministic without a wall-clock sleep.
        from filerepack.format_support import Budget
        check = Budget.check

        def expired(self):
            self.started -= 1
            check(self)

        monkeypatch.setattr(Budget, 'check', expired)
    result = dispatch_packer('warc', str(path), {limit: value})
    assert not result.replaced and ('budget' in result.reason or 'memory' in result.reason)
    assert path.read_bytes() == original


def test_cancellation_keeps_source(tmp_path, captures):
    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    path.write_bytes(original)
    event = threading.Event()
    event.set()
    result = dispatch_packer('warc', str(path), {'_cancel_event': event})
    assert not result.replaced and 'cancelled' in result.reason
    assert path.read_bytes() == original


def test_cancellation_during_candidate_validation_keeps_source_and_resets_context(
    tmp_path, monkeypatch, captures,
):
    from filerepack import warc

    path = tmp_path / 'archive.warc.gz'
    original = _compress(captures)
    path.write_bytes(original)
    event = threading.Event()
    validate = warc.validate_warc_gzip

    def cancelled(candidate):
        event.set()
        validate(candidate)

    monkeypatch.setattr(warc, 'validate_warc_gzip', cancelled)
    result = pack_warc(str(path), _cancel_event=event)
    assert not result.replaced and 'cancelled' in result.reason
    assert path.read_bytes() == original
    monkeypatch.setattr(warc, 'validate_warc_gzip', validate)
    assert pack_warc(str(path)).replaced


def test_header_bound_and_huge_content_length_are_refused(tmp_path):
    path = tmp_path / 'archive.warc.gz'
    for raw in (_record(b'', extra=b'X-Long: ' + b'a' * 65536 + b'\r\n'),
                _record().replace(b'180000', b'99999999999999999999')):
        original = gzip.compress(raw, mtime=0)
        path.write_bytes(original)
        assert not pack_warc(str(path), keep_if_larger=False).replaced
        assert path.read_bytes() == original


def test_file_metadata_is_preserved(tmp_path, captures):
    path = tmp_path / 'archive.warc.gz'
    path.write_bytes(_compress(captures))
    path.chmod(0o640)
    os.utime(path, (1234567890, 1234567890))
    before = path.stat()
    assert pack_warc(str(path)).replaced
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert path.stat().st_mode == before.st_mode


def test_cli_repack_and_bulk_include_warc(tmp_path, captures):
    path = tmp_path / 'archive.warc.gz'
    path.write_bytes(_compress(captures))
    runner = CliRunner()
    result = runner.invoke(app, ['repack', str(path), '--no-progress'])
    assert result.exit_code == 0, result.output
    assert _members(path.read_bytes()) == captures
    path.write_bytes(_compress(captures))
    result = runner.invoke(app, ['bulk', str(tmp_path), '--include-ext', 'warc',
                                 '--jobs', '1', '--json'])
    assert result.exit_code == 0, result.output
    assert _members(path.read_bytes()) == captures
    assert json.loads(result.output)


def test_warcio_can_read_and_seek_each_recompressed_record(tmp_path, captures):
    archiveiterator = pytest.importorskip('warcio.archiveiterator')
    path = tmp_path / 'archive.warc.gz'
    path.write_bytes(_compress(captures))
    assert pack_warc(str(path)).replaced
    with path.open('rb') as stream:
        records = list(archiveiterator.ArchiveIterator(stream, no_record_parse=True))
    assert len(records) == len(captures)
    for raw in _members(path.read_bytes()):
        compressed = gzip.compress(raw, mtime=0)
        with io.BytesIO(compressed) as stream:
            iterator = archiveiterator.ArchiveIterator(stream, no_record_parse=True)
            record = next(iterator)
            assert record.rec_headers.get_header('WARC-Target-URI') == 'https://example.org/'
            record.raw_stream.read()
            assert next(iterator, None) is None
    assert warc_fingerprint(str(path))[1] == len(captures)
