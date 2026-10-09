import struct

import pytest

from filerepack import FileRepacker
from filerepack.format_support import Budget, FormatLimits
from filerepack.tracev3 import _parse, destination_refusal

lz4 = pytest.importorskip('lz4.block')


def chunk(tag, body, subtag=0):
    raw = struct.pack('<IIQ', tag, subtag, len(body)) + body
    return raw + bytes(-len(raw) % 8)


def fixture():
    raw = b'preserved logging records and metadata\0' * 1024
    blocks = b'bv4-' + struct.pack('<I', len(raw)) + raw
    encoded = lz4.compress(raw, store_size=False, dict=raw[-65536:])
    blocks += b'bv41' + struct.pack('<II', len(raw), len(encoded)) + encoded + b'bv4$'
    return (chunk(0x1000, bytes(208), 0x11) + chunk(0x600b, b'opaque catalog metadata') +
            chunk(0x600d, blocks, 7) + chunk(0x1111, b'opaque trailing chunk')), raw


def test_recompression_exact_chunk_payloads(tmp_path):
    source = tmp_path / 'archived.tracev3'
    original, _ = fixture()
    source.write_bytes(original)
    summary = FileRepacker().repack_zip_file(str(source))
    assert summary.outcome.status == 'replaced'
    assert len(source.read_bytes()) < len(original)
    def budget():
        return Budget(FormatLimits())
    assert _parse(original, budget())[1] == _parse(source.read_bytes(), budget())[1]
    assert b'opaque catalog metadata' in source.read_bytes()
    assert b'opaque trailing chunk' in source.read_bytes()


@pytest.mark.parametrize('suffix', [b'bv4X', b'bv41\xff\xff\xff\xff', b''])
def test_bad_stream_never_published(tmp_path, suffix):
    original = chunk(0x1000, bytes(208), 0x11) + chunk(0x600b, b'catalog')
    original += chunk(0x600d, suffix)
    source, output = tmp_path / 'bad.tracev3', tmp_path / 'output.tracev3'
    source.write_bytes(original)
    summary = FileRepacker().repack_zip_file(str(source), str(output))
    assert summary.outcome.status in ('failed', 'unsupported', 'skipped')
    assert source.read_bytes() == original
    assert not output.exists()


def test_decoded_limit_prevents_publication(tmp_path):
    source = tmp_path / 'large.tracev3'
    original, _ = fixture()
    source.write_bytes(original)
    result = FileRepacker().repack_zip_file(str(source), def_options={
        'format_max_decoded_bytes': 1024,
    })
    assert result.outcome.status == 'skipped'
    assert source.read_bytes() == original


def test_active_store_aliases_and_external_output(monkeypatch, tmp_path):
    monkeypatch.setattr('filerepack.tracev3.ACTIVE_STORES', (str(tmp_path / 'live'),))
    alias = tmp_path / 'alias'
    alias.symlink_to(tmp_path / 'live')
    assert destination_refusal('archive.tracev3', str(alias / 'file.tracev3'), None)
    assert destination_refusal(str(alias / 'file.tracev3'),
                               str(tmp_path / 'copy.tracev3'), None) is None
    assert destination_refusal('archive.tracev3', 'copy.tracev3', str(alias / 'backup'))
