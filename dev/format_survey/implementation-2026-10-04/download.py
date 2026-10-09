"""Retrieve the pinned scientific/store corpus without changing the checked-in manifests."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    entries = []
    for row in json.loads((here / 'scientific-results.json').read_text()):
        entries.append((row['repository'].replace('/', '-') + '-' + Path(row['path']).name,
                        row['url'], row['sha256'], row['bytes']))
    for row in json.loads((here / 'spss-extra-results.json').read_text()):
        entries.append((row['name'], row['url'], row['sha256'], row['input_bytes']))
    for store in json.loads((here / 'store-manifests.json').read_text()):
        for row in store['keys']:
            entries.append((store['repository'].replace('/', '-') + '/' + row['key'],
                            row['url'], row['sha256'], row['bytes']))
    total = 0
    for key, url, checksum, size in entries:
        relative = Path(key)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('manifest path escape')
        total += size
        if size > 8 * 1024**2 or total > 64 * 1024**2:
            raise ValueError('pinned corpus download bound exceeded')
        raw = urllib.request.urlopen(url, timeout=30).read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError('pinned source size/checksum differs: ' + key)
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(f'Verified {len(entries)} keys; {total} bytes in {destination}')


if __name__ == '__main__':
    main()
