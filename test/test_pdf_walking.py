import shutil
import subprocess
import zlib
import io
import re

import pytest

from filerepack.pdf_streams import rebuild_pdf_images
from filerepack.pdf_verify import pdf_fingerprint

pikepdf = pytest.importorskip('pikepdf')


def compressed_image_pdf(path, encoded, kind, mode, soft_mask=False):
    from pikepdf import Array, Dictionary, Name
    with pikepdf.Pdf.new() as pdf:
        image = pdf.make_stream(encoded)
        image.Type, image.Subtype = Name.XObject, Name.Image
        image.Width, image.Height, image.BitsPerComponent = 32, 32, 8
        image.ColorSpace = {'L': Name.DeviceGray, 'CMYK': Name.DeviceCMYK}.get(mode,
                                                                                 Name.DeviceRGB)
        image.Filter = Name.DCTDecode if kind == 'JPEG' else Name.JPXDecode
        channels = 1 if mode == 'L' else 4 if mode == 'CMYK' else 3
        image.Decode = Array([0, 1] * channels)
        if mode == 'RGBA':
            image.SMaskInData = 1
        if soft_mask:
            mask = pdf.make_stream(zlib.compress(bytes([128]) * 32 * 32))
            mask.Type, mask.Subtype, mask.ColorSpace = Name.XObject, Name.Image, Name.DeviceGray
            mask.Width, mask.Height, mask.BitsPerComponent = 32, 32, 8
            mask.Filter = Name.FlateDecode
            image.SMask = mask
        page = pdf.add_blank_page(page_size=(32, 32))
        page.Resources = Dictionary(XObject=Dictionary(Im=image))
        page.Contents = pdf.make_stream(b'q 32 0 0 32 0 0 cm /Im Do Q')
        pdf.save(path, compress_streams=True, recompress_flate=False)


@pytest.mark.parametrize('kind,mode', [('JPEG', 'L'), ('JPEG', 'RGB'), ('JPEG', 'CMYK'),
                                      ('JPEG2000', 'L'), ('JPEG2000', 'RGB'),
                                      ('JPEG2000', 'RGBA')])
def test_dct_jpx_samples_host_semantics_and_independent_render(tmp_path, monkeypatch, kind, mode):
    renderer = shutil.which('pdftoppm')
    if not renderer or not shutil.which('qpdf'):
        pytest.skip('Poppler and qpdf independent readers required')
    from PIL import Image, features
    if kind == 'JPEG2000' and not features.check('jpg_2000'):
        pytest.skip('OpenJPEG-backed Pillow required')
    import filerepack.pdf_streams as walker
    image = Image.new(mode, (32, 32), {'L': 100, 'RGB': (20, 40, 60),
                                      'CMYK': (10, 20, 30, 40),
                                      'RGBA': (20, 40, 60, 128)}[mode])
    buffer = io.BytesIO()
    image.save(buffer, format=kind)
    packed = buffer.getvalue()
    if kind == 'JPEG':
        comment = b'\xff\xfe' + (4098).to_bytes(2, 'big') + b'x' * 4096
        original = packed[:2] + comment + packed[2:]
    else:
        original = packed + (4104).to_bytes(4, 'big') + b'free' + b'x' * 4096
    source, output = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    compressed_image_pdf(source, original, kind, mode, soft_mask=mode == 'RGB')
    expected = pdf_fingerprint(str(source))
    monkeypatch.setattr(walker, '_pack_stream_bytes', lambda *args: packed)
    assert rebuild_pdf_images(str(source), str(output))
    assert output.stat().st_size < source.stat().st_size
    assert pdf_fingerprint(str(output)) == expected
    with pikepdf.open(output) as pdf:
        result = pdf.pages[0].Resources.XObject.Im
        assert (int(result.Width), int(result.Height), int(result.BitsPerComponent)) == (32, 32, 8)
        assert result.read_raw_bytes() == packed
        if mode == 'RGB':
            assert result.SMask.read_bytes() == bytes([128]) * 32 * 32
    for path, prefix in ((source, 'before'), (output, 'after')):
        subprocess.run([renderer, '-r', '72', '-png', str(path), str(tmp_path / prefix)],
                       check=True, capture_output=True)
    with Image.open(tmp_path / 'before-1.png') as before, Image.open(
        tmp_path / 'after-1.png'
    ) as after:
        assert before.mode == after.mode and before.size == after.size
        assert before.tobytes() == after.tobytes()


def test_jpx_encoded_16bit_cannot_hide_behind_8bit_pdf_dictionary(tmp_path):
    from PIL import Image, features
    from filerepack.pdf_verify import _image_hash
    from filerepack.verification import VerificationUnavailable
    if not features.check('jpg_2000'):
        pytest.skip('OpenJPEG-backed Pillow required')
    buffer = io.BytesIO()
    Image.new('I;16', (32, 32), 0x1234).save(buffer, format='JPEG2000')
    encoded = buffer.getvalue()
    with pytest.raises(VerificationUnavailable, match='unsigned 8-bit'):
        _image_hash(encoded, {'/BitsPerComponent': 8})
    source, output = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    compressed_image_pdf(source, encoded, 'JPEG2000', 'L')
    original = source.read_bytes()
    assert not rebuild_pdf_images(str(source), str(output))
    assert source.read_bytes() == original
    assert not output.exists()


def test_encoded_dimensions_must_agree_with_pdf_host():
    from PIL import Image
    from filerepack.pdf_verify import _image_hash
    buffer = io.BytesIO()
    Image.new('RGB', (32, 32)).save(buffer, format='JPEG')
    with pytest.raises(ValueError, match='dimensions disagree'):
        _image_hash(buffer.getvalue(), {'/Width': 16, '/Height': 32, '/BitsPerComponent': 8})


@pytest.mark.parametrize('mode,precision,components', [('L', 8, 1), ('RGB', 8, 3),
                                                     ('RGBA', 8, 4), ('I;16', 16, 1)])
def test_jpx_precision_matches_openjpeg_inventory(tmp_path, mode, precision, components):
    from PIL import Image, features
    from filerepack.pdf_verify import _image_hash
    from filerepack.verification import VerificationUnavailable
    reader = shutil.which('opj_dump')
    if not reader or not features.check('jpg_2000'):
        pytest.skip('standalone OpenJPEG inventory required')
    source = tmp_path / 'source.jp2'
    Image.new(mode, (32, 32)).save(source, format='JPEG2000')
    result = subprocess.run([reader, '-i', str(source)], check=True, capture_output=True,
                            text=True)
    assert [int(value) for value in re.findall(r'prec=(\d+)', result.stdout)] == (
        [precision] * components
    )
    assert re.search(r'numcomps=' + str(components) + r'\b', result.stdout)
    if precision == 8:
        assert _image_hash(source.read_bytes(), {'/BitsPerComponent': 8})
    else:
        with pytest.raises(VerificationUnavailable, match='unsigned 8-bit'):
            _image_hash(source.read_bytes(), {'/BitsPerComponent': 8})


def make_pdf(path, predictor=1, cycles=False):
    from pikepdf import Dictionary, Name, Array
    pdf = pikepdf.Pdf.new()
    width, height = 64, 64
    row = bytes([10, 20, 30]) * width
    raw = row * height if predictor == 1 else (b'\0' + row) * height
    image = pdf.make_stream(zlib.compress(raw, 0))
    image.Type, image.Subtype = Name.XObject, Name.Image
    image.Width, image.Height, image.BitsPerComponent = width, height, 8
    image.ColorSpace, image.Filter = Name.DeviceRGB, Name.FlateDecode
    if predictor != 1:
        image.DecodeParms = Dictionary(Predictor=predictor, Columns=width,
                                        Colors=3, BitsPerComponent=8)
    form = pdf.make_stream(b'q 64 0 0 64 0 0 cm /Shared Do Q')
    form.Type, form.Subtype = Name.XObject, Name.Form
    form.BBox = Array([0, 0, 64, 64])
    form.Resources = Dictionary(XObject=Dictionary(Shared=image))
    if cycles:
        form.Resources.XObject.UnusedCycle = form
    for _ in range(2):
        page = pdf.add_blank_page(page_size=(64, 64))
        page.Resources = Dictionary(XObject=Dictionary(Nested=form, Direct=image))
        page.Contents = pdf.make_stream(b'/Nested Do')
    # Keep the deliberately weak Flate bytes on pikepdf 8/9 and newer versions.
    pdf.save(path, compress_streams=True, recompress_flate=False)
    pdf.close()


@pytest.mark.parametrize('predictor', [1, 10, 12, 15])
def test_flate_predictors_shared_nested_forms_preserved(tmp_path, predictor):
    if not shutil.which('qpdf'):
        pytest.skip('qpdf independent structural reader required')
    source, output = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    make_pdf(source, predictor)
    expected = pdf_fingerprint(str(source))
    options = {}
    assert rebuild_pdf_images(str(source), str(output), options)
    assert options['_pdf_work']['images'] == options['_pdf_work']['changed'] == 1
    assert pdf_fingerprint(str(output)) == expected
    assert output.stat().st_size < source.stat().st_size


def test_resource_cycle_encodes_shared_image_once(tmp_path):
    if not shutil.which('qpdf'):
        pytest.skip('qpdf required')
    source, output = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    make_pdf(source, cycles=True)
    options = {}
    assert rebuild_pdf_images(str(source), str(output), options)
    assert options['_pdf_work']['images'] == 1


def test_fixed_renderer_pixels_equal(tmp_path):
    renderer = shutil.which('pdftoppm')
    if not renderer or not shutil.which('qpdf'):
        pytest.skip('Poppler and qpdf independent readers required')
    from PIL import Image
    source, output = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    make_pdf(source, predictor=12)
    assert rebuild_pdf_images(str(source), str(output))
    for path, prefix in ((source, 'before'), (output, 'after')):
        subprocess.run([renderer, '-r', '72', '-png', str(path), str(tmp_path / prefix)],
                       check=True, capture_output=True)
    for page in (1, 2):
        with Image.open(tmp_path / f'before-{page}.png') as before, Image.open(
            tmp_path / f'after-{page}.png'
        ) as after:
            assert before.mode == after.mode and before.size == after.size
            assert before.tobytes() == after.tobytes()


@pytest.mark.parametrize('variant', ['mask', 'soft-mask', 'indexed', 'icc', 'gray16'])
def test_color_masks_and_high_depth_render_identically(tmp_path, variant):
    renderer = shutil.which('pdftoppm')
    if not renderer or not shutil.which('qpdf'):
        pytest.skip('Poppler and qpdf independent readers required')
    from pikepdf import Array, Name, String
    from PIL import Image, ImageCms
    source, output = tmp_path / 'source.pdf', tmp_path / 'output.pdf'
    make_pdf(source)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        image = pdf.pages[0].Resources.XObject.Direct
        width, height = int(image.Width), int(image.Height)
        if variant == 'mask':
            image.ImageMask = True
            image.BitsPerComponent = 1
            del image.ColorSpace
            raw = bytes([0xAA]) * ((width + 7) // 8) * height
        elif variant == 'indexed':
            image.ColorSpace = Array([Name.Indexed, Name.DeviceRGB, 1,
                                      String(bytes([10, 20, 30, 90, 80, 70]))])
            raw = bytes([0, 1]) * (width * height // 2)
        elif variant == 'gray16':
            image.ColorSpace, image.BitsPerComponent = Name.DeviceGray, 16
            raw = bytes([0x12, 0x34]) * width * height
        else:
            raw = bytes([10, 20, 30]) * width * height
            if variant == 'icc':
                profile = pdf.make_stream(ImageCms.ImageCmsProfile(
                    ImageCms.createProfile('sRGB')).tobytes())
                profile.N = 3
                image.ColorSpace = Array([Name.ICCBased, profile])
            else:
                mask = pdf.make_stream(zlib.compress(bytes([128]) * width * height, 0))
                mask.Type, mask.Subtype, mask.ColorSpace = Name.XObject, Name.Image, Name.DeviceGray
                mask.Width, mask.Height, mask.BitsPerComponent = width, height, 8
                image.SMask = mask
        image.write(zlib.compress(raw, 0), filter=Name.FlateDecode)
        pdf.save(source, compress_streams=True, recompress_flate=False)
    expected = pdf_fingerprint(str(source))
    assert rebuild_pdf_images(str(source), str(output))
    assert pdf_fingerprint(str(output)) == expected
    for path, prefix in ((source, 'before'), (output, 'after')):
        subprocess.run([renderer, '-r', '72', '-png', str(path), str(tmp_path / prefix)],
                       check=True, capture_output=True)
    for page in (1, 2):
        with Image.open(tmp_path / f'before-{page}.png') as before, Image.open(
            tmp_path / f'after-{page}.png'
        ) as after:
            assert before.mode == after.mode and before.size == after.size
            assert before.tobytes() == after.tobytes()
