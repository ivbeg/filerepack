"""Fault tests for the checksum-bound OfficeArt experiment, outside runtime."""

import struct
import zlib

import pytest

from dev.ole.officeart_pilot import (
    DATA, DOCUMENT, FIXTURES, PICTURES, WORD, WORKBOOK, Codec, PinnedFixture,
    biff, compressor, drawing_group, parts, record, record_bytes,
)
from filerepack.format_support import FormatLimit
from filerepack.ole_verify import CompoundFile


@pytest.fixture(scope='module', params=list(FIXTURES))
def pilot(request):
    return PinnedFixture(request.param)


def reencoded(pilot):
    # Deliberately larger controls always move nonzero host references.
    streams, _ = pilot.encode(pilot.original.streams, compressor('zlib0'), allow_growth=True)
    return streams


def test_common_codec_preserves_three_host_intents(pilot):
    streams = reencoded(pilot)
    candidate = CompoundFile(pilot.container(streams))
    verified = pilot.verify(pilot.original, candidate)
    assert verified['intent_equal']
    assert verified['decoded_metafile_bytes_equal']
    assert not verified['strict_ole_manifest_equal']
    assert len(pilot.layout(streams)[2]['payloads']) == (
        4 if pilot.name == 'word_with_embeded.doc' else 1 if pilot.host == 'doc' else 2)


def test_retain_source_wrapper_when_encoder_does_not_improve(pilot):
    streams, info = pilot.encode(pilot.original.streams, compressor('zlib0'))
    assert streams == pilot.original.streams
    assert all(p['output_encoded_bytes'] == p['encoded_bytes'] for p in info['payloads'])


@pytest.mark.parametrize('fault', ['unrelated', 'missing', 'extra', 'root-metadata'])
def test_container_faults_are_rejected(pilot, fault):
    streams = reencoded(pilot)
    root = None
    if fault == 'unrelated':
        streams[('\x05SummaryInformation',)] += b'mutation'
    elif fault == 'missing':
        del streams[('\x05SummaryInformation',)]
    elif fault == 'extra':
        streams[('opaque extra',)] = b'opaque'
    else:
        original = next(e for e in pilot.original.entries if e.kind == 5)
        root = (original.clsid, original.state ^ 1, original.created, original.modified)
    with pytest.raises(ValueError):
        pilot.verify(pilot.original, CompoundFile(pilot.container(streams, root)))


def first_metafile(streams, host):
    if host == 'doc':
        data = streams[DATA]
        size = struct.unpack_from('<I', data)[0]
        _, fbse = list(parts(data[68:size]))[-1]
        flags, kind, body = record(fbse)
        assert kind == 0xF007
        return body[36 + body[33]:]
    if host == 'ppt':
        return next(parts(streams[PICTURES]))[1]
    _, _, group, _ = drawing_group(streams[WORKBOOK])
    _, _, body = record(group)
    store = [blob for _, blob in parts(body) if record(blob)[1] == 0xF001][0]
    _, _, store_body = record(store)
    for _, blob in parts(store_body):
        _, _, entry = record(blob)
        child = entry[36 + entry[33]:]
        if record(child)[1] in (0xF01A, 0xF01B):
            return child
    raise AssertionError('missing fixture metafile')


@pytest.mark.parametrize('fault', [
    'decoded-size', 'saved-size', 'filter', 'compression', 'version', 'instance',
    'record-length', 'truncated', 'checksum', 'raw-deflate', 'trailing', 'concatenated',
])
def test_metafile_envelope_faults_are_rejected(pilot, fault):
    blob = first_metafile(pilot.original.streams, pilot.host)
    flags, kind, original = record(blob)
    body = bytearray(original)
    header = 16
    if fault == 'decoded-size':
        struct.pack_into('<I', body, header, struct.unpack_from('<I', body, header)[0] + 1)
    elif fault == 'saved-size':
        struct.pack_into('<I', body, header + 28, len(body))
    elif fault in ('filter', 'compression'):
        body[header + (33 if fault == 'filter' else 32)] ^= 1
    elif fault == 'version':
        flags |= 1
    elif fault == 'instance':
        flags ^= 0x1000
    elif fault == 'checksum':
        body[-1] ^= 1
    elif fault in ('raw-deflate', 'trailing', 'concatenated'):
        encoded = bytes(body[header + 34:])
        if fault == 'raw-deflate':
            raw = zlib.decompress(encoded)
            engine = zlib.compressobj(wbits=-15)
            encoded = engine.compress(raw) + engine.flush()
        else:
            encoded += b'X' if fault == 'trailing' else zlib.compress(b'more')
        body[header + 34:] = encoded
        struct.pack_into('<I', body, header + 28, len(encoded))
    data = record_bytes(flags, kind, body)
    if fault == 'record-length':
        data = data[:4] + struct.pack('<I', len(body) + 1) + data[8:]
    elif fault == 'truncated':
        data = data[:-1]
    with pytest.raises((ValueError, zlib.error)):
        Codec().one(data)


@pytest.mark.parametrize('fault', ['changed', 'trailing', 'concatenated'])
def test_bad_encoder_output_rejected(pilot, fault):
    def bad(raw):
        if fault == 'changed':
            return zlib.compress(raw[:-1] + bytes([raw[-1] ^ 1]), 9)
        return zlib.compress(raw, 9) + (b'X' if fault == 'trailing' else zlib.compress(b'extra'))

    with pytest.raises(ValueError):
        pilot.encode(pilot.original.streams, bad)


@pytest.mark.parametrize('fault', ['uid', 'geometry', 'surrounding', 'reference'])
def test_decoded_equality_does_not_hide_other_mutations(pilot, fault):
    streams = reencoded(pilot)
    if pilot.host == 'ppt':
        path, location = PICTURES, 0
        reference_path, reference_field = DOCUMENT, 908
    elif pilot.host == 'doc':
        path = DATA
        _, fbse = list(parts(streams[path][68:struct.unpack_from('<I', streams[path])[0]]))[-1]
        location = struct.unpack_from('<I', streams[path])[0] - len(fbse) + 44
        reference_path, reference_field = WORD, 3057 if pilot.name == 'vector_image.doc' else 2907
    else:
        path = WORKBOOK
        # The first WMF begins at drawing-group logical offset 12969. The
        # original preceding PNG/JPEG bytes and record fragmentation are exact.
        location = 1408 + 4 + 12969 + 4
        reference_path, reference_field = WORKBOOK, 1338
    data = bytearray(streams[path])
    if fault == 'uid':
        data[location + 8] ^= 1
    elif fault == 'geometry':
        data[location + 28] ^= 1
    elif fault == 'surrounding':
        data[70 if pilot.host == 'doc' else 5] ^= 1
    else:
        data = bytearray(streams[reference_path])
        data[reference_field] ^= 1
        path = reference_path
    streams[path] = bytes(data)
    with pytest.raises(ValueError):
        pilot.verify(pilot.original, CompoundFile(pilot.container(streams)))


def test_xls_relocates_both_sheet_and_index_pointers():
    pilot = PinnedFixture('SimpleWithImages.xls')
    streams = reencoded(pilot)
    before = pilot.layout(pilot.original.streams)[2]['references']
    after = pilot.layout(streams)[2]['references']
    assert {r['record'] for r in before} == {'0x85', '0x20b'}
    assert all(a['target'] != b['target'] for a, b in zip(after, before))
    assert all(a['target'] - b['target'] == after[0]['target'] - before[0]['target']
               for a, b in zip(after, before))
    records = {at: kind for at, kind, _ in biff(streams[WORKBOOK])}
    assert all(records[r['target']] == int(r['target_type'], 16) for r in after)


@pytest.mark.parametrize('kind', [0x85, 0x20B])
def test_xls_stale_absolute_pointer_rejected(kind):
    pilot = PinnedFixture('SimpleWithImages.xls')
    streams = reencoded(pilot)
    _, _, _, records = drawing_group(streams[WORKBOOK])
    at = next(at for at, k, _ in records if k == kind)
    field = at + (4 if kind == 0x85 else 16)
    data = bytearray(streams[WORKBOOK])
    struct.pack_into('<I', data, field, 36566)
    streams[WORKBOOK] = bytes(data)
    with pytest.raises(ValueError, match='BIFF pointer|Excel sheet offset'):
        pilot.verify(pilot.original, CompoundFile(pilot.container(streams)))


def test_valid_xls_pointer_to_different_sheet_is_rejected():
    pilot = PinnedFixture('SimpleWithImages.xls')
    streams = reencoded(pilot)
    records = [(at, payload) for at, kind, payload in biff(streams[WORKBOOK]) if kind == 0x85]
    data = bytearray(streams[WORKBOOK])
    data[records[0][0] + 4:records[0][0] + 8] = records[1][1][:4]
    streams[WORKBOOK] = bytes(data)
    with pytest.raises(ValueError, match='intended content'):
        pilot.verify(pilot.original, CompoundFile(pilot.container(streams)))


def test_valid_zlib_wrapper_with_changed_metafile_is_rejected_by_verifier():
    pilot = PinnedFixture('ole2-embedding-2003.ppt')
    streams = reencoded(pilot)
    blobs = [blob for _, blob in parts(streams[PICTURES])]
    flags, kind, body = record(blobs[0])
    raw = zlib.decompress(body[50:])
    altered = raw[:-1] + bytes([raw[-1] ^ 1])
    encoded = zlib.compress(altered, 9)
    header = bytearray(body[:50])
    struct.pack_into('<I', header, 44, len(encoded))
    first = record_bytes(flags, kind, header + encoded)
    document = bytearray(streams[DOCUMENT])
    struct.pack_into('<I', document, 856, len(first))
    struct.pack_into('<I', document, 908, len(first))
    streams.update({PICTURES: first + blobs[1], DOCUMENT: bytes(document)})
    with pytest.raises(ValueError, match='intended content'):
        pilot.verify(pilot.original, CompoundFile(pilot.container(streams)))


def test_second_uid_variant_retains_both_uids():
    pilot = PinnedFixture('ole2-embedding-2003.ppt')
    flags, kind, body = record(first_metafile(pilot.original.streams, 'ppt'))
    second_uid = bytes(range(16))
    blob = record_bytes(flags + 16, kind, body[:16] + second_uid + body[16:])
    before = Codec().one(blob)[1]
    candidate, after = Codec(compressor('zlib9')).one(blob)
    assert before == after
    assert candidate[8:40] == body[:16] + second_uid


def test_count_and_budget_limits_fail_closed():
    pilot = PinnedFixture('ole2-embedding-2003.ppt')
    blob = first_metafile(pilot.original.streams, 'ppt')
    codec = Codec()
    with pytest.raises(ValueError, match='count/aggregate'):
        codec.sequence(blob * 65)
    codec = Codec()
    codec.budget.limits = type(codec.budget.limits)(decoded=10)
    with pytest.raises(FormatLimit):
        codec.one(blob)


def test_fixture_checksum_gate(tmp_path, monkeypatch):
    import dev.ole.officeart_pilot as module

    pilot = PinnedFixture('vector_image.doc')
    data = bytearray(pilot.original.data)
    data[-1] ^= 1
    (tmp_path / pilot.name).write_bytes(data)
    monkeypatch.setattr(module, 'CORPUS', tmp_path)
    with pytest.raises(ValueError, match='checksum mismatch'):
        PinnedFixture(pilot.name)
