"""Measure source/zlib/Zopfli selection on pinned captures and controlled boundary records."""

import argparse
import gzip
import hashlib
from importlib import metadata
import json
import os
import platform
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from filerepack import FileRepacker, RepackOptions  # noqa: E402
from filerepack.resume import adapter_fingerprint  # noqa: E402


def record(payload, kind):
    return (b'WARC/1.1\r\nWARC-Type: ' + kind.encode() + b'\r\n'
            b'WARC-Record-ID: <urn:uuid:01234567-89ab-cdef-0123-456789abcdef>\r\n'
            b'WARC-Date: 2026-10-07T00:00:00Z\r\n'
            b'WARC-Target-URI: https://example.org/\r\nContent-Length: ' +
            str(len(payload)).encode() + b'\r\n\r\n' + payload + b'\r\n\r\n')


def members(raw):
    result = []
    while raw:
        decoder = zlib.decompressobj(31)
        decoded = decoder.decompress(raw, 32 * 1024 * 1024 + 1)
        if not decoder.eof or len(decoded) > 32 * 1024 * 1024:
            raise ValueError('Invalid or excessive source gzip member')
        result.append(decoded)
        raw = decoder.unused_data
    return result


def record_hashes(raw):
    result = []
    while raw:
        header_end = raw.index(b'\r\n\r\n') + 4
        header = raw[:header_end].split(b'\r\n')
        if not header[0].startswith(b'WARC/1.'):
            raise ValueError('Invalid record prefix')
        lengths = [int(line.split(b':', 1)[1]) for line in header
                   if line.lower().startswith(b'content-length:')]
        if len(lengths) != 1:
            raise ValueError('Ambiguous record length')
        end = header_end + lengths[0] + 4
        if raw[end - 4:end] != b'\r\n\r\n':
            raise ValueError('Incomplete record or incorrect trailer')
        result.append(hashlib.sha256(raw[:end]).hexdigest())
        raw = raw[end:]
    return result


def work_bytes(directory):
    total = 0
    for path in directory.rglob('*'):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            pass
    return total


def fetch(url, maximum):
    request = urllib.request.Request(url, headers={'User-Agent': 'filerepack-qualification'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('Qualification download exceeds bound')
    return raw


def worker(source, ultra, output):
    path = Path(source)
    summary = FileRepacker().repack(str(path), options=RepackOptions(ultra=ultra))
    final = path.read_bytes()
    Path(output).write_text(json.dumps({
        'status': summary.outcome.status, 'reason': summary.outcome.reason,
        'details': summary.results[0].details, 'final_bytes': len(final),
        'final_sha256': hashlib.sha256(final).hexdigest(),
        'decoded_sha256': hashlib.sha256(gzip.decompress(final)).hexdigest(),
        'member_sha256': [hashlib.sha256(value).hexdigest() for value in members(final)],
    }))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--worker', nargs=3)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker[0], args.worker[1] == 'true', args.worker[2])
        return
    samples, errors = [], []
    try:
        commit = json.loads(fetch('https://api.github.com/repos/webrecorder/warcio/commits/master',
                                  1024 * 1024))['sha']
        for name in ('example.warc.gz', 'example-resource.warc.gz', 'post-test.warc.gz',
                     'example-bad-non-chunked.warc.gz'):
            url = f'https://raw.githubusercontent.com/webrecorder/warcio/{commit}/test/data/{name}'
            samples.append((name, fetch(url, 8 * 1024 * 1024), {'url': url, 'commit': commit}))
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    random_source = random.Random(20261007)
    for size in (16 * 1024, 64 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024):
        for kind, binary in (('response', False), ('resource', True)):
            payload = (random_source.randbytes(size) if binary else
                       (b'Captured text and metadata.\n' * (size // 27 + 1))[:size])
            raw = record(payload, kind)
            samples.append((f'controlled-{kind}-{size}', gzip.compress(raw, compresslevel=1,
                                                                      mtime=0),
                            {'generated': 'Python Random(20261007); raw payload length pinned'}))
    for kind, payload in [('request', b'POST / HTTP/1.1\r\n\r\nbody=preserved'),
                          ('metadata', b'creator: preserved\r\n'), ('revisit', b'')]:
        samples.append((f'controlled-{kind}', gzip.compress(record(payload, kind),
                                                           compresslevel=1, mtime=0),
                        {'generated': 'Fixed framing and payload'}))
    cases = []
    with tempfile.TemporaryDirectory(prefix='filerepack-warc-qualification-') as temporary:
        for name, data, provenance in samples:
            for ultra in (False, True):
                directory = Path(temporary) / (name + ('-ultra' if ultra else '-zlib'))
                directory.mkdir()
                source, result = directory / 'capture.warc.gz', directory / 'result.json'
                source.write_bytes(data)
                started, peak_rss, peak_scratch = time.monotonic(), 0, 0
                with (directory / 'log').open('wb') as log:
                    process = subprocess.Popen([sys.executable, __file__, '--worker', str(source),
                                                str(ultra).lower(), str(result)],
                                               stdout=log, stderr=log,
                                               env={**os.environ, 'TMPDIR': str(directory),
                                                    'TMP': str(directory), 'TEMP': str(directory)},
                                               start_new_session=os.name == 'posix')
                    monitor = psutil.Process(process.pid)
                    while process.poll() is None:
                        try:
                            resident = sum(p.memory_info().rss for p in
                                           [monitor, *monitor.children(recursive=True)])
                            peak_rss = max(peak_rss, resident)
                        except psutil.Error:
                            pass
                        # Child-owned temporary files use the task's TMPDIR.
                        peak_scratch = max(peak_scratch, work_bytes(directory))
                        if time.monotonic() - started > 150:
                            from filerepack.format_support import _terminate
                            _terminate(process, monitor)
                            break
                        time.sleep(0.02)
                row = {'name': name, 'ultra': ultra, 'provenance': provenance,
                       'source_sha256': hashlib.sha256(data).hexdigest(), 'source_bytes': len(data),
                       'seconds': time.monotonic() - started, 'sampled_peak_rss_bytes': peak_rss,
                       'sampled_work_bytes': peak_scratch}
                if result.exists():
                    row.update(json.loads(result.read_text()))
                    row['decoded_equal'] = row['decoded_sha256'] == hashlib.sha256(
                        gzip.decompress(data)).hexdigest()
                    final_members = members(source.read_bytes())
                    row['one_record_per_member'] = all(len(record_hashes(value)) == 1
                                                      for value in final_members)
                    row['record_hashes_equal'] = record_hashes(gzip.decompress(data)) == [
                        digest for value in final_members for digest in record_hashes(value)]
                    row['output_member_contract_satisfied'] = (
                        row['one_record_per_member'] if row['status'] == 'replaced' else
                        row['final_sha256'] == row['source_sha256'])
                else:
                    row['status'] = 'worker_failed'
                cases.append(row)
                print(name, ultra, row['status'], flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'schema_version': 1, 'adapter_sha256': adapter_fingerprint(),
                                      'zlib': zlib.ZLIB_RUNTIME_VERSION, 'python': sys.version,
                                      'zopfli': metadata.version('zopfli'),
                                      'platform': platform.platform(),
                                      'harness_sha256': hashlib.sha256(
                                          Path(__file__).read_bytes()).hexdigest(),
                                      'cutoff': 512 * 1024, 'errors': errors, 'cases': cases},
                                     indent=2) + '\n')


if __name__ == '__main__':
    main()
