"""Measure PPT OLE record recompression on one pinned fixture, without publication.

This is a feasibility experiment, not a general PPT relocator or runtime packer.
Only the exact ole2-embedding-2003.ppt layout and its encoding-only variants pass.
The test allocator stages candidates; the qualified native writer compacts them.
"""

import argparse
import hashlib
import io
import json
import platform
import shutil
import struct
import subprocess
import tempfile
import time
import zlib
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from filerepack.ole import _profile
from filerepack.ole_ppt import project_bytes, read_records
from filerepack.ole_verify import CompoundFile, independent_manifest, read_compound
from test.ole_fixtures import CORPUS, compound_bytes

from dev.ole.qualify import render

FIXTURE = 'ole2-embedding-2003.ppt'
FIXTURE_SHA256 = '6a66797577e941c4f32ca5340217445e404cc0701cc8a07dd3625ef256253afd'
DOCUMENT = ('PowerPoint Document',)
CURRENT = ('Current User',)


def require(condition, reason):
    if not condition:
        raise ValueError('Pinned PPT pilot: ' + reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class PinnedFixture:
    def __init__(self):
        self.path = CORPUS / FIXTURE
        raw = self.path.read_bytes()
        require(digest(raw) == FIXTURE_SHA256, 'fixture checksum mismatch')
        self.original = CompoundFile(raw)
        require(_profile(self.original, 'ppt') == ('ppt', False), 'unexpected host profile')
        independent_manifest(io.BytesIO(raw), self.original)
        data = self.original.streams[DOCUMENT]
        records = read_records(data)
        self.raw_objects = [project_bytes(data, offset, records[offset])
                            for offset in (4568, 7195)]
        for payload, extension in zip(self.raw_objects, ('doc', 'xls')):
            nested = CompoundFile(payload)
            require(_profile(nested, extension) == (extension, False),
                    'unexpected nested profile/protection')
            independent_manifest(io.BytesIO(payload), nested)
        self.prefix = data[:4568]
        self.edit = data[9829:]
        self.current = self.original.streams[CURRENT]
        self.layout(self.original.streams)

    def layout(self, streams):
        """Verify every surrounding byte and all five fixture persist targets."""
        reference = self.original.streams
        require(set(streams) == set(reference), 'stream presence differs')
        require(all(streams[path] == reference[path] for path in streams
                    if path not in (DOCUMENT, CURRENT)), 'unrelated stream differs')
        data = streams[DOCUMENT]
        records = read_records(data)
        top = sorted(pos for pos, record in records.items() if record.parent is None)
        require([(records[p].kind, records[p].flags) for p in top] ==
                [(1000, 15), (1016, 15), (1006, 15), (4113, 16), (4113, 16),
                 (6002, 0), (4085, 0)], 'unexpected record layout/history')
        require(top[:4] == [0, 1426, 3902, 4568] and data[:4568] == self.prefix,
                'document/master/slide records differ')
        first, second, directory, edit = top[3:]
        require(second == first + 8 + records[first].size
                and directory == second + 8 + records[second].size
                and edit == directory + 32 and len(data) == edit + 36,
                'unexpected storage/index/edit boundaries')
        index = struct.pack('<HHI6I', 0, 6002, 24, 0x500001, 0, first, second, 1426, 3902)
        require(data[directory:edit] == index, 'persist target/identifier differs')
        expected_edit = bytearray(self.edit)
        struct.pack_into('<I', expected_edit, 20, directory)
        require(data[edit:] == expected_edit, 'user edit differs beyond directory offset')
        current = bytearray(self.current)
        struct.pack_into('<I', current, 16, edit)
        require(streams[CURRENT] == current, 'Current User differs beyond edit offset')
        for offset, raw in zip((first, second), self.raw_objects):
            require(project_bytes(data, offset, records[offset]) == raw,
                    'decoded embedded storage differs')
        return {'objects': [first, second], 'persist_directory': directory, 'user_edit': edit,
                'persist_targets': [0, first, second, 1426, 3902]}

    def encode(self, streams, encoded):
        self.layout(streams)
        require(len(encoded) == 2, 'expected two objects')
        data = bytearray(self.prefix)
        positions = []
        for raw, payload in zip(self.raw_objects, encoded):
            positions.append(len(data))
            data.extend(struct.pack('<HHII', 16, 4113, len(payload) + 4, len(raw)))
            data.extend(payload)
        directory = len(data)
        data.extend(struct.pack('<HHI6I', 0, 6002, 24, 0x500001, 0, *positions, 1426, 3902))
        edit = len(data)
        user_edit = bytearray(self.edit)
        struct.pack_into('<I', user_edit, 20, directory)
        data.extend(user_edit)
        current = bytearray(self.current)
        struct.pack_into('<I', current, 16, edit)
        result = dict(streams)
        result[DOCUMENT], result[CURRENT] = bytes(data), bytes(current)
        self.layout(result)
        return result

    def container(self, streams, *, root_override=None):
        metadata = {e.path: (e.clsid, e.state, e.created, e.modified)
                    for e in self.original.entries if e.kind != 5}
        root = next(e for e in self.original.entries if e.kind == 5)
        return compound_bytes(streams, storages=metadata, root=root_override or
                              (root.clsid, root.state, root.created, root.modified))

    def verify(self, source, candidate):
        """Independent CFB comparison plus fixture-specific encoding/offset equality."""
        before = self.layout(source.streams)
        after = self.layout(candidate.streams)
        require(_profile(candidate, 'ppt') == ('ppt', False), 'candidate profile differs')
        for compound in (source, candidate):
            independent_manifest(io.BytesIO(compound.data), compound)

        def normalized(compound):
            return tuple(replace(e, size=0, sha256='') if e.path in (DOCUMENT, CURRENT) else e
                         for e in compound.manifest.entries)

        require(normalized(source) == normalized(candidate), 'directory metadata differs')
        return {'intent_equal': True, 'surrounding_records_byte_equal': True,
                'unrelated_streams_and_directory_metadata_equal': True,
                'strict_ole_manifest_equal': source.manifest == candidate.manifest,
                'before': before, 'after': after,
                'decoded_storage_sha256': [digest(raw) for raw in self.raw_objects]}


def compact(writer, source, output):
    output.touch()
    started = time.perf_counter()
    subprocess.run([writer, str(source), str(output)], check=True, capture_output=True, timeout=120)
    elapsed = time.perf_counter() - started
    original, candidate = read_compound(str(source)), read_compound(str(output))
    independent_manifest(str(output), candidate)
    require(original.manifest == candidate.manifest, 'native compaction manifest differs')
    return candidate, round(elapsed, 6)


def encodings(raw_objects, compressor):
    payloads, records = [], []
    for raw in raw_objects:
        started = time.perf_counter()
        payload = compressor(raw)
        payloads.append(payload)
        records.append({'decoded_bytes': len(raw), 'encoded_bytes': len(payload),
                        'seconds': round(time.perf_counter() - started, 6)})
    return payloads, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--writer', required=True)
    parser.add_argument('--soffice')
    parser.add_argument('--pdftoppm')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if bool(args.soffice) != bool(args.pdftoppm):
        parser.error('--soffice and --pdftoppm must be supplied together')
    from zopfli.zlib import compress

    fixture = PinnedFixture()
    provenance = json.loads((CORPUS / 'provenance.json').read_text())
    report = {'status': 'development-only feasibility; production integration awaits approval',
              'fixture': FIXTURE, 'fixture_sha256': FIXTURE_SHA256,
              'corpus_commit': provenance['commit'], 'platform': platform.platform(),
              'python': platform.python_version(), 'zlib': zlib.ZLIB_RUNTIME_VERSION,
              'zopfli': version('zopfli'), 'olefile': version('olefile'),
              'writer': subprocess.check_output([args.writer, '--version'], text=True).strip(),
              'scope': 'one pinned, macro-free, single-edit fixture; two embedded DOC/XLS objects',
              'peak_memory': 'not measured', 'cases': []}
    if args.soffice:
        report['renderer'] = subprocess.check_output([args.soffice, '--version'], text=True).strip()
        report['rasterizer'] = subprocess.run([args.pdftoppm, '-v'], text=True,
                                            capture_output=True).stderr.strip().splitlines()[0]
    algorithms = {'zlib9': lambda raw: zlib.compress(raw, 9),
                  'zopfli15': lambda raw: compress(raw, numiterations=15)}
    with tempfile.TemporaryDirectory(prefix='filerepack-ppt-record-pilot-') as scratch:
        base = Path(scratch)
        for variant in ('original', 'controlled-zlib1', 'controlled-zlib0'):
            directory = base / variant
            directory.mkdir()
            source = directory / FIXTURE
            if variant == 'original':
                shutil.copyfile(fixture.path, source)
            else:
                level = int(variant[-1])
                blobs = [zlib.compress(raw, level) for raw in fixture.raw_objects]
                streams = fixture.encode(fixture.original.streams, blobs)
                source.write_bytes(fixture.container(streams))
            original = read_compound(str(source))
            baseline_path = directory / 'compacted.ppt'
            baseline, baseline_seconds = compact(args.writer, source, baseline_path)
            fixture.verify(original, baseline)
            original_pages = None
            if args.soffice:
                before = directory / 'before'
                before.mkdir()
                shutil.copyfile(source, before / FIXTURE)
                original_pages = render(before / FIXTURE, before, args.soffice, args.pdftoppm)
            for name, compressor in algorithms.items():
                blobs, encoding = encodings(fixture.raw_objects, compressor)
                streams = fixture.encode(original.streams, blobs)
                staged = directory / (name + '-staged.ppt')
                staged.write_bytes(fixture.container(streams))
                output = directory / (name + '.ppt')
                candidate, writer_seconds = compact(args.writer, staged, output)
                preservation = fixture.verify(original, candidate)
                case = {'variant': variant, 'encoder': name, 'source_bytes': len(original.data),
                        'compaction_bytes': len(baseline.data),
                        'candidate_bytes': len(candidate.data),
                        'additional_savings_bytes': len(baseline.data) - len(candidate.data),
                        'total_savings_bytes': len(original.data) - len(candidate.data),
                        'document_stream_savings_bytes': len(original.streams[DOCUMENT]) -
                        len(candidate.streams[DOCUMENT]), 'encoding': encoding,
                        'baseline_writer_seconds': baseline_seconds,
                        'writer_seconds': writer_seconds,
                        'source_sha256': digest(original.data),
                        'candidate_sha256': digest(candidate.data),
                        'preservation': preservation}
                if args.soffice:
                    after = directory / name
                    after.mkdir()
                    shutil.copyfile(output, after / FIXTURE)
                    pages = render(after / FIXTURE, after, args.soffice, args.pdftoppm)
                    require(pages == original_pages, 'rendered pages differ')
                    case['render'] = {'equal': True, 'pages': pages,
                                      'macro_security_level': 3, 'dpi': 96}
                report['cases'].append(case)
                print(variant, name, case['additional_savings_bytes'],
                      'additional bytes', flush=True)
    report['original_fixture_unchanged'] = digest(fixture.path.read_bytes()) == FIXTURE_SHA256
    require(report['original_fixture_unchanged'], 'original fixture changed')
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
