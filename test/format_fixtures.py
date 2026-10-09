"""Small native-format byte fixtures with visible metadata and decoded payloads."""

import bz2
import gzip
import sqlite3
import struct
import zlib


def blend_bytes(*, version=300, pointer=64, endian='<'):
    form = endian + ('4siQii' if pointer == 64 else '4siIii')
    header = b'BLENDER' + (b'-' if pointer == 64 else b'_')
    header += b'v' if endian == '<' else b'V'
    header += str(version).encode()
    dna = b'SDNA' + b'NAME' + struct.pack(endian + 'I', 0)
    dna += b'TYPE' + struct.pack(endian + 'I', 0) + b'TLENSTRC' + struct.pack(endian + 'I', 0)
    content = b'project payload and packed texture\0' * 4096
    return (header + struct.pack(form, b'DATA', len(content), 0x1000, 0, 1) + content +
            struct.pack(form, b'DNA1', len(dna), 0, 0, 1) + dna +
            struct.pack(form, b'ENDB', 0, 0, 0, 0))


def psb_bytes(*, layers=True, codec=2):
    raw = b'\x2a' * (128 * 128)
    channel = struct.pack('>H', codec) + zlib.compress(raw, 1)
    header = struct.pack('>4sH6sHIIHH', b'8BPS', 2, b'\0' * 6, 1, 128, 128, 8, 1)
    if layers:
        extra = struct.pack('>II', 0, 0) + b'\4Test' + b'\0' * 3
        record = struct.pack('>4iH', 0, 0, 128, 128, 1)
        record += struct.pack('>hQ', 0, len(channel))
        record += b'8BIMnorm' + bytes([255, 0, 0, 0])
        record += struct.pack('>I', len(extra)) + extra
        info = struct.pack('>h', 1) + record + channel
        info += b'\0' * (len(info) % 2)
        layer_data = struct.pack('>Q', len(info)) + info + struct.pack('>I', 0)
    else:
        layer_data = b''
    return (header + struct.pack('>IIQ', 0, 0, len(layer_data)) + layer_data + channel), raw


def _ase_chunk(kind, payload):
    return struct.pack('<IH', len(payload) + 6, kind) + payload


def _ase_frame(chunks, duration):
    body = b''.join(chunks)
    return struct.pack('<IHHHHI', len(body) + 16, 0xF1FA, len(chunks), duration, 0, 0) + body


def aseprite_bytes(*, tilemap=False, raw_cel=False):
    header = bytearray(128)
    struct.pack_into('<I5H', header, 0, 0, 0xA5E0, 2, 128, 128, 32)
    layer = struct.pack('<6HB3sH', 1, 2 if tilemap else 0, 0, 0, 0, 0,
                        255, b'\0' * 3, 5) + b'Layer'
    if tilemap:
        layer += struct.pack('<I', 7)
    raw = b'\0\x10\x20\xff' * (128 * 128)
    cel_kind = 0 if raw_cel else (3 if tilemap else 2)
    cel = struct.pack('<HhhBHh5s', 0, 2, 3, 255, cel_kind, 0, b'\0' * 5)
    cel += struct.pack('<HH', 128, 128)
    if tilemap:
        cel += struct.pack('<H4I10s', 32, 0x1fffffff, 0x20000000, 0x40000000,
                           0x80000000, b'\0' * 10)
    cel += raw if raw_cel else zlib.compress(raw, 1)
    linked = struct.pack('<HhhBHh5sH', 0, -1, -2, 200, 1, 0, b'\0' * 5, 0)
    frames = _ase_frame([_ase_chunk(0x2004, layer), _ase_chunk(0x7777, b'unknown metadata'),
                         _ase_chunk(0x2005, cel)], 123)
    frames += _ase_frame([_ase_chunk(0x2005, linked)], 456)
    struct.pack_into('<I', header, 0, len(header) + len(frames))
    return bytes(header) + frames, raw


def nrrd_bytes(*, encoding='raw', newline=b'\n', dtype='uint16', raw=None):
    raw = raw if raw is not None else b'\x12\x34' * (128 * 128)
    header = newline.join([
        b'NRRD0005', b'# preserve this comment', b'type: ' + dtype.encode(),
        b'dimension: 2', b'sizes: 128 128', b'endian: big',
        b'space origin: (1,2,3)', b'patient:=exact unchanged string',
        b'encoding: ' + encoding.encode(), b'', b'',
    ])
    payload = raw
    if encoding in ('gzip', 'gz'):
        payload = gzip.compress(raw, compresslevel=1, mtime=123)
    elif encoding in ('bzip2', 'bz2'):
        payload = bz2.compress(raw, compresslevel=1)
    return header + payload, raw


def qgd_database(path, *, implicit_rowids=False):
    with sqlite3.connect(str(path)) as database:
        database.execute('PRAGMA application_id=123')
        database.execute('PRAGMA user_version=7')
        columns = 'value TEXT' if implicit_rowids else 'id INTEGER PRIMARY KEY, value TEXT'
        database.execute('CREATE TABLE auxiliary(' + columns + ')')
        if implicit_rowids:
            database.executemany('INSERT INTO auxiliary(rowid,value) VALUES (?,?)',
                                 [(10, 'keep a'), (1000, 'keep b')])
        else:
            database.executemany('INSERT INTO auxiliary VALUES (?,?)',
                                 ((index, 'stored data ' * 100) for index in range(200)))
            database.execute('DELETE FROM auxiliary WHERE id >= 10')
        database.execute('CREATE INDEX auxiliary_values ON auxiliary(value)')


QGIS_XML = (b'<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'>\n'
            b'<qgis  version = "3.44.0" projectname = "Test">\n'
            b'<title>  title whitespace stays  </title>\n'
            b'<projectlayers><maplayer  name = "keep" /></projectlayers>\n</qgis>')
