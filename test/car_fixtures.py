"""Small complete CAR stores; payloads and allocation gaps are generated locally."""

import struct
import zlib


def car_bytes(bands=False, opaque=False):
    raw = b'Preserve exact decoded CAR pixels and native metadata.\0' * 2000
    chunks = [raw[:len(raw) // 2], raw[len(raw) // 2:]] if bands else [raw]
    streams = [zlib.compress(part, 1) for part in chunks]
    if bands:
        body = b'MLEC' + struct.pack('<III', 1, 2, 2) + b''.join(
            b'KCBC' + bytes(range(12)) + struct.pack('<I', len(stream)) + stream
            for stream in streams)
    else:
        body = b'MLEC' + struct.pack('<III', 0, 2, len(streams[0])) + streams[0]
    if opaque:
        body = b'Unknown encoding\0' + raw[:128]
    rendition = bytearray(184)
    rendition[:4] = b'ISTC'
    struct.pack_into('<I', rendition, 4, 1)
    tlv = struct.pack('<II', 0x1000, 16) + b'native metadata!'
    struct.pack_into('<4I', rendition, 168, len(tlv), 0, 0, len(body))
    rendition.extend(tlv + body)
    catalog = bytearray(436)
    catalog[:4] = b'RATC'
    struct.pack_into('<I', catalog, 8, 8)
    struct.pack_into('<I', catalog, 16, 1)
    page = bytearray(512)
    struct.pack_into('>HHII', page, 0, 1, 1, 0, 0)
    struct.pack_into('>II', page, 12, 4, 5)
    tree = b'tree' + struct.pack('>4I', 1, 6, 512, 1) + b'\0'
    key = b'tmfk\0\0\0\0' + struct.pack('<I', 1) + b'\0' * 4
    blocks = {1: catalog, 2: tree, 3: key, 4: rendition, 5: b'\0\0', 6: page,
              7: b'opaque resource retained exactly'}
    variables = bytearray(struct.pack('>I', 4))
    for block, name in ((1, b'CARHEADER'), (2, b'RENDITIONS'), (3, b'KEYFORMAT'), (7, b'opaque')):
        variables.extend(struct.pack('>IB', block, len(name)) + name)
    output, pointers = bytearray(512), [(0, 0)] * 256
    output[:8] = b'BOMStore'
    output.extend(b'\0' * 4096)
    for block, data in blocks.items():
        output.extend(b'\0' * (-len(output) % 16))
        pointers[block] = len(output), len(data)
        output.extend(data)
    output.extend(b'\0' * (-len(output) % 16))
    var_at = len(output)
    output.extend(variables)
    output.extend(b'\0' * (-len(output) % 16))
    index_at = len(output)
    output.extend(struct.pack('>I', len(pointers)))
    for address, size in pointers:
        output.extend(struct.pack('>II', address, size))
    output.extend(struct.pack('>I', 0))
    struct.pack_into('>6I', output, 8, 1, len(blocks), index_at, len(output) - index_at,
                     var_at, len(variables))
    return bytes(output)
