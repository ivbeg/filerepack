"""Recompressed gzip members keep source metadata instead of scratch names and times."""

import gzip
import io
import shutil
import tarfile
import zlib

import pytest

from filerepack import FileRepacker

PAYLOAD = b'filerepack gzip header regression\n' * 4000
FHCRC, FEXTRA, FNAME, FCOMMENT = 2, 4, 8, 16


def _member(payload, name='', mtime=0, level=1):
    buffer = io.BytesIO()
    with gzip.GzipFile(filename=name, mode='wb', fileobj=buffer, compresslevel=level,
                       mtime=mtime) as target:
        target.write(payload)
    return buffer.getvalue()


def _fields(data):
    flags, position = data[3], 10
    fields = {'flags': flags, 'mtime': int.from_bytes(data[4:8], 'little'), 'os': data[9]}
    if flags & FEXTRA:
        position += 2 + int.from_bytes(data[position:position + 2], 'little')
    for bit, key in ((FNAME, 'name'), (FCOMMENT, 'comment')):
        if flags & bit:
            end = data.index(b'\0', position)
            fields[key] = data[position:end]
            position = end + 1
    if flags & FHCRC:
        fields['hcrc_valid'] = (
            int.from_bytes(data[position:position + 2], 'little')
            == zlib.crc32(data[:position]) & 0xFFFF
        )
    return fields


@pytest.fixture(params=['pigz', 'native'])
def gzip_encoder(request, monkeypatch):
    if request.param == 'pigz':
        if not shutil.which('pigz'):
            pytest.skip('pigz required')
    else:
        from filerepack import streams
        resolve = streams.resolve_tool
        monkeypatch.setattr(streams, 'resolve_tool',
                            lambda key: None if key == 'pigz' else resolve(key))
    return request.param


def test_stream_gzip_keeps_source_name_and_mtime(tmp_path, gzip_encoder):
    path = tmp_path / 'report.csv.gz'
    path.write_bytes(_member(PAYLOAD, name='report.csv', mtime=1234567890))
    original = _fields(path.read_bytes())
    summary = FileRepacker().repack(str(path))
    data = path.read_bytes()
    assert summary.results[0].replaced
    assert gzip.decompress(data) == PAYLOAD
    assert _fields(data) == original
    assert original['name'] == b'report.csv'


def test_stream_gzip_output_is_reproducible(tmp_path, gzip_encoder):
    member = _member(PAYLOAD, mtime=987654321)
    outputs = []
    for name in ('first.gz', 'second.gz'):
        path = tmp_path / name
        path.write_bytes(member)
        FileRepacker().repack(str(path))
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1] != member
    fields = _fields(outputs[0])
    assert not fields['flags'] & FNAME and fields['mtime'] == 987654321


def test_header_transfer_drops_extra_and_recomputes_header_crc(tmp_path):
    from filerepack.streams import _stamp_gzip_header
    extra = b'BC\x02\x00\x00\x00'
    header = (b'\x1f\x8b\x08' + bytes([FHCRC | FEXTRA | FNAME | FCOMMENT])
              + (42).to_bytes(4, 'little') + b'\x00\x03'
              + len(extra).to_bytes(2, 'little') + extra + b'data.bin\0' + b'note\0')
    header += (zlib.crc32(header) & 0xFFFF).to_bytes(2, 'little')
    body = _member(PAYLOAD)[10:]
    source = tmp_path / 'source.gz'
    source.write_bytes(header + body)
    candidate = tmp_path / 'candidate.gz'
    candidate.write_bytes(_member(PAYLOAD, level=9))
    _stamp_gzip_header(str(source), str(candidate))
    data = candidate.read_bytes()
    assert gzip.decompress(data) == PAYLOAD
    assert _fields(data) == {'flags': FHCRC | FNAME | FCOMMENT, 'mtime': 42, 'os': 3,
                             'name': b'data.bin', 'comment': b'note', 'hcrc_valid': True}


def test_svgz_keeps_source_name_and_mtime(tmp_path):
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
           + b'<rect width="10" height="10"/>' * 400 + b'</svg>')
    path = tmp_path / 'icon.svgz'
    path.write_bytes(_member(svg, name='icon.svg', mtime=1500000000))
    original = _fields(path.read_bytes())
    FileRepacker().repack(str(path))
    data = path.read_bytes()
    assert data != _member(svg, name='icon.svg', mtime=1500000000)
    assert _fields(data) == original


def test_tar_gzip_rebuild_keeps_source_name_and_mtime(tmp_path):
    if not (shutil.which('7zz') or shutil.which('7z')):
        pytest.skip('7zz/7z required for archive integration')
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        member = tarfile.TarInfo('data.txt')
        member.size = len(PAYLOAD)
        archive.addfile(member, io.BytesIO(PAYLOAD))
    path = tmp_path / 'bundle.tar.gz'
    path.write_bytes(_member(payload.getvalue(), name='bundle.tar', mtime=1600000000, level=0))
    original = _fields(path.read_bytes())
    summary = FileRepacker().repack(str(path))
    data = path.read_bytes()
    assert summary.total_outsize < len(_member(payload.getvalue(), level=0))
    assert _fields(data) == original
    with tarfile.open(path, 'r:gz') as archive:
        assert archive.extractfile('data.txt').read() == PAYLOAD
