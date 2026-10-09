"""Critical orientation and color metadata survive default lossless compression."""

import struct

import pytest

from filerepack.images import pack_jpg, pack_png
from filerepack.candidates import commit_output
from filerepack.repack import FileRepacker
from filerepack.tools import resolve_tool
from filerepack.verification import image_fingerprint, verify_preservation

Image = pytest.importorskip('PIL.Image')


@pytest.mark.parametrize('kind', ['jpg', 'png'])
def test_default_retains_orientation_and_color_presentation(tmp_path, kind):
    if kind == 'jpg' and not (resolve_tool('jpegoptim') or resolve_tool('jpegtran')):
        pytest.skip('native JPEG optimizer required')
    if kind == 'png' and not (resolve_tool('oxipng') or resolve_tool('optipng')):
        pytest.skip('native PNG optimizer required')
    source = tmp_path / ('source.' + kind)
    image = Image.new('RGB', (64, 64), (20, 40, 60))
    exif = Image.Exif()
    exif[274] = 6
    options = {'exif': exif, 'icc_profile': b'preserved color profile'}
    if kind == 'png':
        from PIL.PngImagePlugin import PngInfo
        metadata = PngInfo()
        metadata.add(b'gAMA', struct.pack('>I', 45455))
        options.update(pnginfo=metadata, compress_level=0)
    image.save(source, **options)
    expected = image_fingerprint(str(source), kind)
    result = (pack_jpg if kind == 'jpg' else pack_png)(str(source), keep_if_larger=False)
    assert result is not None
    assert image_fingerprint(str(source), kind) == expected


@pytest.mark.parametrize('field', ['orientation', 'icc'])
def test_structurally_valid_candidate_cannot_change_presentation(tmp_path, field):
    source, output = tmp_path / 'source.jpg', tmp_path / 'candidate.jpg'
    image = Image.new('RGB', (8, 8))
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, exif=exif, icc_profile=b'original profile')
    if field == 'orientation':
        exif[274] = 1
    image.save(output, exif=exif,
               icc_profile=b'different profile' if field == 'icc' else b'original profile')
    assert not verify_preservation(str(source), str(output), 'jpg')


@pytest.mark.parametrize('source_mode,candidate_mode', [('1', 'L'), ('L', 'RGB')])
def test_png_equal_pixels_cannot_change_encoding(tmp_path, source_mode, candidate_mode):
    source, output = tmp_path / 'source.png', tmp_path / 'candidate.png'
    image = Image.new(source_mode, (64, 64))
    image.save(source, compress_level=0)
    image.convert(candidate_mode).save(output, compress_level=9)
    original = source.read_bytes()
    with Image.open(source) as left, Image.open(output) as right:
        assert left.convert('RGBA').tobytes() == right.convert('RGBA').tobytes()
    assert original[24:26] != output.read_bytes()[24:26]
    assert not verify_preservation(str(source), str(output), 'png')
    assert commit_output(str(output), str(source), len(original), verify='png',
                         lossless=True, keep_if_larger=False) is None
    assert source.read_bytes() == original
    assert not output.exists()


@pytest.mark.parametrize('tool', ['oxipng', 'optipng'])
@pytest.mark.parametrize('mode', ['1', 'L', 'RGB', 'RGBA', 'I;16', 'P'])
def test_native_png_preserves_encoding_and_samples(tmp_path, monkeypatch, tool, mode):
    executable = resolve_tool(tool)
    if executable is None:
        pytest.skip('native PNG optimizer required: ' + tool)
    import filerepack.images as images
    monkeypatch.setattr(images, 'resolve_tool',
                        lambda key: executable if key == tool else None)
    source = tmp_path / 'source.png'
    image = Image.new(mode, (64, 64))
    if mode == 'P':
        image.putpalette([0, 0, 0, 255, 255, 255] + [0] * 762)
    options = {'bits': 4} if mode == 'P' else {}
    image.save(source, compress_level=0, **options)
    original = source.read_bytes()
    expected = image_fingerprint(str(source), 'png')
    result = pack_png(str(source))
    assert result is not None and result.replaced
    assert source.stat().st_size < len(original)
    assert source.read_bytes()[24:26] == original[24:26]
    assert image_fingerprint(str(source), 'png') == expected


def test_smaller_invalid_ultra_candidate_does_not_hide_preserving_result(tmp_path, monkeypatch):
    import filerepack.images as images
    source = tmp_path / 'source.png'
    valid, invalid = tmp_path / 'valid.png', tmp_path / 'invalid.png'
    image = Image.new('RGB', (64, 64))
    image.save(source, compress_level=0)
    image.save(valid, compress_level=9)
    image.convert('1').save(invalid, compress_level=9)
    assert invalid.stat().st_size < valid.stat().st_size
    expected = valid.read_bytes()
    monkeypatch.setattr(images, '_png_lossless_candidates',
                        lambda *args: [str(valid), str(invalid)])
    summary = FileRepacker().repack(str(source), options={'ultra': True})
    assert summary.outcome.status == 'replaced'
    assert source.read_bytes() == expected
    assert not valid.exists() and not invalid.exists()


def test_all_invalid_png_candidates_refuse_publication(tmp_path, monkeypatch):
    import filerepack.images as images
    source, candidate = tmp_path / 'source.png', tmp_path / 'candidate.png'
    image = Image.new('RGB', (64, 64))
    image.save(source, compress_level=0)
    image.convert('1').save(candidate)
    original = source.read_bytes()
    monkeypatch.setattr(images, '_png_lossless_candidates', lambda *args: [str(candidate)])
    summary = FileRepacker().repack(str(source), options={'ultra': True})
    assert summary.outcome.status == 'failed'
    assert summary.outcome.reason_code == 'preservation_failed'
    assert source.read_bytes() == original
    assert not candidate.exists()


def test_magick_structurally_valid_changed_pixels_cannot_publish(tmp_path, monkeypatch):
    import filerepack.images as images
    source = tmp_path / 'source.bmp'
    Image.new('RGB', (64, 64), (20, 40, 60)).save(source)
    original = source.read_bytes()
    monkeypatch.setattr(images, 'resolve_tool', lambda key: '/controlled/convert')

    def encode(command, **kwargs):
        Image.new('RGB', (64, 64), (60, 40, 20)).save(command[-1], format='BMP')
        return object()

    monkeypatch.setattr(images, '_run_command', encode)
    assert images.pack_bmp(str(source), keep_if_larger=False) is None
    assert source.read_bytes() == original


def test_standalone_high_depth_jpx_is_not_losslessly_decoded_as_8bit(tmp_path):
    from PIL import features
    from filerepack.verification import VerificationUnavailable
    if not features.check('jpg_2000'):
        pytest.skip('OpenJPEG-backed Pillow required')
    source = tmp_path / 'source.jp2'
    Image.new('I;16', (32, 32), 0x1234).save(source, format='JPEG2000')
    with pytest.raises(VerificationUnavailable, match='unsigned 8-bit'):
        image_fingerprint(str(source), 'jp2')
