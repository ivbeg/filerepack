"""Qualify temporary CAR copies against Apple's independently computed inventory."""

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from filerepack import FileRepacker
from filerepack.car import CarStore
from filerepack.format_support import Budget, FormatLimits


def digests(value):
    if isinstance(value, dict):
        if 'SHA1Digest' in value:
            yield value['SHA1Digest'].lower()
        for item in value.values():
            yield from digests(item)
    elif isinstance(value, list):
        for item in value:
            yield from digests(item)


def metadata(value):
    if isinstance(value, dict):
        return {key: metadata(item) for key, item in value.items()
                if key not in ('SizeOnDisk', 'SHA1Digest')}
    if isinstance(value, list):
        return [metadata(item) for item in value]
    return value


def inventory(path):
    native = subprocess.run(['/usr/bin/assetutil', '--info', str(path)],
                            capture_output=True, check=True, timeout=60)
    data = json.loads(native.stdout)
    store = CarStore(path.read_bytes(), Budget(FormatLimits()))
    blocks = {hashlib.sha256(block).hexdigest() for block in store.blocks.values()}
    reported = set(digests(data))
    if not reported or reported - blocks:
        raise ValueError('Native digest is not the SHA-256 of a complete allocated CSI block')
    return data, len(reported)


def qualify(source):
    original = source.read_bytes()
    with tempfile.TemporaryDirectory(prefix='filerepack-car-qualification-') as directory:
        target = Path(directory) / 'Assets.car'
        shutil.copyfile(source, target)
        before, before_count = inventory(target)
        baseline = subprocess.run(['/usr/bin/assetutil', '--validate-file', str(target)],
                                  capture_output=True, timeout=60)
        result = FileRepacker().repack(str(target))
        after, after_count = inventory(target)
        validation = subprocess.run(['/usr/bin/assetutil', '--validate-file', str(target)],
                                    capture_output=True, timeout=60)
        equal = metadata(before) == metadata(after)
        retained = source.read_bytes() == original
        return {'source': str(source), 'sha256': hashlib.sha256(original).hexdigest(),
                'original_size': len(original), 'final_size': target.stat().st_size,
                'status': result.outcome.status, 'reason': result.outcome.reason,
                'native_reader_before': 0, 'native_reader_after': 0,
                'native_metadata_equal': equal, 'native_digest_blocks_before': before_count,
                'native_digest_blocks_after': after_count,
                'native_validate_before_exit': baseline.returncode,
                'native_validate_exit': validation.returncode, 'source_unchanged': retained,
                'qualified': equal and retained and before_count == after_count and
                validation.returncode == baseline.returncode}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('catalogs', type=Path, nargs='+')
    args = parser.parse_args()
    samples = [qualify(path) for path in args.catalogs]
    report = {'platform': platform.platform(), 'python': platform.python_version(),
              'reader': '/usr/bin/assetutil', 'reader_sha256': hashlib.sha256(
                  Path('/usr/bin/assetutil').read_bytes()).hexdigest(),
              'digest_contract': 'SHA1Digest is SHA-256 of the complete allocated CSI block',
              'samples': samples, 'qualified': all(item['qualified'] for item in samples)}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    if not report['qualified']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
