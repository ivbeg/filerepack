"""Identify downloaded samples by content and inventory ZIP members without extraction."""

import argparse
import collections
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from collect import extension, write_json
from verify import digest, json_tokens


def inspect(path, kind, limit):
    with path.open('rb') as stream:
        header = stream.read(1024)
    signatures = {
        'png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'jpg': header.startswith(b'\xff\xd8\xff'),
        'webp': header.startswith(b'RIFF') and header[8:12] == b'WEBP',
        'pdf': b'%PDF-' in header,
        'parquet': header.startswith(b'PAR1'),
    }
    if kind in signatures and not signatures[kind]:
        raise ValueError('Extension does not match the expected content signature')
    if kind in ('png', 'jpg', 'webp'):
        from PIL import Image
        with Image.open(path) as image:
            result = {'reader': 'Pillow', 'detected_format': image.format,
                      'width': image.width, 'height': image.height,
                      'frames': getattr(image, 'n_frames', 1), 'mode': image.mode}
            image.verify()
        return result
    if kind in ('json', 'ipynb'):
        json_tokens(path.read_bytes())
        return {'reader': 'stdlib JSON syntax', 'detected_format': 'JSON',
                'application_validation': 'Notebook schema is not validated'}
    if kind == 'svg':
        data = path.read_bytes()
        if re.search(b'<!DOCTYPE|<!ENTITY', data, re.I):
            return {'reader': 'signature', 'detected_format': 'SVG candidate',
                    'limitation': 'DTD-bearing SVG is not parsed by this inspector'}
        root = ET.fromstring(data)
        if root.tag not in ('svg', '{http://www.w3.org/2000/svg}svg'):
            raise ValueError('XML root is not SVG')
        return {'reader': 'stdlib XML root', 'detected_format': 'SVG'}
    if kind in ('zip', 'npz'):
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            total = sum(entry.file_size for entry in entries)
            return {'reader': 'stdlib ZIP directory', 'detected_format': 'ZIP',
                    'members': len(entries), 'declared_decoded_bytes': total,
                    'encrypted_members': sum(bool(entry.flag_bits & 1) for entry in entries),
                    'duplicate_names': len(entries) - len({x.filename for x in entries}),
                    'decoded_budget_exceeded': total > limit,
                    'application_validation': 'NPZ arrays are not unpickled'}
    if kind == 'parquet':
        import pyarrow.parquet as parquet
        metadata = parquet.read_metadata(path)
        return {'reader': 'PyArrow footer', 'detected_format': 'Parquet',
                'rows': metadata.num_rows, 'row_groups': metadata.num_row_groups,
                'columns': metadata.num_columns}
    if kind == 'pdf':
        tool = shutil.which('pdfinfo')
        if tool is None:
            return {'reader': 'signature', 'detected_format': 'PDF',
                    'limitation': 'Poppler pdfinfo is unavailable'}
        process = subprocess.run([tool, str(path)], capture_output=True, timeout=20)
        if process.returncode:
            raise ValueError('Poppler rejects source: ' +
                             process.stderr.decode(errors='replace')[-300:])
        info = process.stdout.decode(errors='replace')
        pages = re.search(r'^Pages:\s+(\d+)', info, re.M)
        return {'reader': 'Poppler pdfinfo', 'detected_format': 'PDF',
                'pages': int(pages.group(1)) if pages else None}
    return {'reader': 'none', 'detected_format': 'unknown'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    run = args.run
    config = json.loads((run / 'config.json').read_text())
    samples = json.loads((run / 'samples.json').read_text())
    inspected, nested = [], []
    for sample in samples:
        if sample['download_status'] != 'downloaded':
            continue
        path = run / sample['local_path']
        row = {'blob_sha': sample['blob_sha'], 'format': sample['format'],
               'repository': sample['repository'], 'path': sample['path']}
        try:
            if digest(path) != sample['sha256']:
                raise ValueError('Frozen source hash differs')
            row.update(inspect(path, sample['format'], config['decoded_byte_limit']))
            row['status'] = 'reader_accepted'
            if sample['format'] in ('zip', 'npz'):
                with zipfile.ZipFile(path) as archive:
                    for entry in archive.infolist():
                        nested.append({'parent_blob_sha': sample['blob_sha'],
                                       'parent_format': sample['format'],
                                       'member_path': entry.filename,
                                       'format': extension(entry.filename),
                                       'decoded_bytes': entry.file_size,
                                       'compressed_bytes': entry.compress_size,
                                       'is_directory': entry.is_dir()})
        except Exception as error:
            row.update(status='reader_rejected',
                       reason='{}: {}'.format(type(error).__name__, error))
        inspected.append(row)
    write_json(run / 'input-inspection.json', inspected)
    write_json(run / 'input-inspection-summary.json',
               dict(collections.Counter(row['status'] for row in inspected)))
    with (run / 'nested-inventory.jsonl').open('w', encoding='utf-8') as stream:
        for row in nested:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    print('Inspected {} inputs; inventoried {} first-level ZIP members'.format(
        len(inspected), len(nested)))


if __name__ == '__main__':
    main()
