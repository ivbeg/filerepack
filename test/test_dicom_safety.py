"""Preservation regressions using synthetic, non-clinical DICOM datasets."""

import struct

import pytest

from filerepack.codecs import pack_dcm
from filerepack.dicom import dicom_is_packable
from test.dicom_fixtures import build_dicom, expl_elem, expl_empty_sq, impl_elem


def sequence(payload, *, undefined_sequence=False, undefined_item=False, implicit=False):
    item = struct.pack('<HHI', 0xFFFE, 0xE000,
                       0xFFFFFFFF if undefined_item else len(payload)) + payload
    if undefined_item:
        item += struct.pack('<HHI', 0xFFFE, 0xE00D, 0)
    length = 0xFFFFFFFF if undefined_sequence else len(item)
    header = struct.pack('<HH', 0x0008, 0x1111)
    if not implicit:
        header += b'SQ\0\0'
    result = header + struct.pack('<I', length) + item
    if undefined_sequence:
        result += struct.pack('<HHI', 0xFFFE, 0xE0DD, 0)
    return result


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('undefined_sequence', [False, True])
@pytest.mark.parametrize('undefined_item', [False, True])
def test_signatures_never_reach_encoder(tmp_path, monkeypatch, nested,
                                       undefined_sequence, undefined_item):
    path = tmp_path / 'signed.dcm'
    if nested:
        content = build_dicom(extra_dataset=[sequence(
            expl_empty_sq(0xFFFA, 0xFFFA),
            undefined_sequence=undefined_sequence, undefined_item=undefined_item,
        )])
    else:
        content = build_dicom(signatures=True)
    path.write_bytes(content)
    assert not dicom_is_packable(str(path))
    monkeypatch.setattr('filerepack.medical.resolve_tool', lambda _: '/fake/gdcmconv')
    def forbidden(*args, **kwargs):
        pytest.fail('Protected source reached an encoder')
    monkeypatch.setattr('filerepack.medical._run_command', forbidden)
    assert pack_dcm(str(path)) is None
    assert path.read_bytes() == content


@pytest.mark.parametrize('removed', [1, 4, 20])
def test_truncated_pixel_values_are_ineligible(tmp_path, removed):
    path = tmp_path / 'truncated.dcm'
    path.write_bytes(build_dicom()[:-removed])
    assert not dicom_is_packable(str(path))


@pytest.mark.parametrize('trailer', [b'x', b'\0' * 8, expl_elem(0x7FE0, 0x0010, 'OW', b'xx')])
def test_malformed_trailing_data_is_ineligible(tmp_path, trailer):
    path = tmp_path / 'bad-tail.dcm'
    path.write_bytes(build_dicom() + trailer)
    assert not dicom_is_packable(str(path))


def test_defined_sequence_item_is_a_dataset(tmp_path):
    path = tmp_path / 'bad-item.dcm'
    path.write_bytes(build_dicom(extra_dataset=[sequence(b'abcd')]))
    assert not dicom_is_packable(str(path))


@pytest.mark.parametrize('implicit', [False, True])
def test_signature_in_deep_sequence(tmp_path, implicit):
    from filerepack.dicom import TS_EXPLICIT_VR_LE, TS_IMPLICIT_VR_LE
    content = (impl_elem(0xFFFA, 0xFFFA, b'') if implicit
               else expl_empty_sq(0xFFFA, 0xFFFA))
    for _ in range(4):
        content = sequence(content, implicit=implicit)
    path = tmp_path / 'nested.dcm'
    path.write_bytes(build_dicom(
        transfer_syntax=TS_IMPLICIT_VR_LE if implicit else TS_EXPLICIT_VR_LE,
        implicit_dataset=implicit, extra_dataset=[content],
    ))
    assert not dicom_is_packable(str(path))


@pytest.mark.parametrize('limit', ['depth', 'elements', 'meta'])
def test_parser_limits_skip_before_encoder(tmp_path, monkeypatch, limit):
    import filerepack.dicom as dicom
    payload = expl_elem(0x0010, 0x0020, 'LO', b'fixture')
    for _ in range(5):
        payload = sequence(payload, undefined_sequence=True, undefined_item=True)
    path = tmp_path / 'limited.dcm'
    original = build_dicom(extra_dataset=[payload])
    path.write_bytes(original)
    option = {'depth': '_MAX_DEPTH', 'elements': '_MAX_ELEMENTS', 'meta': '_MAX_META_BYTES'}
    monkeypatch.setattr(dicom, option[limit], 3)
    inspection = dicom.inspect_dicom(str(path))
    assert not inspection.eligible and 'limit' in inspection.reason
    def forbidden(*args, **kwargs):
        pytest.fail('Limit-exceeded input reached an encoder')
    monkeypatch.setattr('filerepack.medical._run_command', forbidden)
    assert pack_dcm(str(path)) is None
    assert path.read_bytes() == original


@pytest.mark.parametrize('damage', ['odd-length', 'invalid-vr', 'reserved', 'meta-boundary',
                                  'missing-delimiter', 'nonzero-delimiter'])
def test_invalid_headers_and_sequence_lengths(tmp_path, damage):
    content = build_dicom(extra_dataset=[sequence(expl_elem(0x0010, 0x0020, 'LO', b'test'),
                                                undefined_sequence=True)])
    if damage == 'meta-boundary':
        content = content[:140] + struct.pack('<I', 2) + content[144:]
    elif damage in ('missing-delimiter', 'nonzero-delimiter'):
        delim = struct.pack('<HHI', 0xFFFE, 0xE0DD, 0)
        content = content.replace(delim, b'' if damage == 'missing-delimiter' else
                                  struct.pack('<HHI', 0xFFFE, 0xE0DD, 2) + b'xx')
    else:
        position = content.index(b'\xe0\x7f\x10\x00OW')
        value = bytearray(content)
        if damage == 'odd-length':
            value[position + 8:position + 12] = struct.pack('<I', 31)
        elif damage == 'invalid-vr':
            value[position + 4:position + 6] = b'ZZ'
        else:
            value[position + 6:position + 8] = b'xx'
        content = bytes(value)
    path = tmp_path / 'malformed.dcm'
    path.write_bytes(content)
    assert not dicom_is_packable(str(path))


@pytest.mark.parametrize('undefined_sequence', [False, True])
@pytest.mark.parametrize('undefined_item', [False, True])
def test_unsigned_sequence_is_scanned_without_decoding(tmp_path, monkeypatch,
                                                       undefined_sequence, undefined_item):
    from filerepack.dicom import inspect_dicom
    path = tmp_path / 'unsigned.dcm'
    path.write_bytes(build_dicom(extra_dataset=[sequence(
        expl_elem(0x0010, 0x0020, 'LO', b'fixture'),
        undefined_sequence=undefined_sequence, undefined_item=undefined_item,
    )]))
    def forbidden(*args, **kwargs):
        pytest.fail('Eligibility inspection tried to decode pixels')
    monkeypatch.setattr('filerepack.dicom_verify._dependencies', forbidden)
    assert inspect_dicom(str(path)).eligible


def test_missing_verifier_prevents_encoding(tmp_path, monkeypatch, caplog):
    from test.dicom_fixtures import encoder_fixture
    path = tmp_path / 'unsigned.dcm'
    content = encoder_fixture()
    path.write_bytes(content)
    def missing():
        raise ImportError('absent decoder')
    def forbidden(*args, **kwargs):
        pytest.fail('An encoder ran without verification support')
    monkeypatch.setattr('filerepack.dicom_verify._dependencies', missing)
    monkeypatch.setattr('filerepack.medical._run_command', forbidden)
    assert pack_dcm(str(path)) is None
    assert path.read_bytes() == content
    assert 'verification unavailable' in caplog.text


@pytest.fixture
def decoded_backend():
    pydicom = pytest.importorskip('pydicom')
    numpy = pytest.importorskip('numpy')
    pytest.importorskip('jpeg_ls')
    from filerepack.dicom_verify import _dependencies
    try:
        _dependencies()
    except ImportError:
        pytest.skip('JPEG-LS decoding backend unavailable')
    return pydicom, numpy


def write_image(path, backend, *, layout='mono16', syntax=None):
    from filerepack.dicom import TS_EXPLICIT_VR_BE, TS_IMPLICIT_VR_LE
    from test.dicom_fixtures import encoder_fixture
    from io import BytesIO
    pydicom, numpy = backend
    ds = pydicom.dcmread(BytesIO(encoder_fixture()))
    ds.Rows = ds.Columns = 32
    ds.BitsAllocated = ds.BitsStored = 8 if layout == 'mono8' else 16
    ds.HighBit = ds.BitsStored - 1
    ds.PixelRepresentation = int(layout == 'signed16')
    ds.PatientID = 'SYNTHETIC_TEST'
    ds.add_new((0x0011, 0x0010), 'LO', 'FILEREPACK_TEST')
    ds.add_new((0x0011, 0x1001), 'LO', 'retain-private-value')
    item = pydicom.dataset.Dataset()
    item.add_new((0x0008, 0x1155), 'UI', '1.2.3.4.88')
    ds.add_new((0x0008, 0x1111), 'SQ', [item])
    frames = 3 if layout == 'multiframe' else 1
    if frames > 1:
        ds.NumberOfFrames = frames
        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2.1'  # Enhanced CT supports frames.
        ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    values = numpy.arange(32 * 32 * frames, dtype=numpy.int32) % 200
    if layout == 'signed16':
        values -= 100
    dtype = ('>' if syntax == TS_EXPLICIT_VR_BE else '<')
    dtype += ('i' if ds.PixelRepresentation else 'u') + str(ds.BitsAllocated // 8)
    ds.PixelData = values.astype(dtype).tobytes()
    if syntax:
        ds.file_meta.TransferSyntaxUID = syntax
        if not hasattr(pydicom, 'pixels'):
            ds.is_implicit_VR = syntax == TS_IMPLICIT_VR_LE
            ds.is_little_endian = syntax != TS_EXPLICIT_VR_BE
    save_image(pydicom, path, ds)
    return ds


def save_image(pydicom, path, ds):
    if hasattr(pydicom, 'pixels'):
        pydicom.dcmwrite(str(path), ds, enforce_file_format=True)
    else:
        pydicom.dcmwrite(str(path), ds, write_like_original=False)


def encoder_path(tool):
    import shutil
    path = shutil.which(tool)
    if not path:
        pytest.skip(tool + ' not installed')
    return path


def encode(source, output, tool='dcmcjpls'):
    import subprocess
    path = encoder_path(tool)
    args = [path] + (['--jpegls'] if tool == 'gdcmconv' else [])
    subprocess.run(args + [str(source), str(output)], check=True, capture_output=True)


@pytest.mark.parametrize('tool', ['gdcmconv', 'dcmcjpls'])
@pytest.mark.parametrize('layout', ['mono8', 'mono16', 'signed16', 'multiframe'])
def test_real_encoder_preserves_decoded_pixels_and_attributes(tmp_path, monkeypatch,
                                                             decoded_backend, tool, layout):
    from filerepack.dicom import TS_JPEG_LS_LOSSLESS
    from filerepack.utils import verify_output
    source = tmp_path / 'original.dcm'
    original_ds = write_image(source, decoded_backend, layout=layout)
    working = tmp_path / 'working.dcm'
    original_bytes = source.read_bytes()
    working.write_bytes(original_bytes)
    executable = encoder_path(tool)
    monkeypatch.setattr('filerepack.medical.resolve_tool',
                        lambda key: executable if key == tool else None)
    result = pack_dcm(str(working), lossy=True, jpeg_quality=1, png_quality='low')
    assert result is not None and result.replaced
    pydicom, numpy = decoded_backend
    output_ds = pydicom.dcmread(working)
    assert str(output_ds.file_meta.TransferSyntaxUID) == TS_JPEG_LS_LOSSLESS
    assert numpy.array_equal(original_ds.pixel_array, output_ds.pixel_array)
    assert output_ds.PatientID == original_ds.PatientID
    assert output_ds[(0x0011, 0x1001)].value == 'retain-private-value'
    assert source.read_bytes() == original_bytes
    for kind in ('dcm', 'dicom', 'dic'):
        assert verify_output(str(working), kind, source_path=str(source))


@pytest.mark.parametrize('tool', ['gdcmconv', 'dcmcjpls'])
@pytest.mark.parametrize('syntax', ['implicit', 'big-endian', 'rle'])
def test_real_supported_source_syntax(tmp_path, monkeypatch, decoded_backend, tool, syntax):
    import subprocess
    from filerepack.dicom import TS_EXPLICIT_VR_BE, TS_IMPLICIT_VR_LE
    from filerepack.dicom_verify import verify_dicom
    source = tmp_path / 'source.dcm'
    write_image(source, decoded_backend, syntax={
        'implicit': TS_IMPLICIT_VR_LE, 'big-endian': TS_EXPLICIT_VR_BE,
    }.get(syntax))
    if syntax == 'rle':
        encoded = tmp_path / 'rle.dcm'
        subprocess.run([encoder_path('gdcmconv'), '--rle', str(source), str(encoded)],
                       check=True, capture_output=True)
        source.write_bytes(encoded.read_bytes())
    assert dicom_is_packable(str(source))
    working = tmp_path / 'working.dcm'
    working.write_bytes(source.read_bytes())
    executable = encoder_path(tool)
    monkeypatch.setattr('filerepack.medical.resolve_tool',
                        lambda key: executable if key == tool else None)
    result = pack_dcm(str(working), keep_if_larger=False)
    if syntax == 'rle' and tool == 'dcmcjpls':
        # DCMTK's JPEG-LS tool has no RLE decoder; failure must retain the source.
        assert result is None
        assert working.read_bytes() == source.read_bytes()
        return
    assert result is not None and result.replaced
    assert verify_dicom(str(working), str(source))


@pytest.mark.parametrize('damage', ['pixels', 'frames', 'private', 'nested', 'patient',
                                  'bits', 'sop-uid', 'near-lossless', 'signature',
                                  'truncated', 'magic-only', 'decimal'])
def test_invalid_candidate_never_publishes(tmp_path, monkeypatch, decoded_backend, damage):
    import shutil
    from filerepack.dicom import TS_JPEG_LS_LOSSLESS
    from filerepack.dicom_verify import verify_dicom
    from filerepack.repack import _commit_output
    source = tmp_path / 'source.dcm'
    original = write_image(source, decoded_backend)
    if damage == 'decimal':
        original.add_new((0x0011, 0x1002), 'DS', '9007199254740992')
        save_image(decoded_backend[0], source, original)
    candidate = tmp_path / 'candidate.dcm'
    tool = 'dcmcjpls' if shutil.which('dcmcjpls') else 'gdcmconv'
    if damage == 'pixels':
        changed = tmp_path / 'changed.dcm'
        ds = write_image(changed, decoded_backend)
        values = bytearray(ds.PixelData)
        values[0] ^= 1
        ds.PixelData = bytes(values)
        save_image(decoded_backend[0], changed, ds)
        encode(changed, candidate, tool)
    else:
        encode(source, candidate, tool)
        pydicom, _ = decoded_backend
        ds = pydicom.dcmread(candidate)
        if damage == 'frames':
            ds.NumberOfFrames = 2
        elif damage == 'private':
            del ds[(0x0011, 0x1001)]
        elif damage == 'nested':
            ds[(0x0008, 0x1111)].value[0][(0x0008, 0x1155)].value = '1.2.3.999'
        elif damage == 'patient':
            ds.PatientID = 'CHANGED'
        elif damage == 'bits':
            ds.BitsStored = 8
            ds.HighBit = 7
        elif damage == 'sop-uid':
            ds.SOPInstanceUID = '1.2.3.999'
        elif damage == 'near-lossless':
            ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.4.81'
        elif damage == 'signature':
            ds.add_new((0xFFFA, 0xFFFA), 'SQ', [])
        elif damage == 'decimal':
            ds[(0x0011, 0x1002)].value = '9007199254740993'
        else:
            assert str(ds.file_meta.TransferSyntaxUID) == TS_JPEG_LS_LOSSLESS
        save_image(pydicom, candidate, ds)
        if damage == 'truncated':
            candidate.write_bytes(candidate.read_bytes()[:-10])
        elif damage == 'magic-only':
            candidate.write_bytes(b'\0' * 128 + b'DICM' + b'\0' * 8)
    content = source.read_bytes()
    assert not verify_dicom(str(candidate), str(source))
    assert _commit_output(str(candidate), str(source), len(content), verify='dic',
                          keep_if_larger=False) is None
    assert not candidate.exists()
    assert source.read_bytes() == content
    assert original.PatientID == 'SYNTHETIC_TEST'


@pytest.mark.parametrize('where', ['top-level', 'nested'])
def test_signature_macro_fixture_is_protected(tmp_path, monkeypatch, decoded_backend, where):
    # The certificate/signature bytes are placeholders, not a cryptographic test.
    pydicom, _ = decoded_backend
    path = tmp_path / 'signature.dcm'
    ds = write_image(path, decoded_backend)
    signed = pydicom.dataset.Dataset()
    signed.add_new((0x0400, 0x0005), 'US', 1)
    signed.add_new((0x0400, 0x0100), 'UI', '1.2.3.4.99')
    signed.add_new((0x0400, 0x0105), 'DT', '20260101000000')
    signed.add_new((0x0400, 0x0110), 'CS', 'X509_1993_SIG')
    signed.add_new((0x0400, 0x0115), 'OB', b'certificate-placeholder')
    signed.add_new((0x0400, 0x0120), 'OB', b'signature-placeholder')
    target = ds if where == 'top-level' else ds[(0x0008, 0x1111)].value[0]
    target.add_new((0xFFFA, 0xFFFA), 'SQ', [signed])
    save_image(pydicom, path, ds)
    content = path.read_bytes()
    from filerepack.dicom import inspect_dicom
    inspection = inspect_dicom(str(path))
    assert not inspection.eligible and 'Digital Signatures' in inspection.reason
    def forbidden(*args, **kwargs):
        pytest.fail('Signed instance reached an encoder')
    monkeypatch.setattr('filerepack.medical._run_command', forbidden)
    assert pack_dcm(str(path)) is None
    assert path.read_bytes() == content


@pytest.mark.parametrize('dryrun', [False, True])
def test_library_dicom_distinct_output(tmp_path, decoded_backend, dryrun):
    import shutil
    from filerepack import FileRepacker, RepackOptions
    from filerepack.utils import verify_output
    if not shutil.which('gdcmconv') and not shutil.which('dcmcjpls'):
        pytest.skip('DICOM encoder not installed')
    source, output = tmp_path / 'source.dicom', tmp_path / 'output.dicom'
    write_image(source, decoded_backend)
    original = source.read_bytes()
    summary = FileRepacker().repack(str(source), outfile=str(output),
                                   options=RepackOptions(dryrun=dryrun))
    assert source.read_bytes() == original
    assert summary.filepath == str(output)
    if dryrun:
        assert not output.exists()
    else:
        assert verify_output(str(output), 'dicom', source_path=str(source))


def test_cli_dicom_distinct_output(tmp_path, decoded_backend):
    import json
    import shutil
    from typer.testing import CliRunner
    from filerepack.__main__ import app
    from filerepack.utils import verify_output
    if not shutil.which('gdcmconv') and not shutil.which('dcmcjpls'):
        pytest.skip('DICOM encoder not installed')
    source = tmp_path / 'source.dic'
    directory = tmp_path / 'result'
    output = directory / source.name
    write_image(source, decoded_backend)
    content = source.read_bytes()
    result = CliRunner().invoke(app, ['repack', str(source), '--output-dir', str(directory),
                                      '--json', '--lossy', '--jpeg-quality', '1'])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report['output_file'] == str(output)
    assert source.read_bytes() == content
    assert verify_output(str(output), 'dic', source_path=str(source))


def test_opaque_un_sequence_cannot_hide_signatures(tmp_path):
    content = sequence(expl_empty_sq(0xFFFA, 0xFFFA)).replace(b'SQ\0\0', b'UN\0\0', 1)
    path = tmp_path / 'unknown.dcm'
    path.write_bytes(build_dicom(extra_dataset=[content]))
    assert not dicom_is_packable(str(path))


def test_lost_verification_support_rejects_candidate(tmp_path, monkeypatch,
                                                    decoded_backend, caplog):
    import shutil
    from filerepack.repack import _commit_output
    source, candidate = tmp_path / 'source.dcm', tmp_path / 'candidate.dcm'
    write_image(source, decoded_backend)
    encode(source, candidate, 'dcmcjpls' if shutil.which('dcmcjpls') else 'gdcmconv')
    original = source.read_bytes()
    def missing():
        raise ImportError('decoder no longer available')
    monkeypatch.setattr('filerepack.dicom_verify._dependencies', missing)
    assert _commit_output(str(candidate), str(source), len(original),
                          verify='dcm', keep_if_larger=False) is None
    assert not candidate.exists()
    assert source.read_bytes() == original
    assert 'verification unavailable' in caplog.text


@pytest.mark.parametrize('damage', ['missing-attribute', 'pixel-length'])
def test_invalid_image_attributes_prevent_encoding(tmp_path, monkeypatch,
                                                   decoded_backend, damage, caplog):
    path = tmp_path / 'invalid.dcm'
    ds = write_image(path, decoded_backend)
    if damage == 'missing-attribute':
        del ds.BitsStored
    else:
        ds.Rows = 33
    save_image(decoded_backend[0], path, ds)
    original = path.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid image attributes reached an encoder')
    monkeypatch.setattr('filerepack.medical._run_command', forbidden)
    assert pack_dcm(str(path)) is None
    assert path.read_bytes() == original
    assert 'invalid image attributes' in caplog.text
