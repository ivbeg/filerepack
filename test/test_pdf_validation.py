"""Real PDF protection gates, candidate retention and object/stream preservation."""

import io
from pathlib import Path
import subprocess

import pytest

from filerepack import documents, pdf_streams
from filerepack.models import RepackOptions
from filerepack.pdf_verify import inspect_pdf, pdf_fingerprint
from filerepack.repack import FileRepacker
from filerepack.tools import resolve_tool
from test.pdf_fixtures import pdf_bytes


@pytest.fixture(autouse=True)
def qpdf_required():
    if resolve_tool('qpdf') is None:
        pytest.skip('qpdf 11+ required for real PDF structure/object comparison')


@pytest.mark.parametrize('marker', [
    b'<< /Type /Sig >>', b'<< /FT /Sig >>', b'<< /ByteRange [0 10 20 30] >>',
    b'<< /SigFlags 2 >>', b'<< /Perms << >> >>', b'<< /Type /DocTimeStamp >>',
])
@pytest.mark.parametrize('options', [{}, {'lossy': True}, {'pdf_profile': 'screen'},
                                     {'jpeg_quality': 75}, {'pdf_linearize': True}])
@pytest.mark.parametrize('entry', ['pdf', 'ai', 'library'])
def test_protection_anywhere_gates_all_rewriters(tmp_path, monkeypatch, marker, options, entry):
    source = tmp_path / ('protected.ai' if entry == 'ai' else 'protected.pdf')
    original = pdf_bytes(marker=marker)
    source.write_bytes(original)
    assert inspect_pdf(str(source)).protected

    def forbidden(*args, **kwargs):
        raise AssertionError('A protected PDF reached a rewriting operation')

    monkeypatch.setattr(documents, '_run_command', forbidden)
    monkeypatch.setattr(documents, '_maybe_walk_pdf_images', forbidden)
    if entry == 'library':
        FileRepacker().repack(str(source), options=RepackOptions(**options))
    else:
        helper = documents.pack_ai if entry == 'ai' else documents.pack_pdf
        assert helper(str(source), **options) is None
    assert source.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == [source.name]


def test_encrypted_pdf_gates_ghostscript_and_direct_stream_walking(tmp_path, monkeypatch):
    pikepdf = pytest.importorskip('pikepdf')
    source, destination = tmp_path / 'encrypted.pdf', tmp_path / 'candidate.pdf'
    with pikepdf.Pdf.open(io.BytesIO(pdf_bytes())) as pdf:
        pdf.save(source, encryption=pikepdf.Encryption(owner='secret', user='', R=4))
    original = source.read_bytes()
    assert inspect_pdf(str(source)).protected
    monkeypatch.setattr(documents, '_run_command', lambda *a, **k: pytest.fail('rewriter called'))
    assert documents.pack_pdf(str(source), lossy=True) is None
    assert not pdf_streams.rebuild_pdf_images(str(source), str(destination))
    assert source.read_bytes() == original
    assert not destination.exists()


@pytest.mark.parametrize('candidate_kind', ['larger', 'truncated', 'changed', 'failed'])
@pytest.mark.parametrize('dryrun', [False, True])
def test_valid_walked_candidate_survives_bad_or_larger_qpdf_alternative(
    tmp_path, monkeypatch, candidate_kind, dryrun,
):
    source, walked = tmp_path / 'a.pdf', tmp_path / 'walked.pdf'
    original, packed = pdf_bytes(padding=5000), pdf_bytes()
    source.write_bytes(original)
    walked.write_bytes(packed)
    assert pdf_fingerprint(str(source)) == pdf_fingerprint(str(walked))
    monkeypatch.setattr(documents, '_maybe_walk_pdf_images',
                        lambda *a: (str(walked), str(walked)))
    outputs = []

    def encode(command, **kwargs):
        outputs.append(Path(command[-1]))
        if candidate_kind == 'failed':
            return None
        content = {'larger': pdf_bytes(padding=2000), 'truncated': b'%PDF-1.4\n',
                   'changed': pdf_bytes(text=b'changed document')}[candidate_kind]
        outputs[-1].write_bytes(content)
        return object()

    monkeypatch.setattr(documents, '_run_command', encode)
    result = documents.pack_pdf(str(source), dryrun=dryrun)
    assert result is not None and result.outsize == len(packed)
    assert result.replaced is not dryrun
    assert source.read_bytes() == (original if dryrun else packed)
    assert not walked.exists()
    assert all(not path.exists() for path in outputs)


def test_original_is_retained_when_every_valid_alternative_is_larger(tmp_path, monkeypatch):
    source = tmp_path / 'a.pdf'
    original = pdf_bytes()
    source.write_bytes(original)
    monkeypatch.setattr(documents, '_maybe_walk_pdf_images', lambda *a: (str(source), None))

    def encode(command, **kwargs):
        Path(command[-1]).write_bytes(pdf_bytes(padding=1000))
        return object()

    monkeypatch.setattr(documents, '_run_command', encode)
    result = documents.pack_pdf(str(source), keep_if_larger=False)
    assert result is not None and not result.replaced
    assert source.read_bytes() == original


def test_actual_qpdf_compression_preserves_document_graph(tmp_path):
    source = tmp_path / 'a.pdf'
    source.write_bytes(pdf_bytes(padding=10000))
    before = pdf_fingerprint(str(source))
    result = documents.pack_pdf(str(source))
    assert result is not None and result.replaced
    assert result.outsize < result.insize
    assert inspect_pdf(str(source)).rewritable
    assert pdf_fingerprint(str(source)) == before


def test_linearization_is_an_explicit_constraint(tmp_path):
    source = tmp_path / 'a.pdf'
    source.write_bytes(pdf_bytes(padding=10000))
    before = pdf_fingerprint(str(source))
    result = documents.pack_pdf(str(source), pdf_linearize=True, keep_if_larger=False)
    assert result is not None and result.replaced
    assert inspect_pdf(str(source)).linearized
    subprocess.run([resolve_tool('qpdf'), '--check-linearization', str(source)],
                   check=True, capture_output=True)
    assert pdf_fingerprint(str(source)) == before


def test_no_protection_parser_refuses_all_rewriting_paths(tmp_path, monkeypatch, caplog):
    source = tmp_path / 'a.pdf'
    original = pdf_bytes()
    source.write_bytes(original)
    monkeypatch.setattr('filerepack.pdf_verify.resolve_tool', lambda name: None)
    monkeypatch.setitem(__import__('sys').modules, 'pikepdf', None)
    monkeypatch.setattr(documents, '_run_command', lambda *a, **k: pytest.fail('rewriter called'))
    assert documents.pack_pdf(str(source), lossy=True) is None
    assert source.read_bytes() == original
    assert 'inspection unavailable' in caplog.text


def test_pdf_stream_walker_preserves_real_image_pixels_and_host_graph(tmp_path, monkeypatch):
    pikepdf = pytest.importorskip('pikepdf')
    image = pytest.importorskip('PIL.Image')
    encoded = io.BytesIO()
    image.new('RGB', (16, 16), (12, 34, 56)).save(encoded, format='JPEG')
    packed = encoded.getvalue()
    # A removable JPEG comment changes encoded bytes, preserving decoded samples.
    comment = b'\xff\xfe' + (1002).to_bytes(2, 'big') + b'x' * 1000
    original_image = packed[:2] + comment + packed[2:]
    source, destination = tmp_path / 'a.pdf', tmp_path / 'packed.pdf'
    with pikepdf.Pdf.new() as pdf:
        page = pdf.add_blank_page(page_size=(100, 100))
        stream = pikepdf.Stream(pdf, original_image)
        for key, value in pikepdf.Dictionary(
            Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image, Width=16, Height=16,
            ColorSpace=pikepdf.Name.DeviceRGB, BitsPerComponent=8, Filter=pikepdf.Name.DCTDecode,
        ).items():
            stream[key] = value
        page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=stream))
        pdf.save(source)
    before = pdf_fingerprint(str(source))
    monkeypatch.setattr(pdf_streams, '_pack_stream_bytes', lambda *a: packed)
    assert pdf_streams.rebuild_pdf_images(str(source), str(destination))
    assert pdf_fingerprint(str(destination)) == before
    with pikepdf.Pdf.open(destination) as pdf:
        assert pdf.pages[0].Resources.XObject['/Im0'].read_raw_bytes() == packed


def test_pikepdf_inspection_fallback_without_qpdf(tmp_path, monkeypatch):
    pytest.importorskip('pikepdf')
    source = tmp_path / 'a.pdf'
    source.write_bytes(pdf_bytes(marker=b'<< /Type /Sig >>'))
    monkeypatch.setattr('filerepack.pdf_verify.resolve_tool', lambda name: None)
    result = inspect_pdf(str(source))
    assert result.valid and result.protected and not result.rewritable


@pytest.mark.parametrize('entry', ['cli', 'bulk', 'worker'])
def test_linearization_option_reaches_every_entry_point(tmp_path, entry):
    source = tmp_path / 'a.pdf'
    source.write_bytes(pdf_bytes(padding=10000))
    if entry == 'worker':
        from filerepack.jobs import process_file_job
        result = process_file_job({'filepath': str(source), 'pdf_linearize': True})
        assert result['status'] == 'replaced'
        assert result['final_size'] < result['original_size']
    else:
        from typer.testing import CliRunner
        from filerepack.__main__ import app
        command = (['repack', str(source)] if entry == 'cli'
                   else ['bulk', str(tmp_path), '--jobs', '1'])
        result = CliRunner().invoke(app, command + ['--pdf-linearize', '--quiet'])
        assert result.exit_code == 0, result.output
    assert inspect_pdf(str(source)).linearized


def test_lossy_linearization_validates_the_ghostscript_stage(tmp_path, monkeypatch):
    source = tmp_path / 'a.pdf'
    source.write_bytes(pdf_bytes(padding=10000))
    original = pdf_fingerprint(str(source))
    real_run = documents._run_command

    def encode(command, **kwargs):
        if command[0] == '/controlled/gs':
            target = next(arg.split('=', 1)[1] for arg in command
                          if arg.startswith('-sOutputFile='))
            Path(target).write_bytes(pdf_bytes(text=b'intended lossy result'))
            return object()
        return real_run(command, **kwargs)

    qpdf = resolve_tool('qpdf')
    monkeypatch.setattr(documents, 'resolve_tool',
                        lambda key: qpdf if key == 'qpdf' else '/controlled/gs')
    monkeypatch.setattr(documents, '_run_command', encode)
    result = documents.pack_pdf(str(source), lossy=True, pdf_linearize=True)
    assert result is not None and result.replaced
    assert inspect_pdf(str(source)).linearized
    assert pdf_fingerprint(str(source)) != original
