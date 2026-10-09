"""Original raw NIB fixtures, assembled independently of the production writer."""

import struct


def integer(value, padded=False):
    digits = []
    while True:
        digits.append(value % 128)
        value //= 128
        if not value:
            break
    if padded:
        digits.append(0)
    digits[-1] += 128
    return bytes(digits)


def archive_bytes(objects, keys, values, classes, padded=False, coder=9):
    tables = [
        b''.join(integer(field, padded) for obj in objects for field in obj),
        b''.join(integer(len(key), padded) + key for key in keys),
        b''.join(integer(key, padded) + bytes([kind]) +
                 (integer(len(payload), padded) if kind == 8 else b'') + payload
                 for key, kind, payload in values),
        b''.join(integer(len(name), padded) + integer(len(extra) // 4, padded) + extra + name
                 for name, extra in classes),
    ]
    header = [1, coder]
    position = 50
    for entries, table in zip((objects, keys, values, classes), tables):
        header.extend((len(entries), position))
        position += len(table)
    return b'NIBArchive' + struct.pack('<10I', *header) + b''.join(tables)


def nib_parts():
    keys = [b'UINibTopLevelObjectsKey', b'NS.bytes', b'number', b'flag', b'reference',
            b'unused key', b'NS.bytes']
    classes = [(b'NSObject\0', b''), (b'CustomView\0', struct.pack('<I', 0)),
               (b'UnusedClass\0', struct.pack('<2I', 0, 1))]
    # All eleven types; repeated keys, opaque bytes, signed zero and a NaN payload.
    properties = [
        (2, 0, b'\xff'), (2, 1, struct.pack('<h', -123)),
        (2, 2, struct.pack('<i', -123456)), (2, 3, struct.pack('<q', -12345678901)),
        (3, 4, b''), (3, 5, b''), (2, 6, struct.pack('<I', 0x80000000)),
        (2, 7, struct.pack('<Q', 0x7FF8000000004321)),
        (1, 8, b'keep  \0\xff opaque NIBArchive payload' * 8),
        (1, 9, b''), (4, 10, struct.pack('<I', 3)),
    ]
    values = [(0, 10, struct.pack('<I', 1)), (0, 10, struct.pack('<I', 2))]
    values += properties + properties + [(4, 10, struct.pack('<I', 1))]
    values += [(6, 8, b'orphan value retained exactly')]
    objects = [(0, 0, 2), (1, 2, 11), (1, 13, 11), (0, 24, 1)]
    return objects, keys, values, classes


def nib_bytes(padded=False, coder=9):
    return archive_bytes(*nib_parts(), padded=padded, coder=coder)
