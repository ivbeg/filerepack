"""Fault injection for the fixture-bound experiment; no production behavior changes."""

import struct
import zlib

import pytest

from dev.ole.ppt_record_pilot import CURRENT, DOCUMENT, PinnedFixture
from filerepack.ole_verify import CompoundFile


@pytest.fixture(scope='module')
def pilot():
    return PinnedFixture()


def candidate_streams(pilot):
    return pilot.encode(pilot.original.streams,
                        [zlib.compress(raw, 9) for raw in pilot.raw_objects])


def test_encoding_only_change_has_explicit_contract(pilot):
    candidate = CompoundFile(pilot.container(candidate_streams(pilot)))
    result = pilot.verify(pilot.original, candidate)
    assert result['intent_equal']
    assert not result['strict_ole_manifest_equal']
    assert result['before']['objects'][1] != result['after']['objects'][1]
    assert result['before']['user_edit'] != result['after']['user_edit']
    assert set(pilot.original.streams) == set(candidate.streams)


@pytest.mark.parametrize('fault', [
    'document-byte', 'current-edit', 'persist-target', 'edit-directory',
    'record-kind', 'decoded-size', 'zlib-checksum', 'unrelated-stream',
    'missing-stream', 'extra-stream', 'extra-record', 'uncompressed-wrapper',
])
def test_fault_is_rejected(pilot, fault):
    streams = candidate_streams(pilot)
    layout = pilot.layout(streams)
    data = bytearray(streams[DOCUMENT])
    if fault == 'document-byte':
        data[200] ^= 1
    elif fault == 'current-edit':
        streams[CURRENT] = pilot.current
    elif fault == 'persist-target':
        struct.pack_into('<I', data, layout['persist_directory'] + 16, 0)
    elif fault == 'edit-directory':
        struct.pack_into('<I', data, layout['user_edit'] + 20, 9797)
    elif fault == 'record-kind':
        struct.pack_into('<H', data, 4568 + 2, 4114)
    elif fault == 'decoded-size':
        struct.pack_into('<I', data, 4568 + 8, len(pilot.raw_objects[0]) + 1)
    elif fault == 'zlib-checksum':
        data[layout['objects'][1] - 1] ^= 1
    elif fault == 'unrelated-stream':
        streams[('Pictures',)] += b'changed'
    elif fault == 'missing-stream':
        del streams[('Pictures',)]
    elif fault == 'extra-stream':
        streams[('unknown',)] = b'opaque'
    elif fault == 'extra-record':
        data.extend(struct.pack('<HHI', 15, 1000, 0))
    elif fault == 'uncompressed-wrapper':
        struct.pack_into('<H', data, 4568, 0)
    streams[DOCUMENT] = bytes(data)
    with pytest.raises(ValueError):
        pilot.verify(pilot.original, CompoundFile(pilot.container(streams)))


@pytest.mark.parametrize('fault', ['changed-object', 'concatenated-zlib', 'trailing-zlib'])
def test_encoder_output_is_checked_before_container_write(pilot, fault):
    blobs = [zlib.compress(raw, 9) for raw in pilot.raw_objects]
    if fault == 'changed-object':
        blobs[0] = zlib.compress(pilot.raw_objects[0][:-1] + b'X', 9)
    elif fault == 'concatenated-zlib':
        blobs[0] += zlib.compress(b'extra', 9)
    else:
        blobs[0] += b'X'
    with pytest.raises(ValueError):
        pilot.encode(pilot.original.streams, blobs)


def test_directory_metadata_change_is_rejected(pilot):
    root = next(e for e in pilot.original.entries if e.kind == 5)
    candidate = CompoundFile(pilot.container(
        candidate_streams(pilot), root_override=(root.clsid, root.state ^ 1, 0, root.modified)))
    with pytest.raises(ValueError, match='metadata differs'):
        pilot.verify(pilot.original, candidate)


def test_fixture_checksum_gate(pilot, tmp_path, monkeypatch):
    import dev.ole.ppt_record_pilot as module
    raw = bytearray(pilot.original.data)
    raw[-1] ^= 1
    (tmp_path / module.FIXTURE).write_bytes(raw)
    monkeypatch.setattr(module, 'CORPUS', tmp_path)
    with pytest.raises(ValueError, match='checksum mismatch'):
        module.PinnedFixture()
