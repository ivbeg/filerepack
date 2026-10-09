"""Independent encoding-only controls for pinned real OfficeArt fixtures.

Only test constructors use these fixed offsets. Production discovers references
through host records and never imports this module.
"""

import struct
import zlib

from filerepack.ole_verify import CompoundFile, read_compound
from test.ole_fixtures import CORPUS, compound_bytes

NAMES = ('vector_image.doc', 'word_with_embeded.doc', 'SimpleWithImages.xls',
         'ole2-embedding-2003.ppt')
WORD, DATA, BOOK = ('WordDocument',), ('Data',), ('Workbook',)
DOCUMENT, PICTURES = ('PowerPoint Document',), ('Pictures',)


def envelope(flags, kind, body):
    return struct.pack('<HHI', flags, kind, len(body)) + body


def transcode(data, level):
    """Rewrap exact metafile bytes; repair enclosing record/FBSE lengths."""
    result, position = bytearray(), 0
    while position < len(data):
        flags, kind, size = struct.unpack_from('<HHI', data, position)
        body = data[position + 8:position + 8 + size]
        assert len(body) == size
        if kind in (0xF01A, 0xF01B):
            uid_size = 16 * (1 + (flags >> 4 in (0x3D5, 0x217)))
            prefix = bytearray(body[:uid_size + 34])
            payload = zlib.compress(zlib.decompress(body[uid_size + 34:]), level)
            struct.pack_into('<I', prefix, uid_size + 28, len(payload))
            body = bytes(prefix) + payload
        elif flags & 15 == 15:
            body = transcode(body, level)
        elif kind == 0xF007 and len(body) > 36 + body[33]:
            prefix = bytearray(body[:36 + body[33]])
            child = transcode(body[len(prefix):], level)
            struct.pack_into('<I', prefix, 20, len(child))
            body = bytes(prefix) + child
        result.extend(envelope(flags, kind, body))
        position += 8 + size
    assert position == len(data)
    return bytes(result)


def container(original, streams, **kwargs):
    metadata = {e.path: (e.clsid, e.state, e.created, e.modified)
                for e in original.entries if e.kind != 5}
    root = next(e for e in original.entries if e.kind == 5)
    return compound_bytes(streams, storages=metadata,
                          root=(root.clsid, root.state, root.created, root.modified), **kwargs)


def control(name, level=0):
    original = read_compound(str(CORPUS / name))
    streams = dict(original.streams)
    if name.endswith('.doc'):
        old, result, mapping, position = streams[DATA], bytearray(), {}, 0
        fields = (3057,) if name == 'vector_image.doc' else (3043, 2983, 2945, 2907)
        for _ in fields:
            size = struct.unpack_from('<I', old, position)[0]
            prefix = bytearray(old[position:position + 68])
            body = transcode(old[position + 68:position + size], level)
            mapping[position] = len(result)
            struct.pack_into('<I', prefix, 0, 68 + len(body))
            result.extend(prefix + body)
            position += size
        assert not any(old[position:])
        result.extend(old[position:])
        word = bytearray(streams[WORD])
        for field in fields:
            target = struct.unpack_from('<I', word, field)[0]
            struct.pack_into('<I', word, field, mapping[target])
        streams.update({WORD: bytes(word), DATA: bytes(result)})
    elif name.endswith('.xls'):
        old = streams[BOOK]
        position, group = 1408, bytearray()
        while position < 36519:
            kind, size = struct.unpack_from('<HH', old, position)
            assert kind == (0xEB if position == 1408 else 0x3C)
            group.extend(old[position + 4:position + 4 + size])
            position += 4 + size
        assert position == 36519
        group = transcode(bytes(group), level)
        parts = [group[i:i + 8224] for i in range(0, len(group), 8224)]
        wrapped = b''.join(struct.pack('<HH', 0xEB if i == 0 else 0x3C, len(p)) + p
                           for i, p in enumerate(parts))
        delta = len(wrapped) - (36519 - 1408)
        changed = bytearray(old)
        for field in (1338, 1356, 1374, 36602, 37525, 37788):
            target = struct.unpack_from('<I', changed, field)[0]
            struct.pack_into('<I', changed, field, target + delta)
        streams[BOOK] = bytes(changed[:1408]) + wrapped + bytes(changed[36519:])
    else:
        old, blobs, position = streams[PICTURES], [], 0
        while position < len(old):
            size = struct.unpack_from('<I', old, position + 4)[0]
            blobs.append(transcode(old[position:position + 8 + size], level))
            position += 8 + size
        assert len(blobs) == 2
        document = bytearray(streams[DOCUMENT])
        for size_field, delay_field, size, target in (
                (856, 864, len(blobs[0]), 0), (900, 908, len(blobs[1]), len(blobs[0]))):
            struct.pack_into('<I', document, size_field, size)
            struct.pack_into('<I', document, delay_field, target)
        streams.update({DOCUMENT: bytes(document), PICTURES: b''.join(blobs)})
    return CompoundFile(container(original, streams))
