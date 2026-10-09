"""Checksum-bound OfficeArt feasibility experiment; no runtime/publication hooks.

The common record codec is exercised by three distinct pinned host adapters.
Host offsets are audited for these exact fixtures, not discovered by byte carving.
General host discovery and production writers remain in the proposed change.
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

from filerepack.format_support import Budget, FormatLimits, inflate
from filerepack.ole import _profile
from filerepack.ole_ppt import read_records
from filerepack.ole_verify import CompoundFile, independent_manifest, read_compound
from test.ole_fixtures import CORPUS, compound_bytes

from dev.ole.qualify import render

FIXTURES = {
    'vector_image.doc': '747eb4c44a9ff7ac646f267fad6d4006b596a8beaec211fe27cb67f018800850',
    'word_with_embeded.doc': '206acf1f7eb7b7d7d2075e04015d005ae9bb56f025560f2583ad3878257bc4c7',
    'SimpleWithImages.xls': 'dd35970bf68df7bb609b681634602ead30001816009c791012d00b5563ab9314',
    'ole2-embedding-2003.ppt': '6a66797577e941c4f32ca5340217445e404cc0701cc8a07dd3625ef256253afd',
}
DATA, WORD = ('Data',), ('WordDocument',)
WORKBOOK, PICTURES = ('Workbook',), ('Pictures',)
DOCUMENT = ('PowerPoint Document',)
METAFILES = {0xF01A: (0x3D4, 0x3D5), 0xF01B: (0x216, 0x217)}
CONTAINERS = {0xF000, 0xF001, 0xF004}
MAX_PAYLOAD = 16 * 1024 * 1024


def require(condition, reason):
    if not condition:
        raise ValueError('Pinned OfficeArt pilot: ' + reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    require(len(data) >= 8, 'truncated record header')
    flags, kind, size = struct.unpack_from('<HHI', data)
    require(size == len(data) - 8, 'record length differs')
    return flags, kind, data[8:]


def record_bytes(flags, kind, body):
    return struct.pack('<HHI', flags, kind, len(body)) + body


def parts(data):
    offset = 0
    while offset < len(data):
        require(offset + 8 <= len(data), 'truncated sequence header')
        size = struct.unpack_from('<I', data, offset + 4)[0]
        end = offset + 8 + size
        require(end <= len(data), 'truncated sequence body')
        yield offset, data[offset:end]
        offset = end


class Codec:
    """Shared MS-ODRAW codec, independent of DOC/XLS/PPT relocation."""

    def __init__(self, compressor=None, allow_growth=False):
        self.compressor = compressor
        self.allow_growth = allow_growth
        self.budget = Budget(FormatLimits())
        self.payloads = []
        self.decoded = 0

    def metafile(self, flags, kind, body):
        instances = METAFILES[kind]
        require(flags & 15 == 0 and flags >> 4 in instances, 'metafile version/instance')
        uids = 16 * (1 + (flags >> 4 == instances[1]))
        require(len(body) >= uids + 34, 'truncated metafile header')
        header = bytearray(body[uids:uids + 34])
        decoded = struct.unpack_from('<I', header)[0]
        saved = struct.unpack_from('<I', header, 28)[0]
        require(0 < decoded <= MAX_PAYLOAD and 0 < saved <= MAX_PAYLOAD,
                'metafile size limit')
        require(header[32:] == b'\x00\xfe', 'unqualified compression/filter')
        encoded = body[uids + 34:]
        require(len(encoded) == saved, 'cbSave differs from record length')
        require(len(self.payloads) < 64 and self.decoded + decoded <= 64 * 1024 * 1024,
                'metafile count/aggregate size limit')
        raw = inflate(encoded, self.budget, maximum=decoded)
        require(len(raw) == decoded, 'decoded cbSize differs')
        self.decoded += decoded
        output = encoded
        if self.compressor:
            self.budget.check()
            trial = self.compressor(raw)
            require(len(trial) <= MAX_PAYLOAD, 'encoder output size limit')
            require(inflate(trial, self.budget, maximum=decoded) == raw,
                    'encoder changed decoded metafile')
            self.budget.check()
            # Controlled level-0/1 variants are deliberately allowed to grow.
            if self.allow_growth or len(trial) < len(encoded):
                output = trial
        self.payloads.append({'type': 'EMF' if kind == 0xF01A else 'WMF',
                              'decoded_bytes': decoded, 'encoded_bytes': len(encoded),
                              'output_encoded_bytes': len(output), 'decoded_sha256': digest(raw),
                              'uid_bytes': body[:uids].hex(),
                              'geometry_sha256': digest(header[4:28])})
        struct.pack_into('<I', header, 28, len(output))
        rebuilt = body[:uids] + bytes(header) + output
        struct.pack_into('<I', header, 28, 0)
        fingerprint = (flags, kind, body[:uids], bytes(header), digest(raw))
        return record_bytes(flags, kind, rebuilt), fingerprint

    def fbse(self, flags, body, depth):
        require(flags & 15 == 2 and len(body) >= 36, 'FBSE version/size')
        name_size = body[33]
        require(name_size % 2 == 0 and name_size <= 254
                and 36 + name_size <= len(body), 'FBSE name length')
        prefix, embedded = body[:36 + name_size], body[36 + name_size:]
        if not embedded:
            return record_bytes(flags, 0xF007, body), (flags, 0xF007, body)
        size = struct.unpack_from('<I', body, 20)[0]
        require(size == len(embedded), 'embedded FBSE size differs')
        require(flags >> 4 in body[:2], 'FBSE type differs')
        rebuilt, fingerprint = self.one(embedded, depth + 1)
        prefix = bytearray(prefix)
        struct.pack_into('<I', prefix, 20, len(rebuilt))
        output = record_bytes(flags, 0xF007, bytes(prefix) + rebuilt)
        # foDelay is ignored for embedded BLIPs and remains byte-identical.
        struct.pack_into('<I', prefix, 20, 0)
        return output, (flags, 0xF007, bytes(prefix), fingerprint)

    def one(self, data, depth=0):
        require(depth <= 32, 'OfficeArt nesting limit')
        self.budget.consume(nodes=1)
        flags, kind, body = record(data)
        if kind in METAFILES:
            return self.metafile(flags, kind, body)
        if kind == 0xF007:
            return self.fbse(flags, body, depth)
        if flags & 15 == 15:
            require(kind in CONTAINERS, 'unknown OfficeArt container in pinned store')
            rebuilt, fingerprint = self.sequence(body, depth + 1)
            return record_bytes(flags, kind, rebuilt), (flags, kind, fingerprint)
        return data, (flags, kind, body)

    def sequence(self, data, depth=0):
        result, fingerprints = [], []
        for _, child in parts(data):
            rebuilt, fingerprint = self.one(child, depth)
            result.append(rebuilt)
            fingerprints.append(fingerprint)
        return b''.join(result), tuple(fingerprints)


def biff(data):
    offset = 0
    while offset < len(data):
        require(offset + 4 <= len(data), 'truncated BIFF header')
        kind, size = struct.unpack_from('<HH', data, offset)
        end = offset + 4 + size
        require(0 < kind and size <= 8224 and end <= len(data), 'BIFF bounds/type')
        yield offset, kind, data[offset + 4:end]
        offset = end


def drawing_group(data):
    records = list(biff(data))
    first = [i for i, (_, kind, _) in enumerate(records) if kind == 0xEB]
    require(len(first) == 1, 'expected one pinned MsoDrawingGroup')
    start = first[0]
    stop = start + 1
    while stop < len(records) and records[stop][1] == 0x3C:
        stop += 1
    offset = records[start][0]
    end = records[stop][0]
    group = b''.join(payload for _, _, payload in records[start:stop])
    require(struct.unpack_from('<HH', group) == (15, 0xF000), 'drawing group root')
    return offset, end, group, records


def xls_pointers(data, start, stop, new_stop):
    """Relocate exactly the audited pointer families present in the pinned XLS.

    Other files, populated ExtSST/DBCell arrays and unknown offset-bearing records
    are not qualified by this experiment's source checksum gate.
    """
    result = bytearray(data)
    normalized = bytearray(data)
    pointers = []
    records = {at: (kind, payload) for at, kind, payload in biff(data)}
    for at, (kind, payload) in records.items():
        if kind == 0x85:
            require(len(payload) >= 8, 'BoundSheet size')
            field, target_kind = at + 4, 0x809
        elif kind == 0x20B:
            require(len(payload) == 16, 'only empty Index DBCell arrays qualified')
            field, target_kind = at + 16, 0x55
        else:
            if kind == 0xFF:
                require(len(payload) == 2, 'only empty ExtSST pointers qualified')
            continue
        target = struct.unpack_from('<I', data, field)[0]
        require(target >= stop and target in records and records[target][0] == target_kind,
                'missing/stale BIFF pointer')
        relocated = target + new_stop - stop
        struct.pack_into('<I', result, field, relocated)
        # Normalize against the suffix start: retains target identity/position.
        struct.pack_into('<I', normalized, field, target - stop)
        pointers.append({'record': hex(kind), 'field': field, 'target': target,
                         'output_target': relocated, 'target_type': hex(target_kind)})
    require(len(pointers) == 6, 'pinned BoundSheet/Index reference count')
    return bytes(result), bytes(normalized[:start] + normalized[stop:]), pointers


class PinnedFixture:
    def __init__(self, name):
        self.path = CORPUS / name
        raw = self.path.read_bytes()
        require(digest(raw) == FIXTURES[name], 'fixture checksum mismatch')
        self.name = name
        self.host = self.path.suffix[1:]
        self.original = CompoundFile(raw)
        require(_profile(self.original, self.host) == (self.host, False), 'host/protection profile')
        independent_manifest(io.BytesIO(raw), self.original)
        self.changed = ({DATA, WORD} if self.host == 'doc' else
                        {WORKBOOK} if self.host == 'xls' else {PICTURES, DOCUMENT})
        self.reference = self.layout(self.original.streams)[1]

    def doc(self, streams, codec):
        data, word = streams[DATA], bytearray(streams[WORD])
        fields = ((3057, 0),) if self.name == 'vector_image.doc' else (
            (3043, 0), (2983, 1), (2945, 2), (2907, 3))
        count = len(fields)
        before, after, fingerprints = [], [], []
        offset = 0
        output = bytearray()
        for _ in range(count):
            require(offset + 68 <= len(data), 'truncated PICF')
            size, cb_header, mode = struct.unpack_from('<IHH', data, offset)
            require(cb_header == 68 and mode == 100 and 68 < size <= len(data) - offset,
                    'pinned PICF size/format')
            before.append(offset)
            after.append(len(output))
            header = bytearray(data[offset:offset + 68])
            encoded, fingerprint = codec.sequence(data[offset + 68:offset + size])
            struct.pack_into('<I', header, 0, 68 + len(encoded))
            output.extend(header + encoded)
            struct.pack_into('<I', header, 0, 0)
            fingerprints.append((bytes(header), fingerprint))
            offset += size
        padding = data[offset:]
        require(not any(padding), 'pinned Data padding differs')
        output.extend(padding)  # Retain every original logical padding byte.
        references = []
        normalized_word = bytearray(word)
        for field, index in fields:
            require(word[field - 2:field] == b'\x03\x6a'
                    and struct.unpack_from('<I', word, field)[0] == before[index],
                    'pinned picture CPicLocation differs')
            struct.pack_into('<I', word, field, after[index])
            struct.pack_into('<I', normalized_word, field, index)
            references.append({'field': field, 'target': before[index],
                               'output_target': after[index]})
        return {**streams, DATA: bytes(output), WORD: bytes(word)}, (
            tuple(fingerprints), padding, bytes(normalized_word)), references

    def xls(self, streams, codec):
        workbook = streams[WORKBOOK]
        start, stop, group, _ = drawing_group(workbook)
        require(start == 1408, 'pinned drawing group start')
        encoded, fingerprint = codec.one(group)
        fragments = [encoded[i:i + 8224] for i in range(0, len(encoded), 8224)]
        wrapped = b''.join(struct.pack('<HH', 0xEB if i == 0 else 0x3C, len(part)) + part
                           for i, part in enumerate(fragments))
        patched, normalized, pointers = xls_pointers(workbook, start, stop, start + len(wrapped))
        result = patched[:start] + wrapped + patched[stop:]
        return {**streams, WORKBOOK: result}, (normalized, fingerprint), pointers

    def ppt(self, streams, codec):
        pictures, document = streams[PICTURES], bytearray(streams[DOCUMENT])
        parsed = list(parts(pictures))
        require(len(parsed) == 2 and all(record(blob)[1] == 0xF01A for _, blob in parsed),
                'pinned PPT picture sequence')
        before = [at for at, _ in parsed]
        after, encoded, fingerprints, sizes = [], [], [], []
        output = 0
        for _, blob in parsed:
            rebuilt, fingerprint = codec.one(blob)
            after.append(output)
            output += len(rebuilt)
            encoded.append(rebuilt)
            fingerprints.append(fingerprint)
            sizes.append(len(blob))
        records = read_records(bytes(document))
        require([(pos, r.flags, r.size) for pos, r in records.items() if r.kind == 0xF007]
                == [(784, 2, 36), (828, 34, 36), (872, 34, 36)], 'pinned PPT BStore')
        normalized = bytearray(document)
        references = []
        for i, pos in enumerate((828, 872)):
            require(struct.unpack_from('<III', document, pos + 28) == (sizes[i], 1, before[i]),
                    'PPT BStore size/reference/delay differs')
            require(document[pos + 10:pos + 26] == parsed[i][1][8:24], 'PPT BStore UID differs')
            struct.pack_into('<I', document, pos + 28, len(encoded[i]))
            struct.pack_into('<I', document, pos + 36, after[i])
            struct.pack_into('<I', normalized, pos + 28, 0)
            struct.pack_into('<I', normalized, pos + 36, i)
            references.append({'field': pos + 36, 'target': before[i],
                               'output_target': after[i]})
        return {**streams, PICTURES: b''.join(encoded), DOCUMENT: bytes(document)}, (
            tuple(fingerprints), bytes(normalized)), references

    def layout(self, streams, compressor=None, allow_growth=False):
        reference = self.original.streams
        require(set(streams) == set(reference), 'stream presence differs')
        require(all(streams[p] == reference[p] for p in reference if p not in self.changed),
                'unrelated stream differs')
        codec = Codec(compressor, allow_growth)
        rebuilt, fingerprint, references = getattr(self, self.host)(streams, codec)
        require(bool(codec.payloads), 'no metafile payloads')
        return rebuilt, fingerprint, {'payloads': codec.payloads, 'references': references}

    def encode(self, streams, compressor, allow_growth=False):
        require(self.layout(streams)[1] == self.reference, 'source intent differs')
        rebuilt, fingerprint, info = self.layout(streams, compressor, allow_growth)
        require(fingerprint == self.reference and self.layout(rebuilt)[1] == self.reference,
                'encoded intent differs')
        return rebuilt, info

    def container(self, streams, root_override=None):
        metadata = {e.path: (e.clsid, e.state, e.created, e.modified)
                    for e in self.original.entries if e.kind != 5}
        root = next(e for e in self.original.entries if e.kind == 5)
        return compound_bytes(streams, storages=metadata, root=root_override or
                              (root.clsid, root.state, root.created, root.modified))

    def verify(self, source, candidate):
        for compound in (source, candidate):
            require(_profile(compound, self.host) == (self.host, False), 'candidate host differs')
            independent_manifest(io.BytesIO(compound.data), compound)
            require(self.layout(compound.streams)[1] == self.reference, 'intended content differs')

        def normalized(compound):
            return tuple(replace(e, size=0, sha256='') if e.path in self.changed else e
                         for e in compound.manifest.entries)

        require(normalized(source) == normalized(candidate), 'directory metadata differs')
        return {'intent_equal': True, 'decoded_metafile_bytes_equal': True,
                'uids_and_geometry_equal': True, 'host_references_equal': True,
                'unrelated_bytes_and_directory_metadata_equal': True,
                'strict_ole_manifest_equal': source.manifest == candidate.manifest}


def compact(writer, source, destination):
    destination.touch()
    started = time.perf_counter()
    subprocess.run([writer, str(source), str(destination)], check=True,
                   capture_output=True, timeout=120)
    original, candidate = read_compound(str(source)), read_compound(str(destination))
    independent_manifest(str(destination), candidate)
    require(original.manifest == candidate.manifest, 'native compaction manifest differs')
    return candidate, round(time.perf_counter() - started, 6)


def compressor(name):
    if name.startswith('zlib'):
        level = int(name[4:])
        return lambda raw: zlib.compress(raw, level)
    require(name == 'zopfli15' and version('zopfli') == '0.4.3', 'unqualified Zopfli version')
    from zopfli.zlib import compress

    def encode(raw):
        # Same qualification bound as the existing runtime PPT pass.
        return compress(raw, numiterations=15) if len(raw) <= 1024 * 1024 else zlib.compress(raw, 9)

    return encode


def selection(result):
    count = sum(p['output_encoded_bytes'] < p['encoded_bytes'] for p in result['payloads'])
    saving = result['additional_savings_bytes'] > 0
    result.update(changed_payloads=count,
                  selected_bytes=(result['candidate_bytes'] if saving
                                  else result['compaction_bytes']),
                  selected_verifier='officeart-intent' if saving else 'ole',
                  selection_reason=('smaller verified OfficeArt file' if saving else
                                    'payload savings do not improve physical compaction size'
                                    if count
                                    else 'no smaller compressed metafile wrappers'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--writer', required=True)
    parser.add_argument('--soffice')
    parser.add_argument('--pdftoppm')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if bool(args.soffice) != bool(args.pdftoppm):
        parser.error('--soffice and --pdftoppm must be supplied together')
    report = {'status': 'checksum-bound development pilot; runtime integration awaits approval',
              'platform': platform.platform(), 'python': platform.python_version(),
              'zlib': zlib.ZLIB_RUNTIME_VERSION, 'zopfli': version('zopfli'),
              'olefile': version('olefile'),
              'corpus_commit': json.loads((CORPUS / 'provenance.json').read_text())['commit'],
              'writer': subprocess.check_output([args.writer, '--version'], text=True).strip(),
              'peak_memory': 'not measured', 'cases': []}
    if args.soffice:
        report['renderer'] = subprocess.check_output([args.soffice, '--version'], text=True).strip()
        report['rasterizer'] = subprocess.run([args.pdftoppm, '-v'], text=True,
                                             capture_output=True).stderr.strip().splitlines()[0]
    with tempfile.TemporaryDirectory(prefix='filerepack-officeart-pilot-') as scratch:
        base = Path(scratch)
        for name in FIXTURES:
            fixture = PinnedFixture(name)
            for variant in ('original', 'controlled-zlib1', 'controlled-zlib0'):
                folder = base / (name + '-' + variant)
                folder.mkdir()
                source = folder / name
                if variant == 'original':
                    shutil.copyfile(fixture.path, source)
                else:
                    streams, _ = fixture.encode(fixture.original.streams, compressor(variant[11:]),
                                                allow_growth=True)
                    source.write_bytes(fixture.container(streams))
                original = read_compound(str(source))
                require(fixture.verify(fixture.original, original)['intent_equal'],
                        'control differs')
                baseline, duration = compact(args.writer, source,
                                             folder / ('baseline.' + fixture.host))
                reference_render = None
                if args.soffice:
                    reference_render = render(source, folder / 'render-source',
                                              args.soffice, args.pdftoppm)
                for algorithm in ('zlib9', 'zopfli15'):
                    started = time.perf_counter()
                    streams, info = fixture.encode(original.streams, compressor(algorithm))
                    staged = folder / ('staged-' + algorithm + '.' + fixture.host)
                    staged.write_bytes(fixture.container(streams))
                    output = folder / (algorithm + '.' + fixture.host)
                    candidate, writer_time = compact(args.writer, staged, output)
                    verified = fixture.verify(original, candidate)
                    result = {'fixture': name, 'fixture_sha256': FIXTURES[name], 'variant': variant,
                              'encoder': algorithm, 'source_bytes': len(original.data),
                              'compaction_bytes': len(baseline.data),
                              'candidate_bytes': len(candidate.data),
                              'additional_savings_bytes': len(baseline.data) - len(candidate.data),
                              'stream_savings_bytes': sum(len(original.streams[p]) - len(streams[p])
                                                         for p in fixture.changed),
                              'seconds': round(time.perf_counter() - started, 6),
                              'compaction_seconds': duration, 'writer_seconds': writer_time,
                              **verified, **info}
                    selection(result)
                    if reference_render is not None:
                        candidate_render = render(output, folder / ('render-' + algorithm),
                                                  args.soffice, args.pdftoppm)
                        result.update(render_equal=reference_render == candidate_render,
                                      source_pages=reference_render,
                                      candidate_pages=candidate_render)
                        require(result['render_equal'], 'renderer differs')
                    report['cases'].append(result)
            require(digest(fixture.path.read_bytes()) == FIXTURES[name], 'original fixture changed')
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'cases': len(report['cases']),
                      'intent_equal': sum(c['intent_equal'] for c in report['cases']),
                      'render_equal': sum(c.get('render_equal', False) for c in report['cases'])}))


if __name__ == '__main__':
    main()
