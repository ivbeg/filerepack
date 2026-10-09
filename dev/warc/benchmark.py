"""Read-only record compression research; never publish rewritten user archives.

Example: venv/bin/python dev/warc/benchmark.py --download-warcio --cc-index
CC-MAIN-2026-39 --output dev/warc/results-2026-10-05.json INPUT.warc.gz
"""

import argparse
import ctypes
import ctypes.util
import gzip
import hashlib
import io
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from filerepack.format_support import Budget, FormatLimits  # noqa: E402
from filerepack.warc import _read_header, _record_chunks  # noqa: E402

MAX_INPUT = 8 * 1024 * 1024
MAX_DECODED = 32 * 1024 * 1024
MAX_SLOW_RECORD = 512 * 1024
UA = 'filerepack-warc-research/0.1 (bounded record compression experiment)'
WARCIOS = ('example.warc.gz', 'example-resource.warc.gz', 'post-test.warc.gz',
           'example-iana.org-chunked.warc', 'example-bad-non-chunked.warc.gz')
CC_TARGETS = ('docs.python.org/3/library/json.html', 'www.python.org/', 'www.wikipedia.org/',
              'developer.mozilla.org/en-US/docs/Web/JavaScript', 'www.bbc.com/',
              'www.w3.org/TR/html52/')


def fetch(url, maximum=MAX_INPUT, headers=None, expected_range=None):
    request = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=15) as response:
        if expected_range and (response.status != 206 or
                               not response.headers.get('Content-Range', '').startswith(
                                   'bytes ' + expected_range + '/')):
            raise ValueError('Server did not honor the requested byte range')
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Download exceeds experiment input cap')
    return data


def split_records(raw):
    reader = io.BytesIO(raw)
    budget = Budget(FormatLimits(decoded=MAX_DECODED))
    records = []
    while True:
        start = reader.tell()
        header = _read_header(reader, budget, None)
        if header is None:
            return records
        data = b''.join(_record_chunks(reader, *header, budget, None))
        records.append((start, data))


def decode_source(data):
    members, raw_chunks = {}, []
    position, count = 0, 0
    if not data.startswith(b'\x1f\x8b'):
        return split_records(data), members, 0
    while data:
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(data, MAX_DECODED - position + 1)
        if len(raw) + position > MAX_DECODED or not decoder.eof:
            raise ValueError('Corrupt or oversized source member')
        length = len(data) - len(decoder.unused_data)
        try:
            records = split_records(raw)
        except ValueError:
            records = []  # A valid input may split a record across members.
        if len(records) == 1 and records[0][1] == raw:
            members[position] = data[:length]
        raw_chunks.append(raw)
        position += len(raw)
        data = decoder.unused_data
        count += 1
    return split_records(b''.join(raw_chunks)), members, count


def zlib_encode(raw, level=9, memory=8, strategy=zlib.Z_DEFAULT_STRATEGY):
    compressor = zlib.compressobj(level, zlib.DEFLATED, 31, memory, strategy)
    parts = [compressor.compress(raw[start:start + 65536])
             for start in range(0, len(raw), 65536)]
    return b''.join(parts) + compressor.flush()


def libdeflate_encode(raw, level):
    name = ctypes.util.find_library('deflate')
    if not name:
        raise ImportError('libdeflate shared library is unavailable')
    lib = ctypes.CDLL(name)
    lib.libdeflate_alloc_compressor.argtypes = [ctypes.c_int]
    lib.libdeflate_alloc_compressor.restype = ctypes.c_void_p
    lib.libdeflate_gzip_compress_bound.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    lib.libdeflate_gzip_compress_bound.restype = ctypes.c_size_t
    lib.libdeflate_gzip_compress.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_void_p, ctypes.c_size_t]
    lib.libdeflate_gzip_compress.restype = ctypes.c_size_t
    lib.libdeflate_free_compressor.argtypes = [ctypes.c_void_p]
    compressor = lib.libdeflate_alloc_compressor(level)
    if not compressor:
        raise MemoryError('libdeflate compressor allocation failed')
    try:
        bound = lib.libdeflate_gzip_compress_bound(compressor, len(raw))
        target = ctypes.create_string_buffer(bound)
        source = ctypes.create_string_buffer(raw)
        length = lib.libdeflate_gzip_compress(compressor, source, len(raw), target, bound)
        if not length:
            raise ValueError('libdeflate failed to encode')
        return target.raw[:length]
    finally:
        lib.libdeflate_free_compressor(compressor)


def slow_encode(name, source):
    process = subprocess.run([sys.executable, __file__, '--worker', name, str(source)],
                             capture_output=True, check=True, timeout=10)
    return process.stdout, float(process.stderr)


def worker(name, source):
    raw = Path(source).read_bytes()
    started = time.perf_counter()
    if name.startswith('zopfli'):
        from zopfli.gzip import compress
        output = compress(raw, numiterations=int(name.removeprefix('zopfli')))
    else:
        output = libdeflate_encode(raw, int(name.removeprefix('libdeflate')))
    duration = time.perf_counter() - started
    sys.stdout.buffer.write(output)
    print(duration, file=sys.stderr)


def measure_sample(label, data, directory):
    records, originals, member_count = decode_source(data)
    measured = []
    for number, (offset, raw) in enumerate(records):
        sizes, timings, failures = {}, {}, {}
        configurations = {'zlib9': (9, 8, zlib.Z_DEFAULT_STRATEGY),
                          'zlib9_mem9': (9, 9, zlib.Z_DEFAULT_STRATEGY),
                          'zlib9_filtered': (9, 9, zlib.Z_FILTERED),
                          'zlib8': (8, 8, zlib.Z_DEFAULT_STRATEGY),
                          'zlib6': (6, 8, zlib.Z_DEFAULT_STRATEGY)}
        for name, configuration in configurations.items():
            started = time.perf_counter()
            output = zlib_encode(raw, *configuration)
            timings[name] = time.perf_counter() - started
            assert zlib.decompress(output, 31) == raw
            sizes[name] = len(output)
        original = originals.get(offset)
        if original and zlib.decompress(original, 31) == raw:
            sizes['original'] = len(original)
        source = directory / 'record.bin'
        source.write_bytes(raw)
        for name in ('libdeflate9', 'libdeflate12', 'zopfli5', 'zopfli15'):
            if len(raw) > MAX_SLOW_RECORD:
                failures[name] = 'record exceeds 512 KiB buffered-encoder cap'
                continue
            try:
                output, timings[name] = slow_encode(name, source)
                assert zlib.decompress(output, 31) == raw
                sizes[name] = len(output)
            except (subprocess.SubprocessError, ImportError) as exc:
                failures[name] = str(exc)[:200]
        if shutil.which('zstd'):
            for level in (3, 9, 19):
                name = 'zstd' + str(level)
                started = time.perf_counter()
                output = subprocess.run(['zstd', '-q', '-T1', '-' + str(level), '--check',
                                         '-c', str(source)], capture_output=True,
                                        timeout=10, check=True).stdout
                timings[name] = time.perf_counter() - started
                decoded = subprocess.run(['zstd', '-q', '-d', '-c'], input=output,
                                         capture_output=True, check=True, timeout=10).stdout
                assert decoded == raw
                sizes[name] = len(output)
        measured.append({'record': number, 'decoded_bytes': len(raw),
                         'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': sizes,
                         'encode_seconds': timings, 'skipped': failures})
    return {'sample': label, 'source_bytes': len(data), 'source_members': member_count,
            'source_sha256': hashlib.sha256(data).hexdigest(), 'records': measured}


def common_crawl_sources(index, errors):
    sources = []
    for target in CC_TARGETS:
        query = 'https://index.commoncrawl.org/' + index + '-index?' + urllib.parse.urlencode(
            {'url': target, 'output': 'json', 'filter': 'status:200'})
        try:
            matches = [json.loads(line) for line in fetch(query, 65536).splitlines()]
            for row in matches[:2]:
                length, offset = int(row['length']), int(row['offset'])
                if length > 512 * 1024:
                    continue
                byte_range = f'{offset}-{offset + length - 1}'
                url = 'https://data.commoncrawl.org/' + row['filename']
                data = fetch(url, length, {'Range': 'bytes=' + byte_range}, byte_range)
                if len(data) != length:
                    raise ValueError('Range response length differs from index')
                label = f'commoncrawl:{index}:{target}:{row["timestamp"]}'
                sources.append((label, data, {'index': row, 'source_url': url}))
        except (OSError, ValueError) as exc:
            errors.append({'query': query, 'error': str(exc)})
    return sources


def common_crawl_prefix(index):
    """Use the official manifest when the URL index is unavailable; cap transfer at 1 MiB."""
    manifest = f'https://data.commoncrawl.org/crawl-data/{index}/warc.paths.gz'
    with gzip.GzipFile(fileobj=io.BytesIO(fetch(manifest))) as decoded:
        name = decoded.readline(2048).decode().strip()
    url = 'https://data.commoncrawl.org/' + name
    data = fetch(url, 1048576, {'Range': 'bytes=0-1048575'}, '0-1048575')
    parts, decoded_size = [], 0
    pending = data
    while pending and len(parts) < 24:
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(pending, MAX_DECODED - decoded_size + 1)
        if len(raw) + decoded_size > MAX_DECODED:
            raise ValueError('Prefix exceeds decoded research cap')
        if not decoder.eof:
            break  # The HTTP range can end part-way through the last record.
        length = len(pending) - len(decoder.unused_data)
        parts.append(pending[:length])
        decoded_size += len(raw)
        pending = decoder.unused_data
    if not parts:
        raise ValueError('No complete gzip members in the range')
    selected = b''.join(parts)
    return [(f'commoncrawl:{index}:first-24-members', selected,
             {'manifest_url': manifest, 'source_url': url, 'fetched_range': '0-1048575',
              'fetched_bytes': len(data), 'used_bytes': len(selected),
              'selected_members': len(parts), 'selection': 'contiguous prefix, not random'})]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='*')
    parser.add_argument('--worker')
    parser.add_argument('--download-warcio', action='store_true')
    parser.add_argument('--cc-index')
    parser.add_argument('--cc-prefix')
    parser.add_argument('--output', default='warc-benchmark.json')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.inputs[0])
        return
    errors, sources = [], []
    for name in args.inputs:
        path = Path(name)
        if path.stat().st_size > MAX_INPUT:
            raise ValueError('Local input exceeds 8 MiB research cap')
        sources.append((str(path), path.read_bytes(), {'source': 'local'}))
    if args.download_warcio:
        for name in WARCIOS:
            url = 'https://raw.githubusercontent.com/webrecorder/warcio/master/test/data/' + name
            sources.append(('warcio:' + name, fetch(url), {'source_url': url}))
    if args.cc_index:
        sources.extend(common_crawl_sources(args.cc_index, errors))
    if args.cc_prefix:
        sources.extend(common_crawl_prefix(args.cc_prefix))
    result = {'python': platform.python_version(), 'platform': platform.platform(),
              'zlib': zlib.ZLIB_RUNTIME_VERSION, 'libdeflate': ctypes.util.find_library('deflate'),
              'timing_note': 'zstd includes process startup; other encoders exclude worker startup',
              'buffered_record_cap': MAX_SLOW_RECORD, 'errors': errors, 'samples': []}
    with tempfile.TemporaryDirectory(prefix='warc-compression-research-') as scratch:
        for label, data, provenance in sources:
            print('Measuring ' + label, flush=True)
            sample = measure_sample(label, data, Path(scratch))
            sample['provenance'] = provenance
            result['samples'].append(sample)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print('Saved ' + args.output)


if __name__ == '__main__':
    main()
