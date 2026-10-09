"""Independent comparisons for the pilot's explicitly bounded preservation contracts."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile


class Unavailable(ValueError):
    """The comparison cannot establish its declared preservation contract."""


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def json_tokens(data):
    text = data.decode('utf-8-sig')

    def invalid_constant(value):
        raise ValueError('Non-standard JSON constant: ' + value)

    json.loads(text, parse_int=str, parse_float=str, parse_constant=invalid_constant)
    result = []
    quoted = False
    escaped = False
    for char in text:
        if quoted or char not in ' \r\n\t':
            result.append(char)
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
    return (data.startswith(b'\xef\xbb\xbf'), ''.join(result))


def image_fingerprint(path, limit, keep_meta=True):
    from PIL import Image
    with Path(path).open('rb') as stream:
        header = stream.read(26)
    # Pillow reduces 16-bit multichannel PNGs to 8-bit; that cannot prove bit equality.
    if header.startswith(b'\x89PNG\r\n\x1a\n') and header[24] == 16 and header[25] != 0:
        raise Unavailable('Pillow cannot establish all 16-bit multichannel PNG samples')
    frames = []
    decoded = 0
    with Image.open(path) as image:
        if image.format not in ('PNG', 'JPEG', 'WEBP', 'GIF'):
            raise ValueError('Raster signature disagrees with the sampled format')
        metadata = {key: image.info.get(key) for key in ('icc_profile', 'exif', 'xmp', 'comment')}
        metadata.update({key: image.info.get(key) for key in
                         ('gamma', 'srgb', 'chromaticity', 'dpi')})
        metadata['orientation'] = image.getexif().get(274)
        if not keep_meta:
            metadata.pop('exif')
            metadata.pop('comment')
        metadata['loop'] = image.info.get('loop')
        for index in range(getattr(image, 'n_frames', 1)):
            image.seek(index)
            decoded += image.width * image.height * 4
            if decoded > limit:
                raise Unavailable('Decoded raster exceeds comparison budget')
            pixels = image if image.mode in ('I', 'F', 'I;16', 'I;16B') else image.convert('RGBA')
            frames.append((image.size, pixels.mode, hashlib.sha256(pixels.tobytes()).hexdigest(),
                           image.info.get('duration')))
        if keep_meta and hasattr(image, 'text'):
            metadata['text'] = dict(image.text)
    return metadata, frames


def command(argv, timeout=25):
    value = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, check=False)
    if value.returncode:
        raise ValueError('Reader failed: ' + value.stderr.decode(errors='replace')[-1000:])
    return value.stdout


def svg_compare(source, output, limit):
    renderer = shutil.which('rsvg-convert')
    if renderer is None:
        raise Unavailable('Independent SVG renderer rsvg-convert is not installed')
    for path in (source, output):
        data = Path(path).read_text(encoding='utf-8-sig')
        if re.search(r'<!DOCTYPE|<!ENTITY', data, re.I):
            raise Unavailable('DTD-bearing SVG is outside the rendering contract')
        refs = re.findall(r'(?:href\s*=\s*[\'"]([^\'"]+)|url\(\s*([^)]*))', data)
        if any(not (ref.strip(' \t\'"').startswith(('#', 'data:')))
               for pair in refs for ref in pair if ref):
            raise Unavailable('SVG has external resources; standalone rendering is insufficient')
    with tempfile.TemporaryDirectory(prefix='svg-compare-') as folder:
        for size in (256, 1024):
            fingerprints = []
            for index, path in enumerate((source, output)):
                png = Path(folder) / '{}-{}.png'.format(size, index)
                command([renderer, '--width', str(size), '--height', str(size),
                         '--keep-aspect-ratio', '--output', str(png), str(path)])
                fingerprints.append(image_fingerprint(png, limit)[1])
            if fingerprints[0] != fingerprints[1]:
                raise ValueError('SVG rendered pixels differ at {}px'.format(size))
    return 'svg_render_256_1024'


def pdf_compare(source, output, limit):
    info_tool, render = shutil.which('pdfinfo'), shutil.which('pdftoppm')
    if not info_tool or not render:
        raise Unavailable('Poppler pdfinfo and pdftoppm are required')
    infos = [command([info_tool, str(path)]).decode(errors='replace') for path in (source, output)]
    pages = [int(re.search(r'^Pages:\s+(\d+)', info, re.M).group(1)) for info in infos]
    if pages[0] != pages[1]:
        raise ValueError('PDF page count differs')
    if pages[0] > 40:
        raise Unavailable('PDF exceeds the 40-page rendering budget')
    # Ignore storage/linearization details, retain reported document metadata and forms.
    ignored = ('File size:', 'Optimized:', 'PDF version:')
    normalized = ['\n'.join(line for line in info.splitlines()
                            if not line.startswith(ignored)) for info in infos]
    if normalized[0] != normalized[1]:
        raise ValueError('PDF document information differs')
    with tempfile.TemporaryDirectory(prefix='pdf-compare-') as folder:
        fingerprints = []
        for index, path in enumerate((source, output)):
            prefix = Path(folder) / ('page-' + str(index))
            command([render, '-r', '72', '-scale-to', '1600', '-png', str(path), str(prefix)],
                    timeout=40)
            files = sorted(Path(folder).glob(prefix.name + '-*.png'))
            if len(files) != pages[index]:
                raise ValueError('PDF reader did not render every page')
            fingerprints.append([image_fingerprint(png, limit)[1] for png in files])
        if fingerprints[0] != fingerprints[1]:
            raise ValueError('PDF rendered page pixels differ')
    return 'pdf_all_page_render_and_info'


def parquet_compare(source, output, limit):
    try:
        import pyarrow.parquet as parquet
    except ImportError as error:
        raise Unavailable('PyArrow is not installed') from error
    for path in (source, output):
        metadata = parquet.read_metadata(path)
        decoded = sum(metadata.row_group(i).column(j).total_uncompressed_size
                      for i in range(metadata.num_row_groups)
                      for j in range(metadata.num_columns))
        if decoded > limit:
            raise Unavailable('Declared Parquet payload exceeds comparison budget')
    tables = [parquet.read_table(path) for path in (source, output)]
    if sum(table.nbytes for table in tables) > limit:
        raise Unavailable('Decoded Parquet tables exceed comparison budget')
    if not tables[0].schema.equals(tables[1].schema, check_metadata=True):
        raise ValueError('Parquet schema or Arrow metadata differs')
    if not tables[0].equals(tables[1], check_metadata=True):
        raise ValueError('Parquet ordered values differ')
    metadata = [dict(parquet.read_metadata(path).metadata or {}) for path in (source, output)]
    # The declared Parquet contract allows the writer to add Arrow's schema record.
    # Decoded schemas are compared above; every pre-existing file metadata key is exact.
    if b'ARROW:schema' not in metadata[0]:
        metadata[1].pop(b'ARROW:schema', None)
    if metadata[0] != metadata[1]:
        raise ValueError('Parquet file key/value metadata differs')
    return 'parquet_arrow_schema_metadata_values'


def zip_compare(source, output, deep, limit, depth, keep_meta=True):
    if depth > 4:
        raise Unavailable('Nested archive exceeds comparison depth')
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output) as candidate:
        left, right = original.infolist(), candidate.infolist()
        if original.comment != candidate.comment or len(left) != len(right):
            raise ValueError('ZIP member count or archive comment differs')
        names = [entry.filename for entry in left]
        if len(names) != len(set(names)):
            raise Unavailable('Duplicate ZIP names are outside the comparison contract')
        if sum(entry.file_size for entry in left + right) > limit:
            raise Unavailable('Decoded ZIP exceeds comparison budget')
        fields = ('filename', 'date_time', 'external_attr', 'internal_attr', 'create_system',
                  'comment', 'extra')
        with tempfile.TemporaryDirectory(prefix='zip-compare-') as folder:
            for index, (before, after) in enumerate(zip(left, right)):
                if any(getattr(before, key) != getattr(after, key) for key in fields):
                    raise ValueError('ZIP member order or metadata differs: ' + before.filename)
                old, new = original.read(before), candidate.read(after)
                if old == new:
                    continue
                if not deep:
                    raise ValueError('Shallow ZIP member bytes differ: ' + before.filename)
                suffix = Path(before.filename).suffix.lower()
                paths = [Path(folder) / '{}-{}{}'.format(index, side, suffix)
                         for side in ('before', 'after')]
                paths[0].write_bytes(old)
                paths[1].write_bytes(new)
                compare(paths[0], paths[1], suffix.lstrip('.'), deep, limit, depth + 1, keep_meta)
    return 'zip_members_order_metadata_recursive' if deep else 'zip_members_bytes_order_metadata'


def compare(source, output, kind, deep=False, limit=64 * 1024**2, depth=0, keep_meta=True):
    if digest(source) == digest(output):
        return 'byte_identical'
    if kind in ('json', 'ipynb', 'geojson'):
        if json_tokens(Path(source).read_bytes()) != json_tokens(Path(output).read_bytes()):
            raise ValueError('JSON exact tokens/order/duplicates/BOM differ')
        return 'json_exact_tokens'
    if kind in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        if image_fingerprint(source, limit, keep_meta) != image_fingerprint(output, limit, keep_meta):
            raise ValueError('Decoded raster frames or tracked metadata differ')
        return 'raster_frames_tracked_metadata' if keep_meta else 'raster_frames_presentation_metadata'
    if kind == 'svg':
        return svg_compare(source, output, limit)
    if kind == 'pdf':
        return pdf_compare(source, output, limit)
    if kind in ('zip', 'npz'):
        return zip_compare(source, output, deep, limit, depth, keep_meta)
    if kind == 'parquet':
        return parquet_compare(source, output, limit)
    raise Unavailable('No independent preservation comparison for changed .' + kind)
