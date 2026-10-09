"""A recognized header cannot authorize publishing an incomplete candidate."""

import gzip
import io
import sqlite3
import sys
import tarfile
import zipfile

import pytest

from filerepack import candidates, verification
from filerepack.commands import capture_bytes, check_command
from filerepack.utils import verify_output


@pytest.mark.parametrize('kind', sorted(verification.VALIDATORS))
def test_all_declared_validators_refuse_header_or_garbage_only(tmp_path, kind):
    prefixes = {
        'pdf': b'%PDF-1.4\n', 'jpg': b'\xff\xd8\xff', 'png': b'\x89PNG\r\n\x1a\n',
        'arrow': b'ARROW1\0\0', 'feather': b'ARROW1\0\0', 'parquet': b'PAR1PAR1',
        'gif': b'GIF89a', 'zip': b'PK\x03\x04', 'sqlite': b'SQLite format 3\0',
        'mp4': b'\0\0\0\x18ftypmp42', 'flac': b'fLaC', 'woff': b'wOFF',
        'woff2': b'wOF2', 'tar': b'broken' + b'\0' * 1018,
        'gz': b'\x1f\x8b', 'svgz': b'\x1f\x8b', 'xz': b'\xfd7zXZ\0',
        'bz2': b'BZh9', 'zst': b'\x28\xb5\x2f\xfd', 'lz4': b'\x04\x22\x4d\x18',
        'lz': b'LZIP', 'lzo': b'\x89LZO', 'z': b'\x1f\x9d', 'lzma': b'\x5d',
        'rar': b'Rar!\x1a\x07\0', '7z': b'7z\xbc\xaf\x27\x1c', 'cab': b'MSCF',
        'wim': b'MSWIM\0\0\0', 'ooxml': b'PK\x03\x04', 'jar': b'PK\x03\x04',
        'epub': b'PK\x03\x04', 'cbz': b'PK\x03\x04',
        'json': b'{"incomplete":', 'jsonl': b'{"incomplete":', 'xml': b'<root',
        'svg': b'<svg', 'qgs': b'<qgis', 'orc': b'ORC', 'avro': b'Obj\x01',
        'hdf5': b'\x89HDF\r\n\x1a\n', 'nc': b'CDF\x01', 'bmp': b'BM',
        'pcx': b'\x0a\x05\x01\x08', 'pnm': b'P6\n16 16\n255\n',
        'tif': b'II\x2a\0', 'dng': b'II\x2a\0', 'webp': b'RIFF\x10\0\0\0WEBP',
        'ico': b'\0\0\x01\0\x01\0', 'cur': b'\0\0\x02\0\x01\0',
        'icns': b'icns\0\0\0\x10', 'avif': b'\0\0\0\x18ftypavif',
        'heic': b'\0\0\0\x18ftypheic', 'jp2': b'\0\0\0\x0cjP  \r\n\x87\n',
        'jxl': b'\xff\x0a', 'exr': b'\x76\x2f\x31\x01',
        'psd': b'8BPS\0\x01', 'psb': b'8BPS\0\x02', 'nrrd': b'NRRD0005\n',
        'aseprite': b'\x80\0\0\0\xe0\xa5', 'blend': b'BLENDER-v300',
        'fits': b'SIMPLE  =                    T',
        'mov': b'\0\0\0\x18ftypqt  ', 'm4v': b'\0\0\0\x18ftypM4V ',
        'm4a': b'\0\0\0\x18ftypM4A ', '3gp': b'\0\0\0\x18ftyp3gp4',
        'mkv': b'\x1a\x45\xdf\xa3', 'webm': b'\x1a\x45\xdf\xa3',
        'avi': b'RIFF\x10\0\0\0AVI ', 'ogg': b'OggS', 'oga': b'OggS', 'opus': b'OggS',
        'mp3': b'ID3', 'ape': b'MAC ', 'wv': b'wvpk', 'tta': b'TTA1',
        'video': b'\0\0\0\x18ftypmp42',
        'asf': b'\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\0\xaa\0\x62\xce\x6c',
        'wmv': b'\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\0\xaa\0\x62\xce\x6c',
        'ts': b'\x47', 'mts': b'\x47', 'm2ts': b'\x47',
        'tga': b'\0\0\x02' + b'\0' * 9 + b'\x10\0\x10\0\x18\0',
    }
    path = tmp_path / ('broken.' + kind)
    path.write_bytes(prefixes.get(kind, b'not a complete supported file'))
    assert not verify_output(str(path), kind)


@pytest.mark.parametrize('kind', [None, 'unknown-format'])
def test_missing_or_unknown_validator_preserves_destination_and_removes_candidate(tmp_path, kind):
    source, output = tmp_path / 'original', tmp_path / 'candidate'
    source.write_bytes(b'original bytes')
    output.write_bytes(b'new')
    assert candidates.commit_output(str(output), str(source), 14, verify=kind) is None
    assert source.read_bytes() == b'original bytes'
    assert not output.exists()


def test_gzip_full_read_detects_crc_and_truncation(tmp_path):
    path = tmp_path / 'a.gz'
    valid = gzip.compress(b'payload' * 100)
    path.write_bytes(valid)
    assert verify_output(str(path), 'gz')
    for invalid in (valid[:-1], valid[:-8] + b'\0' * 8):
        path.write_bytes(invalid)
        assert not verify_output(str(path), 'gz')


def test_valid_gzip_with_different_decoded_content_is_not_published(tmp_path):
    source, output = tmp_path / 'a.gz', tmp_path / 'candidate.gz'
    original = gzip.compress(b'original content' * 100, compresslevel=1)
    source.write_bytes(original)
    output.write_bytes(gzip.compress(b'wrong content'))
    assert candidates.commit_output(str(output), str(source), len(original),
                                    verify='gz', lossless=True) is None
    assert source.read_bytes() == original
    assert not output.exists()


def test_zip_checks_member_crc_not_only_central_directory(tmp_path):
    path = tmp_path / 'a.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('member', b'unique member contents')
    valid = path.read_bytes()
    assert verify_output(str(path), 'zip')
    path.write_bytes(valid.replace(b'unique member contents', b'broken member contents'))
    assert not verify_output(str(path), 'zip')


def test_tar_requires_payload_and_complete_end_blocks(tmp_path):
    path = tmp_path / 'a.tar'
    with tarfile.open(path, 'w') as archive:
        info = tarfile.TarInfo('member')
        info.size = 2000
        archive.addfile(info, io.BytesIO(b'a' * info.size))
    valid = path.read_bytes()
    assert verify_output(str(path), 'tar')
    path.write_bytes(valid[:512])
    assert not verify_output(str(path), 'tar')


def test_sqlite_uses_integrity_check_without_sidecars(tmp_path):
    path = tmp_path / 'a.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE items (value TEXT)')
        db.execute('INSERT INTO items VALUES (?)', ('kept',))
    assert verify_output(str(path), 'sqlite')
    assert sorted(item.name for item in tmp_path.iterdir()) == ['a.db']
    path.write_bytes(path.read_bytes()[:100])
    assert not verify_output(str(path), 'sqlite')


@pytest.mark.parametrize('extension', ['png', 'jpg', 'gif', 'tif', 'webp'])
def test_images_must_decode_completely_and_match_pixels(tmp_path, extension):
    image = pytest.importorskip('PIL.Image')
    source, output = tmp_path / ('a.' + extension), tmp_path / ('b.' + extension)
    image.new('RGB', (16, 16), (12, 34, 56)).save(source)
    image.new('RGB', (16, 16), (56, 34, 12)).save(output)
    original = source.read_bytes()
    assert verify_output(str(source), extension)
    assert not verification.verify_preservation(str(source), str(output), extension)
    source.write_bytes(original[:len(original) // 2])
    assert not verify_output(str(source), extension)


def test_unavailable_image_parser_is_failure(tmp_path, monkeypatch):
    path = tmp_path / 'a.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\n')
    monkeypatch.setitem(sys.modules, 'PIL', None)
    assert not verify_output(str(path), 'png')


def test_validator_process_failure_timeout_and_output_limit():
    assert capture_bytes([sys.executable, '-c', 'print("checked")']) == b'checked\n'
    assert not check_command([sys.executable, '-c', 'raise SystemExit(3)'])
    assert capture_bytes([sys.executable, '-c', 'print("x" * 10000)'], max_output=10) is None
    assert not check_command([sys.executable, '-c', 'import time; time.sleep(5)'], timeout=1)


def test_svg_and_svgz_require_svg_root(tmp_path):
    source = tmp_path / 'a.svg'
    source.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>')
    assert verify_output(str(source), 'svg')
    source.write_bytes(b'<different-root/>')
    assert not verify_output(str(source), 'svg')
    compressed = tmp_path / 'a.svgz'
    compressed.write_bytes(gzip.compress(source.read_bytes()))
    assert not verify_output(str(compressed), 'svgz')


def test_media_requires_matching_container_and_full_decode(tmp_path):
    from filerepack.tools import resolve_tool
    import subprocess
    ffmpeg = resolve_tool('ffmpeg')
    if ffmpeg is None or resolve_tool('ffprobe') is None:
        pytest.skip('ffmpeg/ffprobe required for real media corpus')
    source = tmp_path / 'movie.mp4'
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=16x16:r=5', '-t', '0.4', '-c:v', 'mpeg4', '-y', str(source)],
                   check=True, capture_output=True)
    original = source.read_bytes()
    assert verify_output(str(source), 'mp4')
    assert not verify_output(str(source), 'flac')
    source.write_bytes(original[:len(original) // 2])
    assert not verify_output(str(source), 'mp4')


def test_unavailable_media_decoder_refuses_publication(tmp_path, monkeypatch):
    source = tmp_path / 'movie.mp4'
    source.write_bytes(b'\0\0\0\x18ftypmp42')
    monkeypatch.setattr(verification, 'resolve_tool', lambda name: None)
    result = verification.validate_output(str(source), 'mp4')
    assert not result.ok and 'required' in result.reason


def test_arrow_table_schema_metadata_and_ordered_values_are_compared(tmp_path):
    pa = pytest.importorskip('pyarrow')
    source, candidate = tmp_path / 'a.arrow', tmp_path / 'b.arrow'
    table = pa.table({'value': [1, 2, 3]}).replace_schema_metadata({b'custom': b'preserved'})

    def write(path, data):
        with pa.OSFile(str(path), 'wb') as sink, pa.ipc.new_file(sink, data.schema) as writer:
            writer.write_table(data)

    write(source, table)
    write(candidate, table)
    assert verify_output(str(candidate), 'arrow')
    assert verification.verify_preservation(str(source), str(candidate), 'arrow')
    write(candidate, table.take([2, 1, 0]))
    assert not verification.verify_preservation(str(source), str(candidate), 'arrow')
    write(candidate, table.replace_schema_metadata({b'custom': b'changed'}))
    assert not verification.verify_preservation(str(source), str(candidate), 'arrow')


def test_icon_checks_every_embedded_resolution(tmp_path):
    image = pytest.importorskip('PIL.Image')
    path = tmp_path / 'a.ico'
    image.new('RGB', (64, 64), (12, 34, 56)).save(path, sizes=[(16, 16), (32, 32), (64, 64)])
    original = path.read_bytes()
    assert verify_output(str(path), 'ico')
    # Corrupt a small resource that the default image loader would never select.
    import struct
    size, offset = struct.unpack_from('<II', original, 14)
    broken = bytearray(original)
    broken[offset + size - 5] ^= 1
    path.write_bytes(broken)
    assert not verify_output(str(path), 'ico')


def test_icns_checks_container_extent_and_all_sizes(tmp_path):
    image = pytest.importorskip('PIL.Image')
    path = tmp_path / 'a.icns'
    image.new('RGB', (32, 32), (12, 34, 56)).save(path)
    original = path.read_bytes()
    assert verify_output(str(path), 'icns')
    path.write_bytes(original[:-1])
    assert not verify_output(str(path), 'icns')


def test_archive_tester_requires_the_declared_container(tmp_path):
    from filerepack.tools import resolve_szip
    if resolve_szip() is None:
        pytest.skip('7z/7zz required for real container inspection')
    path = tmp_path / 'disguised.rar'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('kept', b'unchanged')
    assert verify_output(str(path), 'zip')
    assert not verify_output(str(path), 'rar')
    assert not verify_output(str(path), '7z')


@pytest.mark.parametrize('kind', ['woff', 'woff2'])
def test_font_parser_decompiles_real_tables_and_checks_checksums(tmp_path, kind):
    pytest.importorskip('fontTools')
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    builder = FontBuilder(1000, isTTF=True)
    glyphs = ['.notdef', 'A']
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap({65: 'A'})
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in glyphs})
    builder.setupHorizontalMetrics({name: (600, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'Validation', 'styleName': 'Regular'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    builder.font.flavor = kind
    path = tmp_path / ('a.' + kind)
    try:
        builder.save(path)
    except ImportError:
        pytest.skip('fontTools WOFF compression extras missing')
    original = path.read_bytes()
    assert verify_output(str(path), kind)
    if kind == 'woff':
        corrupted = bytearray(original)
        corrupted[44 + 16] ^= 1  # First directory entry's table checksum.
        path.write_bytes(corrupted)
    else:
        path.write_bytes(original[:len(original) // 2])
    assert not verify_output(str(path), kind)
