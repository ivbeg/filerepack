"""Small CFB allocator for preservation/corruption tests, independent of writers."""

import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from filerepack.ole_verify import DIFAT, END, FAT, FREE, MAGIC, Path as OlePath

CORPUS = Path(__file__).parent / 'fixtures' / 'ole'
ADDITIONAL_ART_ORIGINALS = (
    '28774.xls',
    '29675.xls',
    'two_images.doc',
    '58804_1.doc',
    'msobrightnesscontrast.doc',
    'tdf104596_wrapInHeaderTable.doc',
    'tdf132094_transparentPageImage.doc',
    'tdf162541_notLayoutInCell_paraLeft.doc',
    'tdf162542_notLayoutInCell_charLeft_wrapThrough.doc',
    'tdf79553_lineNumbers.doc',
    'file-with-png-image.xls',
    'nissl-lab-TestSectionDictionary.doc',
    'nissl-lab-multimedia.doc',
    'testControlCharacters.doc',
    '0018-doc.doc',
    '0029-doc.doc',
    '0066-doc.doc',
    '0113-doc.doc',
    '0670-doc.doc',
    '0771-doc.doc',
    '1825-doc.doc',
    '4128-doc.doc',
    'fdo66692-2.doc',
    'tdf131707_flyWrap.doc',
)
SAMPLES = {'doc': 'simple.doc', 'xls': 'SampleSS.xls', 'ppt': 'SampleShow.ppt'}
Metadata = Tuple[bytes, int, int, int]


def ppt_embedded_streams(encoded: List[bytes],
                         decoded_sizes: Optional[List[int]] = None) -> Dict[OlePath, bytes]:
    """Independent constructor for encoding-only variants of the pinned two-object PPT."""
    from filerepack.ole_verify import read_compound
    source = read_compound(str(CORPUS / 'ole2-embedding-2003.ppt')).streams
    data = source[('PowerPoint Document',)]
    assert len(encoded) == 2 and len(data) == 9865
    assert struct.unpack_from('<HHI', data, 4568) == (16, 4113, 2619)
    assert struct.unpack_from('<HHI', data, 7195) == (16, 4113, 2594)
    result = bytearray(data[:4568])
    offsets = []
    for i, (payload, original) in enumerate(zip(encoded, (4568, 7195))):
        offsets.append(len(result))
        decoded = (decoded_sizes[i] if decoded_sizes is not None else
                   struct.unpack_from('<I', data, original + 8)[0])
        result.extend(struct.pack('<HHII', 16, 4113, len(payload) + 4, decoded) + payload)
    directory = len(result)
    result.extend(struct.pack('<HHI6I', 0, 6002, 24, 0x500001, 0, *offsets, 1426, 3902))
    edit = len(result)
    tail = bytearray(data[9829:])
    struct.pack_into('<I', tail, 20, directory)
    result.extend(tail)
    current = bytearray(source[('Current User',)])
    struct.pack_into('<I', current, 16, edit)
    return {**source, ('PowerPoint Document',): bytes(result), ('Current User',): bytes(current)}


def compound_bytes(streams: Dict[OlePath, bytes], *,
                   storages: Optional[Dict[OlePath, Metadata]] = None,
                   root: Metadata = (b'\0' * 16, 0, 0, 0),
                   free_sectors: int = 0, mini_gaps: int = 0) -> bytes:
    """Build version 3 containers, optionally with holes and extended DIFAT."""
    metadata = dict(storages or {})
    for path in list(streams) + list(metadata):
        for depth in range(1, len(path)):
            metadata.setdefault(path[:depth], (b'\0' * 16, 0, 0, 0))
    paths = [()] + sorted(set(streams) | set(metadata))
    indexes = {path: index for index, path in enumerate(paths)}
    blocks: List[bytes] = []
    links: List[int] = []

    def allocate(data: bytes) -> int:
        count = (len(data) + 511) // 512
        start = len(blocks)
        for offset in range(count):
            blocks.append(data[offset * 512:(offset + 1) * 512].ljust(512, b'\0'))
            links.append(start + offset + 1 if offset + 1 < count else END)
        return start if count else END

    directory_count = (len(paths) + 3) // 4
    directory = allocate(b'\0' * (directory_count * 512))
    mini_data = bytearray()
    mini_links: List[int] = []
    starts = {}
    for path, data in streams.items():
        if len(data) >= 4096:
            starts[path] = allocate(data)
            continue
        count = (len(data) + 63) // 64
        start = len(mini_links)
        starts[path] = start if count else END
        for offset in range(count):
            mini_data.extend(data[offset * 64:(offset + 1) * 64].ljust(64, b'\0'))
            mini_links.append(start + offset + 1 if offset + 1 < count else END)
        if count:
            mini_data.extend(b'\0' * (mini_gaps * 64))
            mini_links.extend([FREE] * mini_gaps)
    mini_start = allocate(bytes(mini_data))
    mini_count = (len(mini_links) + 127) // 128
    mini_links.extend([FREE] * (mini_count * 128 - len(mini_links)))
    minifat_start = allocate(struct.pack('<' + 'I' * len(mini_links), *mini_links))
    blocks.extend([b'\0' * 512] * free_sectors)
    links.extend([FREE] * free_sectors)

    raw = bytearray(directory_count * 512)
    for path in paths:
        index = indexes[path]
        name = (path[-1] if path else 'Root Entry').encode('utf-16le') + b'\0\0'
        assert len(name) <= 64
        offset = index * 128
        raw[offset:offset + len(name)] = name
        kind = 5 if not path else 2 if path in streams else 1
        struct.pack_into('<HBBIII', raw, offset + 64, len(name), kind, 1, FREE, FREE, FREE)
        clsid, state, created, modified = root if not path else metadata.get(
            path, (b'\0' * 16, 0, 0, 0))
        raw[offset + 80:offset + 96] = clsid
        start = mini_start if not path else starts.get(path, 0)
        size = len(mini_data) if not path else len(streams.get(path, b''))
        struct.pack_into('<IQQIQ', raw, offset + 96, state, created, modified, start, size)

    def name_key(path: OlePath) -> Tuple[int, bytes]:
        name = path[-1]
        # Explicit exceptional mappings for our Unicode fixtures, independently
        # of the production table. Other full-uppercase expansions stay unchanged.
        exceptions = {'ᾀ': 'ᾈ', 'ᾳ': 'ᾼ'}
        upper = ''.join(exceptions.get(c, c.upper() if len(c.upper()) == 1 else c) for c in name)
        return len(name.encode('utf-16le')), upper.encode('utf-16be')

    def tree(children: List[OlePath]) -> int:
        if not children:
            return FREE
        center = len(children) // 2
        index = indexes[children[center]]
        struct.pack_into('<II', raw, index * 128 + 68,
                         tree(children[:center]), tree(children[center + 1:]))
        return index

    for parent in [()] + list(metadata):
        children = sorted([p for p in paths[1:] if p[:-1] == parent], key=name_key)
        struct.pack_into('<I', raw, indexes[parent] * 128 + 76, tree(children))
    for offset in range(directory_count):
        blocks[directory + offset] = bytes(raw[offset * 512:(offset + 1) * 512])

    return _finish_blocks(blocks, links, directory, minifat_start, mini_count)


def _finish_blocks(blocks: List[bytes], links: List[int], directory: int,
                   minifat_start: int, mini_count: int) -> bytes:
    base, fat_count, difat_count = len(blocks), 1, 0
    while True:
        new_fat = (base + fat_count + difat_count + 127) // 128
        new_difat = (max(new_fat - 109, 0) + 126) // 127
        if (new_fat, new_difat) == (fat_count, difat_count):
            break
        fat_count, difat_count = new_fat, new_difat
    fat_ids = list(range(base, base + fat_count))
    difat_ids = list(range(base + fat_count, base + fat_count + difat_count))
    links.extend([FAT] * fat_count + [DIFAT] * difat_count)
    links.extend([FREE] * (fat_count * 128 - len(links)))
    for offset in range(fat_count):
        blocks.append(struct.pack('<128I', *links[offset * 128:(offset + 1) * 128]))
    extra = fat_ids[109:]
    for offset in range(difat_count):
        chunk = extra[offset * 127:(offset + 1) * 127]
        chunk += [FREE] * (127 - len(chunk))
        chunk.append(difat_ids[offset + 1] if offset + 1 < difat_count else END)
        blocks.append(struct.pack('<128I', *chunk))
    header = bytearray(512)
    header[:8] = MAGIC
    struct.pack_into('<5H', header, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into('<9I', header, 40, 0, fat_count, directory, 0, 4096,
                     minifat_start, mini_count, difat_ids[0] if difat_ids else END, difat_count)
    struct.pack_into('<109I', header, 76, *(fat_ids[:109] + [FREE] * max(109 - fat_count, 0)))
    return bytes(header) + b''.join(blocks)


def ppt_project_streams(streams: Dict[OlePath, bytes], payload: bytes,
                        flags: int = 0x10) -> Dict[OlePath, bytes]:
    """Replace only SimpleMacro.ppt's final storage wrapper for controlled fixtures.

This is a fixture-specific relocation, never a production PPT rewrite path.
All four persist objects precede the final directory; only the following
directory/edit offsets move. Assertions pin that arrangement independently.
"""
    streams = dict(streams)
    data = streams[('PowerPoint Document',)]
    current = bytearray(streams[('Current User',)])
    edit = struct.unpack_from('<I', current, 16)[0]
    previous, directory = struct.unpack_from('<II', data, edit + 16)
    assert previous == 0 and struct.unpack_from('<HHI', data, directory) == (0, 6002, 20)
    assert struct.unpack_from('<I', data, directory + 8)[0] == (4 << 20) | 1
    targets = struct.unpack_from('<4I', data, directory + 12)
    start = targets[2]
    old_flags, kind, size = struct.unpack_from('<HHI', data, start)
    assert old_flags == 0x10 and kind == 4113 and start + 8 + size == directory
    assert all(target <= start for target in targets) and edit + 36 == len(data)
    replacement = struct.pack('<HHI', flags, 4113, len(payload)) + payload
    delta = len(replacement) - 8 - size
    rebuilt = bytearray(data[:start] + replacement + data[directory:])
    struct.pack_into('<I', rebuilt, edit + delta + 20, directory + delta)
    struct.pack_into('<I', current, 16, edit + delta)
    streams[('PowerPoint Document',)] = bytes(rebuilt)
    streams[('Current User',)] = bytes(current)
    return streams
