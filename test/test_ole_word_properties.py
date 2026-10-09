"""Audited Word formatting retains bytes and rejects hidden reference owners."""

import struct

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.format_support import Budget, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_officeart import Parser, header
from filerepack.ole_verify import CompoundFile
from filerepack.ole_word_art import CHAR, PARA, TABLE, fib_slice, properties, u16
from test.ole_art_fixtures import DATA, WORD, container, control
from test.test_ole import native_writer as _native_writer
from test.test_ole_host_coverage import inherited_word

native_writer = _native_writer


def budget():
    return Budget(FormatLimits())


def conditional(code, nested, condition=1):
    return struct.pack("<HBH", code, 2 + len(nested), condition) + nested


def formatted_word(char_cond=None, para_cond=None, table_cond=None):
    source = control("vector_image.doc")
    layout = inspect_art(source, budget()).adapter
    word, table = bytearray(source.streams[WORD]), bytearray(source.streams["1Table",])
    old = fib_slice(word, table, 1)
    pos, styles = 2 + u16(old, 0), []
    for _ in range(u16(old, 2)):
        size = u16(old, pos)
        styles.append(old[pos + 2 : pos + 2 + size])
        pos += 2 + size + size % 2
    char_cond = struct.pack("<HH", 0x4A43, 28) if char_cond is None else char_cond
    para_cond = struct.pack("<HB", 0x2431, 1) if para_cond is None else para_cond
    table_cond = struct.pack("<HB", 0x3488, 2) if table_cond is None else table_cond
    groups = (
        conditional(0xD66A, table_cond) + struct.pack("<H", 0xD613) + b"\x30" + b"\0" * 48,
        struct.pack("<H", 2) + conditional(0xC666, para_cond),
        conditional(0xCA85, char_cond),
    )
    body = bytearray(18)
    struct.pack_into("<HH", body, 2, 0xFFF3, 0xFFF3)
    body.extend(b"\0" * 4)  # Empty UTF16 style name and terminator.
    for group in groups:
        body.extend(struct.pack("<H", len(group)) + group + b"\0" * (len(group) % 2))
    struct.pack_into("<H", body, 6, len(body))
    styles[2] = bytes(body)
    sheet = old[: 2 + u16(old, 0)] + b"".join(
        struct.pack("<H", len(s)) + s + b"\0" * (len(s) % 2) for s in styles
    )
    struct.pack_into("<II", word, 162, len(table), len(sheet))
    table.extend(sheet)
    start, prefix, records = layout.blocks[0]
    shape = records[0]
    children = []
    for child in shape.children:
        if child.kind != 0xF00B:
            children.append(child.original())
            continue
        count = child.flags >> 4
        props = [struct.unpack_from("<HI", child.body, 6 * i) for i in range(count)]
        props.extend(((0x7F, 0), (0x33F, 0x100010)))
        props.sort(key=lambda p: p[0] & 0x3FFF)
        body = b"".join(struct.pack("<HI", *p) for p in props) + child.body[6 * count :]
        children.append(header(len(props) << 4 | 3, 0xF00B, body))
    children.append(header(0x13, 0xF122, struct.pack("<HI", 0x3AA, 0xF000000)))
    record_bytes = header(shape.flags, shape.kind, b"".join(children)) + records[1].original()
    framed = bytearray(prefix)
    struct.pack_into("<I", framed, 0, len(framed) + len(record_bytes))
    original_size = len(prefix) + sum(len(r.original()) for r in records)
    # A complete, unreferenced history picture precedes the selected picture.
    history = source.streams[DATA][start : start + original_size]
    data = history + b"\0" * 8 + framed + record_bytes + source.streams[DATA][original_size:]
    for field in layout.refs:
        struct.pack_into("<I", word, field, len(history) + 8)
    return CompoundFile(
        container(source, {**source.streams, WORD: bytes(word), DATA: bytes(data),
                           ("1Table",): bytes(table)})
    )


def test_conditional_styles_drawing_flags_and_history_survive_recompression(monkeypatch):
    monkeypatch.setattr("filerepack.ole_officeart._zopfli", lambda: None)
    source = formatted_word()
    before = inspect_art(source, budget())
    changes, details = before.reencode(budget())
    candidate = CompoundFile(container(source, {**source.streams, **changes}))
    after = inspect_art(candidate, budget())
    assert details["stream_savings_bytes"] > 0 and equal_art(before, after)
    assert source.streams["1Table",] == candidate.streams["1Table",]
    assert before.adapter.blocks[0][1] == after.adapter.blocks[0][1]
    assert before.adapter.blocks[1][2][0].original() == after.adapter.blocks[1][2][0].original()
    # A valid but different z-order or style font is still a preservation failure.
    for stream, marker, at in (
        (DATA, struct.pack("<HI", 0x3AA, 0xF000000), 2),
        (("1Table",), conditional(0xCA85, struct.pack("<HH", 0x4A43, 28)), 7),
    ):
        value = bytearray(candidate.streams[stream])
        field = value.rindex(marker) + at
        value[field] ^= 1
        damaged = CompoundFile(container(candidate, {**candidate.streams, stream: bytes(value)}))
        assert not equal_art(before, inspect_art(damaged, budget()))


@pytest.mark.parametrize(
    "part,nested",
    [
        ("char_cond", struct.pack("<HI", 0x6A03, 0)),
        ("char_cond", struct.pack("<HB", 0x0855, 1)),
        ("char_cond", struct.pack("<H", 0xFFFF)),
        ("char_cond", conditional(0xCA85, b"")),
        ("para_cond", struct.pack("<HI", 0x6646, 0)),
        ("para_cond", struct.pack("<HI", 0x646B, 0)),
        ("table_cond", struct.pack("<HI", 0x6646, 0)),
        ("table_cond", struct.pack("<HI", 0x7479, 123)),  # Style-preserved revision ID.
        ("table_cond", struct.pack("<HB", 0xD670, 0)),  # UpxTapx forbids raw cell shading.
        ("table_cond", conditional(0xD66A, b"")),
        ("table_cond", struct.pack("<H", 0xD613) + b"\x30\0"),
    ],
)
def test_conditional_styles_reject_unknown_nested_properties_and_hidden_offsets(part, nested):
    with pytest.raises(ValueError):
        inspect_art(formatted_word(**{part: nested}), budget())


@pytest.mark.parametrize("code,allowed", [(0xCA85, CHAR), (0xC666, PARA), (0xD66A, TABLE)])
def test_conditional_operand_requires_table_style_and_one_valid_condition(code, allowed):
    with pytest.raises(ValueError, match="outside a Word table style"):
        properties(conditional(code, b""), 0, allowed)
    for condition in (0, 3, 0x1000, 0xFFFF):
        with pytest.raises(ValueError, match="conditional formatting condition"):
            properties(conditional(code, b"", condition), 0, allowed, table_style=True)
    with pytest.raises(ValueError, match="truncated Word property operand"):
        properties(conditional(code, b"\0")[:-1], 0, allowed, table_style=True)


@pytest.mark.parametrize("code", [0x0800, 0x0801, 0x4804, 0x6805, 0x6817, 0x4863,
                                 0x6864, 0xCA89, 0x2A83, 0x2A0C])
def test_new_revision_identity_properties_remain_forbidden_in_character_styles(code):
    size = (1, 1, 2, 4, 2, 2, 1, 3)[code >> 13]
    with pytest.raises(ValueError, match="forbidden Word style property"):
        inspect_art(inherited_word(struct.pack("<H", code) + b"\0" * size), budget())


@pytest.mark.parametrize("extended", [False, True])
def test_tab_array_framing_does_not_swallow_the_following_picture_reference(extended):
    deleted, added = (64, 2) if extended else (1, 1)
    body = bytes([deleted]) + b"\0" * (4 * deleted) + bytes([added]) + b"\0" * (3 * added)
    operand = bytes([255 if extended else len(body)]) + body
    data = struct.pack("<H", 0xC615) + operand + struct.pack("<HI", 0x6A03, 123)
    parsed = properties(data, 0, PARA | CHAR)
    assert parsed[0x6A03] == (4 + len(operand), struct.pack("<I", 123))
    for corrupt in (operand[:-1], bytes([1]) + operand[1:], b"\xff\x41"):
        with pytest.raises(ValueError):
            properties(struct.pack("<H", 0xC615) + corrupt, 0, PARA)


def test_word_only_drawing_properties_and_exact_empty_complex_defaults():
    defaults = header(0x23, 0xF00B, struct.pack("<HIHI", 0xC186, 0, 0xC1C5, 0))
    parsed = Parser(budget(), word_properties=True).sequence(defaults)[0]
    assert parsed.original() == defaults
    with pytest.raises(ValueError, match="unsupported FOPT property"):
        Parser(budget()).sequence(defaults)
    for code, value in ((0xC186, 1), (0x4186, 1), (0x807F, 0), (0x433F, 0)):
        record = header(0x13, 0xF00B, struct.pack("<HI", code, value))
        with pytest.raises(ValueError):
            Parser(budget(), word_properties=True).sequence(record)


@pytest.mark.parametrize("fault", ["owner", "version", "count", "length", "property", "bid",
                                  "complex", "host"])
def test_tertiary_z_order_rejects_wrong_scope_and_malformed_tables(fault):
    flags, code, body = 0x13, 0x3AA, struct.pack("<HI", 0x3AA, 7)
    if fault == "version":
        flags = 0x12
    elif fault == "count":
        flags = 0x23
    elif fault == "length":
        body += b"\0"
    elif fault in ("property", "bid", "complex"):
        code = {"property": 0x186, "bid": 0x43AA, "complex": 0x83AA}[fault]
        body = struct.pack("<HI", code, 7)
    blob = header(15, 0xF000 if fault == "owner" else 0xF004, header(flags, 0xF122, body))
    with pytest.raises(ValueError):
        Parser(budget(), word_properties=fault != "host").sequence(blob)


@pytest.mark.parametrize("dryrun", [False, True])
def test_public_doc_candidate_with_new_properties_preserves_source_and_metadata(
    tmp_path, native_writer, dryrun
):
    source, output = tmp_path / "formatted.doc", tmp_path / "smaller.doc"
    original = formatted_word().data
    source.write_bytes(original)
    result = FileRepacker().repack(
        str(source), outfile=str(output), options=RepackOptions(ole_recompress=True, dryrun=dryrun)
    ).results[0]
    assert result.details["strategy"] == "ole-officeart-recompression"
    assert result.outsize < result.insize and source.read_bytes() == original
    if dryrun:
        assert not output.exists()
    else:
        assert equal_art(inspect_art(CompoundFile(original), budget()),
                         inspect_art(CompoundFile(output.read_bytes()), budget()))


def test_public_hidden_conditional_picture_location_retains_strict_fallback(
    tmp_path, native_writer
):
    source = tmp_path / "hidden-reference.doc"
    original = formatted_word(char_cond=struct.pack("<HI", 0x6A03, 0)).data
    source.write_bytes(original)
    result = FileRepacker().repack(
        str(source), options=RepackOptions(ole_recompress=True, dryrun=True)
    ).results[0]
    assert result.details["strategy"] == "ole-compaction"
    assert "unsupported Word property: 0x6a03" in result.details["officeart_skip"]
    assert source.read_bytes() == original
