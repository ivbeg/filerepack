"""Scientific FITS arrays and metadata survive genuine CFITSIO compression."""

from pathlib import Path

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.fits import pack_fits, verify_fits
from filerepack.tools import resolve_szip


@pytest.fixture
def fits_backend():
    return pytest.importorskip('astropy.io.fits'), pytest.importorskip('numpy')


def write_fits(path, backend, *, dtype='int16', checksum=True, extension=False, table=False):
    fits, np = backend
    data = np.zeros((128, 128), dtype=dtype)
    if data.dtype.kind == 'f':
        words = [0x80000000, 0x7fc01234, 0x7fa05678, 0x7f800000, 0xff800000, 0x3f800000]
        if data.dtype.itemsize == 8:
            words = [0x8000000000000000, 0x7ff8000000001234, 0x7ff0000000005678,
                     0x7ff0000000000000, 0xfff0000000000000, 0x3ff0000000000000]
        data.view('u' + str(data.dtype.itemsize))[0, :6] = words
    else:
        data[0, :3] = [0, 1, 42]
    image = fits.ImageHDU(data) if extension else fits.PrimaryHDU(data)
    image.header['OBJECT'] = ('unchanged object', 'keep this comment')
    image.header.append(('CUSTOM', 'first', 'first occurrence'))
    image.header.append(('CUSTOM', 'second', 'second occurrence'))
    image.header.add_comment('first comment')
    image.header.add_comment('second comment')
    image.header.add_history('original processing')
    image.header['LONGKEY'] = 'a long header string ' * 20
    hdus = [fits.PrimaryHDU(), image] if extension else [image]
    if table:
        hdus.append(fits.BinTableHDU.from_columns([
            fits.Column(name='id', format='J', array=np.arange(30, dtype='int32')),
            fits.Column(name='value', format='8A', array=['keep'] * 30),
        ], name='CATALOG'))
    fits.HDUList(hdus).writeto(path, checksum=checksum)
    return data


@pytest.mark.parametrize('dtype', ['uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64',
                                 'float32', 'float64'])
@pytest.mark.parametrize('extension', [False, True])
def test_fits_preserves_all_image_bits_metadata_and_checksums(tmp_path, fits_backend,
                                                           dtype, extension):
    fits, np = fits_backend
    source = tmp_path / 'source.fits'
    original = tmp_path / 'original.fits'
    data = write_fits(source, fits_backend, dtype=dtype, extension=extension, table=True)
    original.write_bytes(source.read_bytes())
    result = pack_fits(str(source))
    assert result is not None and result.replaced
    assert source.stat().st_size < original.stat().st_size
    assert verify_fits(str(original), str(source), primary_image=not extension)
    with fits.open(source, do_not_scale_image_data=True, uint=False) as hdus:
        image = hdus[1]
        assert isinstance(image, fits.CompImageHDU)
        assert image.header['OBJECT'] == 'unchanged object'
        assert list(image.header['COMMENT']) == ['first comment', 'second comment']
        assert list(image.header['HISTORY']) == ['original processing']
        if np.dtype(dtype).kind == 'f':
            read = image.data.astype(data.dtype)
            assert read.view('u' + str(data.dtype.itemsize)).tobytes() == data.view(
                'u' + str(data.dtype.itemsize),
            ).tobytes()
        assert hdus[2].data['id'].tolist() == list(range(30))
    with fits.open(source, disable_image_compression=True) as hdus:
        assert all(hdu.verify_checksum() == 1 and hdu.verify_datasum() == 1 for hdu in hdus)


@pytest.mark.parametrize('extension', ['fits', 'fit', 'fts'])
@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'min_savings', 'outfile'])
def test_fits_aliases_keep_filename_and_publication_contract(tmp_path, fits_backend,
                                                           extension, mode):
    source = tmp_path / ('source.' + extension)
    write_fits(source, fits_backend)
    original = source.read_bytes()
    output = tmp_path / ('output.' + extension)
    result = FileRepacker().repack(str(source), outfile=str(output) if mode == 'outfile' else None,
                                  options=RepackOptions(dryrun=mode == 'dryrun',
                                                        min_savings=100 if mode == 'min_savings'
                                                        else None))
    assert Path(result.filepath).suffix == source.suffix
    if mode != 'inplace':
        assert source.read_bytes() == original
    if mode in ('inplace', 'outfile'):
        assert (output if mode == 'outfile' else source).stat().st_size < len(original)


@pytest.mark.parametrize(('scale', 'zero'), [(1, 0), (2.5, 3.0), (-2, 32768)])
def test_fits_explicit_scaling_cards_survive(tmp_path, fits_backend, scale, zero):
    fits, np = fits_backend
    source = tmp_path / 'scaled.fits'
    image = fits.PrimaryHDU(np.zeros((128, 128), dtype='int16'))
    image.header['BSCALE'] = (scale, 'scaling comment')
    image.header['BZERO'] = (zero, 'offset comment')
    image.writeto(source)
    original = tmp_path / 'original.fits'
    original.write_bytes(source.read_bytes())
    assert pack_fits(str(source)).replaced
    assert verify_fits(str(original), str(source), primary_image=True)
    with fits.open(source) as hdus:
        assert hdus[1].header.get('BSCALE', 1) == scale
        assert hdus[1].header.get('BZERO', 0) == zero
    with fits.open(source, disable_image_compression=True) as hdus:
        assert hdus[1].header['BSCALE'] == scale
        assert hdus[1].header['BZERO'] == zero
        assert hdus[1].header.comments['BSCALE'] == 'scaling comment'
        assert hdus[1].header.comments['BZERO'] == 'offset comment'


def test_fits_recompresses_existing_compressed_images(tmp_path, fits_backend):
    fits, np = fits_backend
    source = tmp_path / 'compressed.fits'
    image = fits.CompImageHDU(np.zeros((128, 128), dtype='int16'), compression_type='NOCOMPRESS')
    image.header['OBJECT'] = 'retain this'
    fits.HDUList([fits.PrimaryHDU(), image]).writeto(source)
    original = tmp_path / 'original.fits'
    original.write_bytes(source.read_bytes())
    assert pack_fits(str(source)).replaced
    assert verify_fits(str(original), str(source))


@pytest.mark.parametrize('fault', ['truncated', 'signature', 'checksum', 'candidate_values',
                                 'candidate_metadata', 'candidate_table', 'verify', 'bounds'])
def test_fits_failures_retain_original(tmp_path, fits_backend, monkeypatch, fault):
    from filerepack import fits as implementation
    fits, _np = fits_backend
    source = tmp_path / 'source.fits'
    write_fits(source, fits_backend, table=True)
    data = source.read_bytes()
    if fault == 'truncated':
        data = data[:-5]
    elif fault == 'signature':
        data = b'BAD!' + data[4:]
    elif fault == 'checksum':
        data = data[:3000] + bytes([data[3000] ^ 1]) + data[3001:]
    source.write_bytes(data)
    if fault.startswith('candidate_'):
        encode = implementation._compress_fits

        def corrupt(path, output, backend):
            primary = encode(path, output, backend)
            with fits.open(output, mode='update', do_not_scale_image_data=True,
                           uint=False) as candidate:
                if fault == 'candidate_values':
                    candidate[1].data[0, 0] = 20
                elif fault == 'candidate_table':
                    candidate[2].data['id'][0] = 20
                else:
                    candidate[1].header['OBJECT'] = 'changed'
                for hdu in candidate:
                    hdu.add_checksum()
            return primary

        monkeypatch.setattr(implementation, '_compress_fits', corrupt)
    elif fault == 'verify':
        monkeypatch.setattr(implementation, 'verify_fits', lambda *args, **kwargs: False)
    elif fault == 'bounds':
        monkeypatch.setattr(implementation, 'MAX_NATIVE_BYTES', 100)
    assert pack_fits(str(source)) is None
    assert source.read_bytes() == data


def test_missing_fits_extra_is_a_safe_skip(tmp_path, monkeypatch):
    source = tmp_path / 'source.fits'
    source.write_bytes(b'SIMPLE  = whatever')
    monkeypatch.setattr('filerepack.fits._backend', lambda: None)
    assert pack_fits(str(source)) is None
    assert source.read_bytes() == b'SIMPLE  = whatever'


def test_fits_works_in_nested_zip(tmp_path, fits_backend):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    import zipfile
    source = tmp_path / 'source.fits'
    write_fits(source, fits_backend, dtype='float32')
    original = source.read_bytes()
    archive = tmp_path / 'observations.zip'
    with zipfile.ZipFile(archive, 'w') as target:
        target.writestr('image.fit', original)
    FileRepacker().repack(str(archive))
    with zipfile.ZipFile(archive) as target:
        assert target.namelist() == ['image.fit']
        candidate = tmp_path / 'candidate.fit'
        candidate.write_bytes(target.read('image.fit'))
    assert candidate.stat().st_size < len(original)
    assert verify_fits(str(source), str(candidate), primary_image=True)
