"""Identity, byte preservation and transaction gates for compiled NIB archives."""

import os
import struct
import threading
import zipfile

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.format_support import Budget, FormatLimits, format_scope
from filerepack.formats import identify_filename, matches_ext_filter
from filerepack.nib import NibArchive, nib_fingerprint, pack_nib
from filerepack.tools import resolve_szip
from filerepack.verification import validate_output, verify_preservation
from test.nib_fixtures import archive_bytes, nib_bytes, nib_parts


def parse(data):
    return NibArchive(data, Budget(FormatLimits()))


def test_routes_exports_and_independent_validator(tmp_path, monkeypatch):
    from filerepack.codecs import pack_nib as codec_packer
    from filerepack.repack import pack_nib as repack_packer

    assert codec_packer is repack_packer is pack_nib
    assert identify_filename('View.NIB').packer == 'nib'
    assert matches_ext_filter('View.NIB', ['nib'])
    source = tmp_path / 'view.nib'
    source.write_bytes(nib_bytes())
    monkeypatch.setattr(NibArchive, 'compact', lambda _: pytest.fail('verifier called writer'))
    assert validate_output(str(source), 'nib').ok
    assert verify_preservation(str(source), str(source), 'nib')


@pytest.mark.parametrize('padded', [False, True])
@pytest.mark.parametrize('coder', [9, 10])
def test_compaction_preserves_all_types_bits_order_metadata_and_identity(tmp_path, padded, coder):
    original = nib_bytes(padded, coder)
    source = tmp_path / 'view.nib'
    source.write_bytes(original)
    result = pack_nib(str(source))
    assert result.replaced and result.outsize < result.insize
    assert result.details['objects'] == 4
    assert result.details['coder'] == coder
    assert result.details['candidate_values'] == 15
    rewritten = source.read_bytes()
    assert nib_fingerprint(rewritten) == nib_fingerprint(original)
    before, after = parse(original), parse(rewritten)
    assert len(before.objects) == len(after.objects) == 4
    assert after.objects[1] == after.objects[2]  # Stored properties shared, objects still distinct.
    assert after.keys == before.keys and after.classes == before.classes
    references = [struct.unpack('<I', value.payload)[0]
                  for value in after.values if value.kind == 10]
    assert references == [1, 2, 3, 1]
    assert {value.kind for value in after.values} == set(range(11))
    assert after.values[-1] == before.values[-1]
    # Repeating an already compacted input has no effect.
    assert not pack_nib(str(source)).replaced
    assert source.read_bytes() == rewritten


def test_overlapping_components_and_unused_values_are_preserved(tmp_path):
    keys, classes = [b'key'], [(b'Class\0', b'')]
    values = [(0, 8, bytes([index]) * 100) for index in range(5)]
    # Both [A,B,C] components overlap internally; the orphan X is between them.
    values = values[:3] + [values[4]] + values[:3]
    objects = [(0, 0, 2), (0, 1, 2), (0, 4, 2), (0, 5, 2), (0, 7, 0)]
    original = archive_bytes(objects, keys, values, classes)
    source = tmp_path / 'overlap.nib'
    source.write_bytes(original)
    assert pack_nib(str(source)).replaced
    rewritten = source.read_bytes()
    assert nib_fingerprint(rewritten) == nib_fingerprint(original)
    after = parse(rewritten)
    assert after.objects == [(0, 0, 2), (0, 1, 2), (0, 0, 2), (0, 1, 2), (0, 0, 0)]
    assert len(after.values) == 4 and after.values[-1].payload == b'\x04' * 100


def test_nonduplicate_overlaps_do_not_expand_and_empty_archives_are_valid(tmp_path):
    values = [(0, 8, bytes([index]) * 100) for index in range(4)]
    original = archive_bytes([(0, 0, 3), (0, 1, 3)], [b'key'], values, [(b'Class\0', b'')])
    source = tmp_path / 'overlap.nib'
    source.write_bytes(original)
    assert not pack_nib(str(source)).replaced
    assert source.read_bytes() == original
    empty = archive_bytes([], [], [], [])
    assert len(empty) == 50 and parse(empty).fingerprint() == nib_fingerprint(empty)
    source.write_bytes(empty)
    assert not pack_nib(str(source)).replaced
    assert source.read_bytes() == empty


@pytest.mark.parametrize('coder', [9, 10])
@pytest.mark.parametrize('fault', ['class-name', 'fallback-index', 'trailer'])
def test_class_records_and_undocumented_trailers_are_rejected(tmp_path, coder, fault):
    objects, keys, values, classes = nib_parts()
    if fault == 'class-name':
        classes[0] = (b'NSObject!', b'')
    elif fault == 'fallback-index':
        classes[1] = (classes[1][0], struct.pack('<I', len(classes)))
    original = archive_bytes(objects, keys, values, classes, coder=coder)
    if fault == 'trailer':
        original += b'undocumented trailer'
    source = tmp_path / 'unsupported.nib'
    source.write_bytes(original)
    assert not pack_nib(str(source)).replaced
    assert source.read_bytes() == original
    assert not validate_output(str(source), 'nib').ok


def test_coder_version_is_part_of_preservation_contract():
    assert nib_fingerprint(nib_bytes(coder=9)) != nib_fingerprint(nib_bytes(coder=10))


def test_structural_varints_across_multiple_bytes(tmp_path):
    keys = [b'key'] * 130
    classes = [(b'Class\0', b'')] * 130
    payload = b'opaque ' * 2400  # Data length needs three VInt32 bytes.
    values = [(129, 8, payload)] * 130
    # Class, key, value offset and value count all need multiple bytes.
    original = archive_bytes([(129, 129, 1), (129, 0, 129)], keys, values, classes, padded=True)
    source = tmp_path / 'large-varints.nib'
    source.write_bytes(original)
    assert pack_nib(str(source)).replaced
    assert nib_fingerprint(source.read_bytes()) == nib_fingerprint(original)


def test_cancellation_during_validation_and_context_reset(tmp_path, monkeypatch):
    original = nib_bytes()
    source = tmp_path / 'source.nib'
    source.write_bytes(original)
    event = threading.Event()
    fingerprint = NibArchive.fingerprint

    def cancel(archive):
        event.set()
        return fingerprint(archive)

    monkeypatch.setattr(NibArchive, 'fingerprint', cancel)
    assert not pack_nib(str(source), _cancel_event=event).replaced
    assert source.read_bytes() == original
    monkeypatch.setattr(NibArchive, 'fingerprint', fingerprint)
    assert pack_nib(str(source)).replaced


def test_library_forwards_cumulative_nib_resource_limits(tmp_path):
    original = nib_bytes()
    source = tmp_path / 'source.nib'
    source.write_bytes(original)
    result = FileRepacker().repack(str(source), options=RepackOptions(format_max_nodes=1))
    assert not result.results[0].replaced and 'budget' in result.results[0].reason
    assert source.read_bytes() == original


@pytest.mark.parametrize('fault', [
    'signature', 'keyed-plist', 'version', 'coder', 'truncated', 'trailing', 'offset',
    'gap', 'count', 'unknown-type', 'reference', 'class', 'key', 'range',
    'unterminated-varint', 'overflow-varint', 'class-length', 'class-extra', 'data-length',
])
def test_malformed_or_unsupported_inputs_stay_exact(tmp_path, fault):
    original = bytearray(nib_bytes())
    fields = struct.unpack_from('<10I', original, 10)
    objects, keys, values, classes = nib_parts()
    mutations = {
        'signature': (0, b'BAD!'),
        'version': (10, struct.pack('<I', 10)),
        'coder': (14, struct.pack('<I', 11)),
        'offset': (30, struct.pack('<I', 49)),
        'gap': (22, struct.pack('<I', 51)),
        'count': (18, struct.pack('<I', 0xFFFFFFFF)),
        'unknown-type': (fields[7] + 1, b'\x0b'),
        'reference': (fields[7] + 2, struct.pack('<I', len(objects))),
        'class': (50, bytes([0x80 + len(classes)])),
        'key': (fields[7], bytes([0x80 + len(keys)])),
        'range': (52, bytes([0x80 + len(values) + 1])),
        'unterminated-varint': (50, b'\0' * 5),
        'overflow-varint': (50, b'\x7f\x7f\x7f\x7f\xff'),
        'class-length': (fields[9], b'\xff'),
        'class-extra': (fields[9] + 1, b'\xff'),
    }
    if fault in mutations:
        offset, replacement = mutations[fault]
        original[offset:offset + len(replacement)] = replacement
    elif fault == 'keyed-plist':
        original = bytearray(b'bplist00' + b'opaque keyed archive')
    elif fault == 'truncated':
        original = original[:-1]
    elif fault == 'trailing':
        original.extend(b'unknown tail')
    else:
        original = bytearray(archive_bytes([(0, 0, 1)], [b'key'], [(0, 8, b'a')],
                                           [(b'Class\0', b'')]))
        value_offset = struct.unpack_from('<I', original, 38)[0]
        original[value_offset + 2] = 0xFF
    source = tmp_path / 'bad.nib'
    source.write_bytes(original)
    result = pack_nib(str(source))
    assert not result.replaced and result.reason
    assert source.read_bytes() == original
    assert not validate_output(str(source), 'nib').ok


@pytest.mark.parametrize('field', ['opaque', 'reference', 'object', 'scalar', 'key',
                                  'class-extra', 'unused-class', 'orphan'])
def test_valid_smaller_changed_candidate_is_refused(tmp_path, monkeypatch, field):
    original = nib_bytes()
    candidate = parse(original).compact()
    if field == 'opaque':
        candidate = candidate.replace(b'keep  ', b'keep! ', 1)
    elif field == 'reference':
        candidate = candidate.replace(b'\x84\x0a\x03\0\0\0', b'\x84\x0a\x00\0\0\0', 1)
    elif field == 'object':
        candidate = candidate[:50] + b'\x81' + candidate[51:]
    elif field == 'scalar':
        candidate = candidate.replace(b'\x82\x06\0\0\0\x80', b'\x82\x06\0\0\0\0', 1)
    elif field == 'key':
        candidate = candidate.replace(b'UINibTopLevelObjectsKey', b'UINibTopLevelObjectsKEy', 1)
    elif field == 'class-extra':
        marker = b'\x8b\x81\0\0\0\0CustomView\0'
        candidate = candidate.replace(marker, b'\x8b\x81\x02\0\0\0CustomView\0', 1)
    elif field == 'unused-class':
        candidate = candidate.replace(b'UnusedClass', b'UNusedClass', 1)
    else:
        candidate = candidate.replace(b'orphan value', b'Orphan value', 1)
    assert candidate != parse(original).compact() and len(candidate) < len(original)
    assert nib_fingerprint(candidate) != nib_fingerprint(original)
    source = tmp_path / 'source.nib'
    source.write_bytes(original)
    monkeypatch.setattr(NibArchive, 'compact', lambda _: candidate)
    assert not pack_nib(str(source)).replaced
    assert source.read_bytes() == original


@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'min-savings', 'outfile', 'backup'])
def test_library_publication_policies_and_metadata(tmp_path, mode):
    source, target = tmp_path / 'source.NIB', tmp_path / 'output.NIB'
    original = nib_bytes()
    source.write_bytes(original)
    os.chmod(source, 0o640)
    os.utime(source, ns=(1600000000000000000, 1600000000123456789))
    before = source.stat()
    options = RepackOptions(dryrun=mode == 'dryrun', backup=mode == 'backup',
                            min_savings=100 if mode == 'min-savings' else None,
                            pack_images=False)
    result = FileRepacker().repack(str(source), outfile=str(target) if mode == 'outfile' else None,
                                  options=options)
    after = target if mode == 'outfile' else source
    assert nib_fingerprint(after.read_bytes()) == nib_fingerprint(original)
    assert after.stat().st_mode == before.st_mode
    assert after.stat().st_mtime_ns == before.st_mtime_ns
    if mode in ('inplace', 'outfile', 'backup'):
        assert after.stat().st_size < len(original)
        assert any(item.replaced for item in result.results)
    if mode in ('dryrun', 'min-savings', 'outfile'):
        assert source.read_bytes() == original
    if mode == 'backup':
        assert (tmp_path / 'source.NIB.bak').read_bytes() == original


@pytest.mark.parametrize('limit', ['nodes', 'decoded', 'memory', 'scratch', 'deadline', 'cancel'])
def test_resource_limits_cancellation_and_cleanup(tmp_path, monkeypatch, limit):
    original = nib_bytes()
    source, scratch = tmp_path / 'source.nib', tmp_path / 'scratch'
    source.write_bytes(original)
    scratch.mkdir()
    monkeypatch.setattr('filerepack.candidates.TEMP_PATH', str(scratch))
    options = {}
    if limit in ('nodes', 'decoded', 'memory', 'scratch'):
        option = 'format_max_nodes' if limit == 'nodes' else 'format_max_' + limit + '_bytes'
        options[option] = 1
    elif limit == 'cancel':
        event = threading.Event()
        event.set()
        options['_cancel_event'] = event
    else:
        with format_scope({}) as budget:
            budget.started -= budget.limits.seconds + 1
            result = pack_nib(str(source))
    if limit != 'deadline':
        result = pack_nib(str(source), **options)
    assert not result.replaced and any(
        word in result.reason for word in ('budget', 'cancelled', 'bounded buffer')
    )
    assert source.read_bytes() == original and list(scratch.iterdir()) == []


def test_failed_publication_preserves_source_and_cleans_scratch(tmp_path, monkeypatch):
    original = nib_bytes()
    source, scratch = tmp_path / 'source.nib', tmp_path / 'scratch'
    source.write_bytes(original)
    scratch.mkdir()
    monkeypatch.setattr('filerepack.candidates.TEMP_PATH', str(scratch))

    def fail(*args, **kwargs):
        raise OSError('injected publication failure')

    monkeypatch.setattr('filerepack.candidates.publish_candidate', fail)
    assert not pack_nib(str(source)).replaced
    assert source.read_bytes() == original and list(scratch.iterdir()) == []


def test_cli_repack_and_filtered_parallel_bulk(tmp_path):
    runner = CliRunner()
    source = tmp_path / 'single.nib'
    original = nib_bytes()
    source.write_bytes(original)
    result = runner.invoke(app, ['repack', str(source), '--no-images'])
    assert result.exit_code == 0, result.output
    assert source.stat().st_size < len(original)
    folder = tmp_path / 'bulk'
    folder.mkdir()
    for name in ('first.nib', 'second.NIB'):
        (folder / name).write_bytes(original)
    untouched = folder / 'keep.json'
    untouched.write_bytes(b' { "keep": true } ')
    result = runner.invoke(app, ['bulk', str(folder), '--include-ext', 'nib', '--jobs', '2'])
    assert result.exit_code == 0, result.output
    for name in ('first.nib', 'second.NIB'):
        assert (folder / name).stat().st_size < len(original)
        assert nib_fingerprint((folder / name).read_bytes()) == nib_fingerprint(original)
    assert untouched.read_bytes() == b' { "keep": true } '


@pytest.mark.parametrize('deep', [False, True])
def test_nested_zip_retains_member_names_and_expected_payloads(tmp_path, deep):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    source = tmp_path / 'interfaces.zip'
    original = nib_bytes()
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('Base.lproj/View.nib', original)
        archive.writestr('keep.bin', b'unchanged')
    FileRepacker().repack(str(source), options=RepackOptions(deep_walking=deep))
    with zipfile.ZipFile(source) as archive:
        assert set(archive.namelist()) == {'Base.lproj/View.nib', 'keep.bin'}
        rewritten = archive.read('Base.lproj/View.nib')
        assert nib_fingerprint(rewritten) == nib_fingerprint(original)
        assert archive.read('keep.bin') == b'unchanged'
    assert (len(rewritten) < len(original)) if deep else rewritten == original
