"""Independent mixed-Data controls: binary fields and chained table formatting."""

import struct

import pytest

from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_verify import CompoundFile
from filerepack.ole_word_art import DATA, WORD, u32
from test.ole_art_fixtures import container, control


def budget(**limits):
    return Budget(FormatLimits(**limits))


def mixed_word():
    source = control("vector_image.doc")
    word, table = bytearray(source.streams[WORD]), bytearray(source.streams["1Table",])
    pic = source.streams[DATA][:u32(source.streams[DATA], 0)]
    payload = b"\xff\0opaque binary field\x01\x02\x03"
    binary = struct.pack("<IH", 68 + len(payload), 68) + b"\0" * 62 + payload
    table_grp = struct.pack("<HBHIHH", 0x2416, 1, 0x6649, 1, 0xA414, 120)
    table_prc = struct.pack("<H", len(table_grp)) + table_grp
    table_at = len(pic + binary)
    huge_grp = struct.pack("<HIHH", 0x646B, table_at, 0xA413, 240)
    huge_prc = struct.pack("<H", len(huge_grp)) + huge_grp
    huge_at = table_at + len(table_prc)
    data = pic + binary + table_prc + huge_prc
    text = b"\x01\x13 ADDIN \x14\x01\x15\r"
    binary_fc = 2048 + text.index(b"\x01", 1)
    end = 2048 + len(text)
    word[2048:end] = text
    struct.pack_into("<I", word, 28, end)
    struct.pack_into("<I", word, 76, len(text))
    clx = u32(word, 418)
    struct.pack_into("<I", table, clx + 9, len(text))
    # Independent FKP encoding, with a single-character CFData run.
    chpx = bytearray(512)
    bounds = (1536, 2049, binary_fc, binary_fc + 1, end)
    struct.pack_into("<5I", chpx, 0, *bounds)
    props = (
        struct.pack("<HIHB", 0x6A03, 0, 0x0855, 1),
        b"", struct.pack("<HIHBHB", 0x6A03, len(pic), 0x0855, 1, 0x0806, 1), b"",
    )
    for i, grp in enumerate(props):
        if grp:
            at = 200 + i * 40
            chpx[20 + i] = at // 2
            chpx[at] = len(grp)
            chpx[at + 1:at + 1 + len(grp)] = grp
    chpx[511] = 4
    word[2560:3072] = chpx
    papx = bytearray(512)
    struct.pack_into("<II", papx, 0, 1536, end)
    papx[8] = 100
    papx[200:210] = b"\0\4\0\0" + struct.pack("<HI", 0x6646, huge_at)
    papx[511] = 1
    word[3072:3584] = papx
    for index in (12, 13):
        at = u32(word, 154 + 8 * index)
        struct.pack_into("<I", table, at + 4, end)
    # The binary character is inside an ADDIN field (PlcfFldMom).
    fields = struct.pack("<4I", 1, text.index(b"\x14"), text.index(b"\x15"), len(text))
    fields += b"\x13\x51\x14\0\x15\0"
    struct.pack_into("<II", word, 154 + 8 * 16, len(table), len(fields))
    table.extend(fields)
    return CompoundFile(container(source, {**source.streams, WORD: bytes(word),
                                           ("1Table",): bytes(table), DATA: data}))


def replace(source, path, data):
    return CompoundFile(container(source, {**source.streams, path: bytes(data)}))


def test_picture_shrink_relocates_binary_and_both_levels_of_table_properties(monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "_zopfli", lambda: None)
    source = mixed_word()
    before = inspect_art(source, budget())
    changes, details = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert details["stream_savings_bytes"] > 0 and equal_art(before, after)
    assert len(before.adapter.refs) == 3 and len(before.adapter.data_refs) == 1
    assert all(a > b for a, b in zip(sorted(before.adapter.refs.values())[1:],
                                   sorted(after.adapter.refs.values())[1:]))
    # Private bytes and table operands stay exact; only the nested Data offset changes.
    assert before.adapter.blocks[1][1] == after.adapter.blocks[1][1]
    assert before.adapter.blocks[2][1] == after.adapter.blocks[2][1]
    assert ("1Table",) not in changes
    assert source.streams["1Table",] == after.adapter.table


@pytest.mark.parametrize("fault", ("cycle", "bounds", "length", "overlap", "unknown"))
def test_external_paragraph_corruption_fails_closed(fault):
    source = mixed_word()
    before = inspect_art(source, budget()).adapter
    data = bytearray(source.streams[DATA])
    table_at, huge_at = before.blocks[2][0], before.blocks[3][0]
    if fault == "cycle":
        struct.pack_into("<I", data, huge_at + 4, huge_at)
    elif fault == "bounds":
        struct.pack_into("<I", data, huge_at + 4, len(data))
    elif fault == "length":
        struct.pack_into("<H", data, table_at, 0xFFFF)
    elif fault == "overlap":
        struct.pack_into("<H", data, table_at, len(data) - table_at - 2)
    else:
        struct.pack_into("<H", data, table_at + 2, 0xFFFF)
    with pytest.raises(ValueError):
        inspect_art(replace(source, DATA, data), budget())


def test_stale_or_wrong_valid_prc_target_is_not_an_equal_candidate(monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "_zopfli", lambda: None)
    source = mixed_word()
    before = inspect_art(source, budget())
    changes, _ = before.reencode(budget())
    candidate = CompoundFile(container(source, {**source.streams, **changes}))
    after = inspect_art(candidate, budget())
    word = bytearray(changes[WORD])
    huge_field = max(before.adapter.refs)
    # The unchanged source target is now outside the shortened Data stream.
    struct.pack_into("<I", word, huge_field, before.adapter.refs[huge_field])
    with pytest.raises(ValueError):
        inspect_art(replace(candidate, WORD, word), budget())
    # A valid smaller PrcData is a different formatting identity.
    struct.pack_into("<I", word, huge_field, after.adapter.blocks[2][0])
    # This leaves the original, still present HugePapx region without a consumer.
    with pytest.raises(ValueError):
        inspect_art(replace(candidate, WORD, word), budget())


def test_private_binary_bytes_and_metadata_cannot_change(monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "_zopfli", lambda: None)
    source = mixed_word()
    before = inspect_art(source, budget())
    data = bytearray(source.streams[DATA])
    binary_at = sorted(before.adapter.refs.values())[1]
    data[binary_at + 68] ^= 1
    assert not equal_art(before, inspect_art(replace(source, DATA, data), budget()))
    data[binary_at + 6] = 1
    with pytest.raises(ValueError, match="NilPICF"):
        inspect_art(replace(source, DATA, data), budget())


def test_chained_properties_obey_existing_depth_and_node_limits():
    source = mixed_word()
    with pytest.raises(FormatLimit):
        inspect_art(source, budget(depth=1))
    with pytest.raises(FormatLimit):
        inspect_art(source, budget(nodes=1))


def test_table_definition_uses_its_two_byte_length():
    from filerepack.ole_word_art import TABLE, properties

    # 16 columns: the operand exceeds a one-byte length. No stream offsets.
    operand = b"\x10" + b"\0" * (2 * 17 + 20 * 16)
    data = struct.pack("<HH", 0xD608, len(operand) + 1) + operand
    assert properties(data, 0, TABLE)[0xD608][1] == data[2:]
    with pytest.raises(ValueError):
        properties(data[:-1], 0, TABLE)


@pytest.mark.parametrize("kind", ("style", "following-operand"))
def test_huge_paragraph_requires_the_specified_fkp_envelope(kind):
    source = mixed_word()
    word = bytearray(source.streams[WORD])
    if kind == "style":
        struct.pack_into("<H", word, 3274, 1)
    else:
        word[3273] = 6  # Extended Papx size grows by four bytes.
        struct.pack_into("<HH", word, 3282, 0xA413, 120)
    with pytest.raises(ValueError):
        inspect_art(replace(source, WORD, word), budget())


def test_inline_named_shape_retains_scalar_flags_and_exact_complex_name():
    from filerepack.ole_officeart import Parser, header

    name = "Picture 10".encode("utf-16le") + b"\0\0"
    props = struct.pack("<HIHIHIHI", 0x13F, 0x60000, 0x1BF, 0x110000,
                        0xC380, len(name), 0x3BF, 0x20000) + name
    data = header((4 << 4) | 3, 0xF00B, props)
    parsed = Parser(budget()).sequence(data)[0]
    assert parsed.encode({}) == data and parsed.body.endswith(name)
    damaged = bytearray(props)
    damaged[-1] = 1
    with pytest.raises(ValueError, match="terminator"):
        Parser(budget()).sequence(header((4 << 4) | 3, 0xF00B, damaged))
