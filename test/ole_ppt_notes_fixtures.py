"""Generated notes/master/shared-Pictures PPT controls; no private corpus bytes."""

import struct
import zlib

from filerepack.ole_verify import CompoundFile
from test.ole_fixtures import compound_bytes
from test.test_ole_raster import png


def record(flags, kind, body):
    return struct.pack("<HHI", flags, kind, len(body)) + body


def shape(index, external=False, extra=b""):
    body = record(19, 0xF00B, struct.pack("<HI", 0x4104, index))
    if external:
        body += record(15, 0xF011, record(0, 3009, struct.pack("<I", 24)))
    return record(15, 0xF004, body + extra)


def drawing(body=b""):
    return record(15, 1036, record(15, 0xF002, body))


def notes_page(slide_id, flags, body=b""):
    return record(
        15,
        1008,
        record(1, 1009, struct.pack("<IHH", slide_id, flags, 0xABCD))
        + drawing(body)
        + record(16, 2032, b"\0" * 32),
    )


def presentation(
    *, notes=True, legacy=False, embedded=True, images=None, document_info=b"",
    drawing_group_extra=b"", master_extra=b"", slide_extra=b"", slide_shape_extra=b"",
):
    images = images or [png(), png(width=32, height=16)]
    types = [5 if image.startswith(b"\xff\xd8") else 6 for image in images]
    blips = [
        record(
            0x46A0 if types[i] == 5 else 0x6E00,
            0xF01D if types[i] == 5 else 0xF01E,
            bytes([i + 1]) * 16 + b"\xff" + image,
        )
        for i, image in enumerate(images)
    ]
    assert len(blips) == 2
    entries, offset = [], 0
    for i, blip in enumerate(blips):
        body = bytearray(36)
        body[:2] = bytes([types[i]]) * 2
        body[2:18] = bytes([i + 1]) * 16
        struct.pack_into(
            "<HIII", body, 18, 0xFF, len(blip), 2 + int(notes) if i == 0 else 1, offset
        )
        entries.append(record(types[i] << 4 | 2, 0xF007, bytes(body)))
        offset += len(blip)
    group = record(
        15, 1035, record(15, 0xF000, record(47, 0xF001, b"".join(entries)) + drawing_group_extra)
    )
    atom = bytearray(40)
    struct.pack_into("<I", atom, 24, 2 if notes else 0)
    document = record(1, 1001, bytes(atom)) + group
    if document_info:
        document += record(15, 2000, document_info)
    if embedded:
        obj = record(1, 4035, struct.pack("<6I", 1, 0, 24, 0, 3, 0))
        document += record(
            15,
            1033,
            record(0, 1034, struct.pack("<I", 25))
            + record(15, 4044, record(0, 4045, b"\0" * 8) + obj),
        )
    for instance, identifier, logical_id in ((1, 4, 0x80000001), (0, 5, 256), (2, 6, 512)):
        if instance != 2 or notes:
            document += record(
                (instance << 4) | 15,
                4080,
                record(0, 1011, struct.pack("<5I", identifier, 0, 0, logical_id, 0)),
            )
    top = [(1, record(15, 1000, document))]
    if notes:
        top.append((2, notes_page(0x80000000 if legacy else 0, 2 if legacy else 0)))
    master = record(2, 1007, b"\0" * 24) + drawing(shape(1, embedded)) + master_extra
    top.append((4, record(15, 1016, master)))
    slide_atom = bytearray(24)
    struct.pack_into("<II", slide_atom, 12, 0x80000001, 512 if notes else 0)
    top.append(
        (5, record(
            15, 1006, record(2, 1007, bytes(slide_atom))
            + drawing(shape(1, extra=slide_shape_extra) + shape(2)) + slide_extra,
        ))
    )
    if notes:
        top.append((6, notes_page(256, 3, shape(1))))
    if embedded:
        raw = compound_bytes(
            {
                ("CONTENTS",): b"immutable Photoshop image" * 256,
                ("\x01CompObj",): b"Adobe Photoshop Image",
            }
        )
        top.append((3, record(16, 4113, struct.pack("<I", len(raw)) + zlib.compress(raw))))
    targets, data = {}, bytearray()
    for identifier, body in top:
        targets[identifier] = len(data)
        data.extend(body)
    directory = len(data)
    index = b"".join(
        struct.pack("<II", (1 << 20) | i, target) for i, target in sorted(targets.items())
    )
    data.extend(record(0, 6002, index))
    edit = len(data)
    data.extend(
        record(0, 4085, struct.pack("<IHBBIIIIHH", 0, 0, 0, 3, 0, directory, 1, max(targets), 0, 0))
    )
    current = record(0, 4086, struct.pack("<IIIHHBBHI", 20, 0xE391C05F, edit, 0, 0x3F4, 3, 0, 0, 0))
    streams = {
        ("PowerPoint Document",): bytes(data),
        ("Current User",): current,
        ("Pictures",): b"".join(blips),
    }
    return CompoundFile(compound_bytes(streams))
