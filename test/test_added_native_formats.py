"""Real-byte preservation and publication tests for newly supported native files."""

import gzip
import os
from pathlib import Path
import struct
import zipfile
import zlib

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.aseprite import pack_aseprite, rewrite_aseprite
from filerepack.blend import decode_blend, pack_blend, validate_blend
from filerepack.nrrd import decode_nrrd, pack_nrrd
from filerepack.psb import pack_psb, psb_fingerprint
from filerepack.tools import resolve_szip
from test.format_fixtures import aseprite_bytes, blend_bytes, nrrd_bytes, psb_bytes


def native_payload(extension):
    if extension == 'blend':
        return blend_bytes()
    if extension == 'nrrd':
        return nrrd_bytes()[0]
    if extension == 'psb':
        return psb_bytes()[0]
    return aseprite_bytes()[0]


def native_fingerprint(path, extension, tmp_path):
    data = path.read_bytes()
    if extension == 'blend':
        decoded = tmp_path / 'decoded.bin'
        decode_blend(str(path), str(decoded))
        assert validate_blend(str(decoded)) == 300
        return decoded.read_bytes()
    if extension == 'nrrd':
        return decode_nrrd(data)
    if extension == 'psb':
        return psb_fingerprint(data)
    return rewrite_aseprite(data)[1]


@pytest.mark.parametrize('extension', ['blend', 'nrrd', 'psb', 'ase', 'aseprite'])
@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'min_savings', 'outfile'])
def test_native_rewrites_preserve_decoded_contents_and_extensions(tmp_path, extension, mode):
    path = tmp_path / ('source.' + extension)
    original = native_payload(extension)
    path.write_bytes(original)
    os.chmod(path, 0o640)
    os.utime(path, ns=(1600000000000000000, 1600000000123456789))
    before = path.stat()
    expected = native_fingerprint(path, extension, tmp_path)
    output = tmp_path / ('output.' + extension)
    result = FileRepacker().repack(str(path), outfile=str(output) if mode == 'outfile' else None,
                                  options=RepackOptions(dryrun=mode == 'dryrun',
                                                        min_savings=100 if mode == 'min_savings'
                                                        else None))
    target = output if mode == 'outfile' else path
    assert Path(result.filepath).suffix == '.' + extension
    assert native_fingerprint(target, extension, tmp_path) == expected
    assert target.stat().st_mode == before.st_mode
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    if mode in ('inplace', 'outfile'):
        assert target.stat().st_size < len(original)
    if mode != 'inplace':
        assert path.read_bytes() == original


@pytest.mark.parametrize('extension', ['blend', 'nrrd', 'psb', 'ase', 'aseprite'])
@pytest.mark.parametrize('fault', ['signature', 'truncation', 'trailing'])
def test_invalid_native_files_stay_unchanged(tmp_path, extension, fault):
    data = native_payload(extension)
    if fault == 'signature':
        data = b'BAD!' + data[4:]
    elif fault == 'truncation':
        data = data[:-10]
    else:
        data += b'unexpected trailing bytes'
    path = tmp_path / ('bad.' + extension)
    path.write_bytes(data)
    FileRepacker().repack(str(path))
    assert path.read_bytes() == data


@pytest.mark.parametrize('codec', ['raw', 'gzip', 'zstd'])
@pytest.mark.parametrize(('pointer', 'endian'), [(32, '<'), (64, '<'), (32, '>'), (64, '>')])
def test_blender_preserves_stream_for_each_codec_and_header(tmp_path, codec, pointer, endian):
    raw = blend_bytes(pointer=pointer, endian=endian)
    data = raw
    if codec == 'gzip':
        data = gzip.compress(raw, compresslevel=1)
    elif codec == 'zstd':
        zstd = pytest.importorskip('zstandard')
        data = zstd.ZstdCompressor(level=1).compress(raw)
    path = tmp_path / 'project.blend'
    path.write_bytes(data)
    result = pack_blend(str(path), keep_if_larger=False)
    assert result is not None and result.replaced
    decoded = tmp_path / 'decoded.bin'
    output_codec = decode_blend(str(path), str(decoded))
    assert decoded.read_bytes() == raw
    if codec != 'raw':
        assert output_codec == codec


def test_legacy_blender_uses_gzip_and_missing_zstd_retains_source(tmp_path, monkeypatch):
    raw = blend_bytes(version=279)
    path = tmp_path / 'legacy.blend'
    path.write_bytes(raw)
    assert pack_blend(str(path)).replaced
    assert path.read_bytes().startswith(b'\x1f\x8b')
    zstd = pytest.importorskip('zstandard')
    data = zstd.ZstdCompressor(level=1).compress(blend_bytes())
    path.write_bytes(data)
    monkeypatch.setattr('filerepack.blend._zstandard', lambda: None)
    assert pack_blend(str(path)) is None
    assert path.read_bytes() == data


def test_blender_bounds_and_failed_candidate_decode(tmp_path, monkeypatch):
    path = tmp_path / 'project.blend'
    raw = blend_bytes()
    path.write_bytes(gzip.compress(raw))
    original = path.read_bytes()
    monkeypatch.setattr('filerepack.blend.MAX_NATIVE_BYTES', 100)
    assert pack_blend(str(path)) is None
    monkeypatch.setattr('filerepack.blend.MAX_NATIVE_BYTES', 256 * 1024 * 1024)
    monkeypatch.setattr('filerepack.blend._encode_blend',
                        lambda source, output, codec: Path(output).write_bytes(b'bad candidate'))
    assert pack_blend(str(path)) is None
    assert path.read_bytes() == original


@pytest.mark.parametrize('layers', [True, False])
@pytest.mark.parametrize('codec', [2, 3])
def test_psb_zip_and_prediction_preserve_all_decoded_channels(tmp_path, layers, codec):
    data, _raw = psb_bytes(layers=layers, codec=codec)
    expected = psb_fingerprint(data)
    path = tmp_path / 'layers.psb'
    path.write_bytes(data)
    assert pack_psb(str(path)).replaced
    assert psb_fingerprint(path.read_bytes()) == expected


def test_psb_rejects_wrong_version_and_damaged_zip(tmp_path):
    path = tmp_path / 'wrong.psb'
    data, _ = psb_bytes()
    for invalid in (data[:4] + b'\0\1' + data[6:], data[:-1] + bytes([data[-1] ^ 255])):
        path.write_bytes(invalid)
        assert pack_psb(str(path)) is None
        assert path.read_bytes() == invalid


def test_psb_rejects_valid_candidate_with_changed_composite(tmp_path, monkeypatch):
    data, raw = psb_bytes()
    channel = b'\0\2' + zlib.compress(raw, 1)
    candidate = data[:-len(channel)] + b'\0\2' + zlib.compress(b'\x44' * len(raw), 9)
    assert psb_fingerprint(candidate) != psb_fingerprint(data)
    path = tmp_path / 'image.psb'
    path.write_bytes(data)
    monkeypatch.setattr('filerepack.psb._recompress_psd_bytes', lambda *args: candidate)
    assert pack_psb(str(path)) is None
    assert path.read_bytes() == data


def test_nrrd_rejects_valid_candidate_with_changed_array(tmp_path, monkeypatch):
    data, raw = nrrd_bytes()
    candidate, _ = nrrd_bytes(encoding='gzip', raw=b'\0' * len(raw))
    path = tmp_path / 'array.nrrd'
    path.write_bytes(data)
    monkeypatch.setattr('filerepack.nrrd._compress_nrrd', lambda *args: candidate)
    assert pack_nrrd(str(path)) is None
    assert path.read_bytes() == data


@pytest.mark.parametrize('tilemap', [False, True])
def test_aseprite_preserves_timings_linked_cels_and_unknown_chunks(tmp_path, tilemap):
    data, _raw = aseprite_bytes(tilemap=tilemap)
    expected = rewrite_aseprite(data)[1]
    path = tmp_path / 'animation.aseprite'
    path.write_bytes(data)
    assert pack_aseprite(str(path)).replaced
    rewritten = path.read_bytes()
    assert rewrite_aseprite(rewritten)[1] == expected
    assert b'unknown metadata' in rewritten
    assert struct.unpack_from('<H', rewritten, 136)[0] == 123
    first_size = struct.unpack_from('<I', rewritten, 128)[0]
    assert struct.unpack_from('<H', rewritten, 128 + first_size + 8)[0] == 456


def test_aseprite_keeps_raw_cels_and_rejects_invalid_linked_frame(tmp_path):
    data, _raw = aseprite_bytes(raw_cel=True)
    assert rewrite_aseprite(data)[0] == data
    path = tmp_path / 'animation.ase'
    path.write_bytes(data)
    result = pack_aseprite(str(path))
    assert result is None or not result.replaced
    assert path.read_bytes() == data
    invalid = data[:-2] + struct.pack('<H', 2)
    path.write_bytes(invalid)
    assert pack_aseprite(str(path)) is None
    assert path.read_bytes() == invalid


@pytest.mark.parametrize('encoding', ['raw', 'gzip', 'gz', 'bzip2', 'bz2'])
@pytest.mark.parametrize('newline', [b'\n', b'\r\n'])
def test_nrrd_preserves_array_header_and_line_endings(tmp_path, encoding, newline):
    data, raw = nrrd_bytes(encoding=encoding, newline=newline)
    expected = decode_nrrd(data)
    path = tmp_path / 'volume.nrrd'
    path.write_bytes(data)
    result = pack_nrrd(str(path), keep_if_larger=False)
    assert result is not None and result.replaced
    assert decode_nrrd(path.read_bytes()) == expected
    assert decode_nrrd(path.read_bytes())[1] == raw
    assert b'patient:=exact unchanged string' in path.read_bytes()


@pytest.mark.parametrize('field', [b'data file: external.raw', b'byte skip: -1',
                                 b'line skip: 1', b'encoding: ascii', b'dimension: 3',
                                 b'type: unsupported', b'endian: unknown',
                                 b'sizes: 1000000000 1000000000'])
def test_unsupported_nrrd_inputs_and_related_files_are_untouched(tmp_path, field):
    data, _ = nrrd_bytes()
    header, payload = data.split(b'\n\n', 1)
    key = field.split(b':', 1)[0]
    lines = header.split(b'\n')
    lines = [line for line in lines if not line.startswith(key + b':')]
    data = b'\n'.join(lines + [field]) + b'\n\n' + payload
    path = tmp_path / 'unsupported.nrrd'
    external = tmp_path / 'external.raw'
    external.write_bytes(b'other data')
    path.write_bytes(data)
    assert pack_nrrd(str(path)) is None
    assert path.read_bytes() == data and external.read_bytes() == b'other data'


def test_nrrd_float_payload_keeps_nan_and_signed_zero_bits(tmp_path):
    words = [0x80000000, 0x7fc01234, 0x7fa05678, 0x7f800000, 0xff800000, 0x3f800000]
    raw = (struct.pack('>6I', *words) * 2731)[:128 * 128 * 4]
    data, _ = nrrd_bytes(dtype='float', raw=raw)
    path = tmp_path / 'floats.nrrd'
    path.write_bytes(data)
    assert pack_nrrd(str(path)).replaced
    assert decode_nrrd(path.read_bytes())[1] == raw


@pytest.mark.parametrize(('extension', 'handler'), [('psb', pack_psb), ('aseprite', pack_aseprite),
                                                  ('nrrd', pack_nrrd), ('blend', pack_blend)])
def test_failed_publication_cleans_all_owned_scratch(tmp_path, monkeypatch, extension, handler):
    path = tmp_path / ('source.' + extension)
    original = native_payload(extension)
    path.write_bytes(original)
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr('filerepack.candidates.TEMP_PATH', str(scratch))
    monkeypatch.setattr('filerepack.candidates.publish_candidate',
                        lambda *args, **kwargs: (_ for _ in ()).throw(OSError('injected failure')))
    assert handler(str(path)) is None
    assert path.read_bytes() == original
    assert list(scratch.iterdir()) == []


def test_native_formats_work_in_nested_zip_without_renaming(tmp_path):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    path = tmp_path / 'native.zip'
    extensions = ['blend', 'nrrd', 'psb', 'aseprite']
    originals = {}
    with zipfile.ZipFile(path, 'w') as archive:
        for extension in extensions:
            originals[extension] = native_payload(extension)
            archive.writestr('data.' + extension, originals[extension])
    FileRepacker().repack(str(path))
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {'data.' + ext for ext in extensions}
        for extension in extensions:
            before = tmp_path / ('before.' + extension)
            after = tmp_path / ('after.' + extension)
            before.write_bytes(originals[extension])
            after.write_bytes(archive.read('data.' + extension))
            assert native_fingerprint(before, extension, tmp_path) == native_fingerprint(
                after, extension, tmp_path,
            )
            assert after.stat().st_size < before.stat().st_size
