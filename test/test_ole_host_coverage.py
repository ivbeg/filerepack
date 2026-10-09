"""Encoding controls for populated BIFF and table-owned Word picture pointers."""

import struct

import pytest

from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_officeart import Parser
from filerepack.ole_dedup import inspect_dedup
from filerepack.ole_ppt import read_records
from filerepack.ole_verify import CompoundFile, read_compound
from filerepack.ole_word_art import WORD, DATA, u32
from filerepack.ole_xls_art import WORKBOOK, biff, shared_strings, worksheet_drawing
from test.ole_art_fixtures import container, control
from test.ole_fixtures import ADDITIONAL_ART_ORIGINALS, CORPUS

EXTENDED = CORPUS.parent / "ole_extended"


def budget():
    return Budget(FormatLimits())


def rec(kind, body):
    return struct.pack("<HH", kind, len(body)) + body


def populated_xls():
    source = control("SimpleWithImages.xls")
    layout = inspect_art(source, budget()).adapter
    records = biff(source.streams[WORKBOOK])
    sst_at, _, old_sst = next(r for r in records if r[1] == 0xFC)
    assert old_sst == b"\0" * 8
    # String characters continue with an explicit narrow -> UTF16 transition.
    sst = rec(0xFC, struct.pack("<IIHB", 1, 1, 4, 0) + b"ab")
    sst += rec(0x3C, b"\1c\0d\0")
    extsst = rec(0xFF, struct.pack("<HIHH", 8, sst_at + 12, 12, 0))
    global_add = sst + extsst
    old_end = sst_at + 18  # Includes the original empty ExtSST.
    delta = len(global_add) - 18
    book = bytearray(source.streams[WORKBOOK])
    for field, target in layout.pointers.items():
        if target >= old_end:
            struct.pack_into("<I", book, field, target + delta)
    book = bytearray(book[:sst_at] + global_add + book[old_end:])
    records = biff(bytes(book))
    # Put a populated row block before the final worksheet EOF; all existing
    # drawing records and their consumers retain exact order/content.
    end = [at for at, kind, _ in records if kind == 0xA][-1]
    row = rec(0x208, struct.pack("<8H", 0, 0, 2, 255, 0, 0, 0, 0))
    number = rec(0x203, struct.pack("<HHHd", 0, 0, 0, 1.25))
    label = rec(0xFD, struct.pack("<HHHI", 0, 1, 0, 0))
    formula = rec(6, struct.pack("<HHHdHIH", 0, 2, 0, 2.0, 0, 0, 3) + b"\x1e\2\0")
    db_at = end + len(row + number + label + formula)
    db = rec(0xD7, struct.pack("<IH", db_at - end, 0))
    # Index may be earlier in this worksheet, and ibXF points to global Uncalced.
    sheet_bof = [at for at, kind, _ in records if kind == 0x809][-1]
    index_at = next(at for at, kind, _ in records if kind == 0x20B and at > sheet_bof)
    old_size = struct.unpack_from("<H", book, index_at + 2)[0]
    assert old_size == 16
    struct.pack_into(
        "<I", book, index_at + 16, struct.unpack_from("<I", book, index_at + 16)[0] + 4
    )
    struct.pack_into("<II", book, index_at + 8, 0, 1)
    struct.pack_into("<H", book, index_at + 2, 20)
    book = book[: index_at + 20] + struct.pack("<I", db_at + 4) + book[index_at + 20 :]
    end += 4
    book = book[:end] + row + number + label + formula + db + book[end:]
    return CompoundFile(container(source, {**source.streams, WORKBOOK: bytes(book)}))


def piece_word():
    source = control("vector_image.doc")
    art = inspect_art(source, budget()).adapter
    word, table = bytearray(source.streams[WORD]), bytearray(source.streams["1Table",])
    # Keep a fully framed, unreferenced PICF before the referenced copy.
    first_size = u32(source.streams[DATA], 0)
    data = source.streams[DATA][:first_size] + b"\0" * 8 + source.streams[DATA]
    target = first_size + 8
    grp = struct.pack("<HIHB", 0x6A03, target, 0x0855, 1)
    prc = b"\1" + struct.pack("<H", len(grp)) + grp
    pcdt = struct.pack("<3I", 0, 1, 5)
    pcdt += struct.pack("<HIH", 0x50, 0x40000000 + 2048 * 2, 1)
    pcdt += struct.pack("<HIH", 0x50, 0x40000000 + 2049 * 2, 0)
    clx = prc + b"\2" + struct.pack("<I", len(pcdt)) + pcdt
    struct.pack_into("<II", word, 418, len(table), len(clx))
    table.extend(clx)
    # The original first CHPX contains PicLocation, a font property and fSpec.
    field = next(iter(art.refs))
    start = field - 2
    assert word[start : start + 2] == b"\3j"
    old_length = word[start - 1]
    assert old_length == 15
    keep = word[start + 6 : start + 12]
    word[start - 1] = len(keep)
    word[start : start + len(keep)] = keep
    return CompoundFile(
        container(
            source, {**source.streams, WORD: bytes(word), ("1Table",): bytes(table), DATA: data}
        )
    )


def test_populated_cells_formula_continued_sst_and_dbcell_are_exact():
    source = populated_xls()
    before = inspect_art(source, budget())
    changes, details = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert details["stream_savings_bytes"] > 0 and equal_art(before, after)
    unchanged = {0x208, 0x203, 0xFD, 6, 0xD7, 0xFC}
    assert [(k, p) for _, k, p in biff(before.adapter.data) if k in unchanged] == [
        (k, p) for _, k, p in biff(after.adapter.data) if k in unchanged
    ]


def test_piece_owned_location_mixed_picf_and_padding_are_preserved():
    source = piece_word()
    before = inspect_art(source, budget())
    assert all(at < 0 for at in before.adapter.refs)
    changes, details = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after) and details["stream_savings_bytes"] > 0
    assert changes[WORD] == source.streams[WORD]
    # An opaque leading PICF cannot shrink, so the target and table stay exact.
    assert changes["1Table",] == source.streams["1Table",]
    assert before.adapter.blocks[0][1] == after.adapter.blocks[0][1]
    assert before.adapter.gaps == after.adapter.gaps


@pytest.mark.parametrize("fault", ("extsst", "dbcell", "label", "formula", "continue"))
def test_populated_pointer_and_string_faults_are_rejected(fault):
    source = populated_xls()
    data = bytearray(source.streams[WORKBOOK])
    kind = {"extsst": 0xFF, "dbcell": 0xD7, "label": 0xFD, "formula": 6, "continue": 0x3C}[fault]
    records = biff(bytes(data))
    if fault == "continue":
        at = next(at for at, k, p in records if k == kind and p == b"\1c\0d\0")
        data[at + 4] = 2
    else:
        at = next(at for at, k, p in records if k == kind and (fault != "dbcell" or len(p) == 6))
        off = {"extsst": 6, "dbcell": 4, "label": 10, "formula": 24}[fault]
        struct.pack_into(
            "<I" if fault in ("extsst", "dbcell", "label") else "<H",
            data,
            at + off,
            0xFFFFFFF if fault != "formula" else 5000,
        )
    with pytest.raises(ValueError):
        inspect_art(
            CompoundFile(container(source, {**source.streams, WORKBOOK: bytes(data)})), budget()
        )


def test_sst_rich_metadata_continue_is_not_character_flag():
    # Rich-text run bytes split into another CONTINUE without an encoding byte.
    first = struct.pack("<IIHBH", 1, 1, 1, 8, 1) + b"x" + b"\0\0"
    second = b"\3\0"
    strings = shared_strings([(0, 0xFC, first), (len(first) + 4, 0x3C, second)], Parser(budget()))
    assert strings == [(12, 0, 12)]


def test_real_floating_png_manifest_and_relocation():
    source = read_compound(str(CORPUS / "PngPicture.doc"))
    before = inspect_art(source, budget())
    changes, _ = before.reencode(budget(), ultra=True)
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after) and before.rasters and after.rasters


def inherited_word(style_grp=None):
    source = control("vector_image.doc")
    before = inspect_art(source, budget())
    word = bytearray(source.streams[WORD])
    table = bytearray(source.streams["1Table",])
    from filerepack.ole_word_art import fib_slice, u16

    old = fib_slice(word, table, 1)
    position = 2 + u16(old, 0)
    styles = []
    for _ in range(u16(old, 2)):
        size = u16(old, position)
        position += 2
        styles.append(old[position : position + size])
        position += size + size % 2
    # Style 1 inherits default character style 10 and supplies a font size.
    # Picture identity and fSpec must remain direct: MS-DOC forbids them in UPX.
    body = bytearray(styles[10][:18])
    name = "Picture".encode("utf-16le")
    struct.pack_into("<H", body, 2, (10 << 4) | 2)
    grp = struct.pack("<HH", 0x4A43, 24) if style_grp is None else style_grp
    body.extend(
        struct.pack("<H", 7) + name + b"\0\0" + struct.pack("<H", len(grp))
        + grp + b"\0" * (len(grp) % 2)
    )
    struct.pack_into("<H", body, 6, len(body))
    styles[1] = bytes(body)
    sheet = old[: 2 + u16(old, 0)] + b"".join(
        struct.pack("<H", len(s)) + s + b"\0" * (len(s) % 2) for s in styles
    )
    struct.pack_into("<II", word, 162, len(table), len(sheet))
    table.extend(sheet)
    field = next(iter(before.adapter.refs))
    start = field - 2
    assert word[start : start + 2] == b"\3j" and word[start + 12 : start + 15] == b"\x55\x08\1"
    direct = bytes(word[start : start + 6]) + struct.pack("<HH", 0x4A30, 1)
    direct += bytes(word[start + 12 : start + 15])
    assert len(direct) <= word[start - 1]
    word[start - 1] = len(direct)
    word[start : start + len(direct)] = direct
    return CompoundFile(
        container(source, {**source.streams, WORD: bytes(word), ("1Table",): bytes(table)})
    )


def test_character_style_inheritance_retains_exact_property_provenance():
    from filerepack.ole_word_art import fib_slice, style_properties, u32

    source = inherited_word()
    before = inspect_art(source, budget())
    assert len(before.adapter.refs) == 1 and next(iter(before.adapter.refs)) >= 0
    resolved = {}
    style_properties(
        fib_slice(source.streams[WORD], source.streams["1Table",], 1),
        budget(), base=u32(source.streams[WORD], 162), resolved=resolved,
    )
    font_field, font_value = resolved[1][0x4A43]
    assert font_field < 0 and font_value == b"\x18\0"
    assert source.streams["1Table",][-font_field - 1 : -font_field + 1] == font_value
    assert 0x6A03 not in resolved[1] and 0x0855 not in resolved[1]
    changes, _ = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after) and changes[WORD] == source.streams[WORD]
    assert ("1Table",) not in changes


@pytest.mark.parametrize(
    "code,operand",
    ((0x6A03, b"\0" * 4), (0x0855, b"\1"), (0x0856, b"\0"),
     (0x080A, b"\0"), (0x0806, b"\0"), (0x6816, b"\0" * 4), (0x4A30, b"\x0a\0")),
)
def test_identity_and_revision_properties_cannot_be_inherited_from_styles(code, operand):
    source = inherited_word(struct.pack("<H", code) + operand)
    with pytest.raises(ValueError, match="forbidden Word style property: " + hex(code)):
        inspect_art(source, budget())


@pytest.mark.parametrize("name", ("vector_image.doc", "word_with_embeded.doc", "two_images.doc"))
def test_original_inline_pictures_use_permitted_inherited_font_properties(name):
    from filerepack.ole_word_art import CHAR, fib_slice, fkps, properties, style_properties, u16

    root = EXTENDED if name == "two_images.doc" else CORPUS
    source = read_compound(str(root / name))
    before = inspect_art(source, budget())
    word, table = source.streams[WORD], source.streams[before.adapter.table_path]
    resolved = {}
    style_properties(fib_slice(word, table, 1), budget(), resolved=resolved)
    paragraphs = fkps(word, table, 13, budget())
    witnessed = set()
    for first, _, base, grp in fkps(word, table, 12, budget()):
        direct = properties(grp, base, CHAR)
        if 0x6A03 not in direct or direct[0x6A03][0] not in before.adapter.refs:
            continue
        style = next(u16(pgrp, 0) for low, high, _, pgrp in paragraphs if low <= first < high)
        inherited = set(resolved[style]) - set(direct)
        assert 0x4A43 in inherited and all(resolved[style][code][0] < 0 for code in inherited)
        assert not inherited & {0x6A03, 0x0855, 0x0856, 0x080A, 0x0806, 0x6816}
        witnessed.add(direct[0x6A03][0])
    assert witnessed == set(before.adapter.refs)
    changes, _ = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after) and before.adapter.table_path not in changes


def alternate_group_xls():
    source = populated_xls()
    layout = inspect_art(source, budget()).adapter
    book = bytearray(source.streams[WORKBOOK])
    first_continue = next(
        at for at, kind, _ in biff(bytes(book)) if layout.start < at < layout.stop and kind == 0x3C
    )
    struct.pack_into("<H", book, first_continue, 0xEB)
    return CompoundFile(container(source, {**source.streams, WORKBOOK: bytes(book)}))


def test_alternate_drawing_group_fragment_relocates_populated_pointers():
    source = alternate_group_xls()
    before = inspect_art(source, budget())
    assert sum(kind == 0xEB for _, kind, _ in biff(before.adapter.data)) == 2
    changes, details = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after) and details["stream_savings_bytes"] > 0
    assert [
        (kind, payload) for _, kind, payload in biff(before.adapter.data) if kind in (6, 0xFD)
    ] == [(kind, payload) for _, kind, payload in biff(after.adapter.data) if kind in (6, 0xFD)]


@pytest.mark.parametrize("fault", ("third", "nonadjacent"))
def test_unqualified_drawing_group_fragment_sequences_are_rejected(fault):
    source = alternate_group_xls()
    layout = inspect_art(source, budget()).adapter
    book = bytearray(source.streams[WORKBOOK])
    records = biff(bytes(book))
    extra = next(at for at, kind, _ in records if layout.start < at < layout.stop and kind == 0x3C)
    struct.pack_into("<H", book, extra, 0xEB)
    if fault == "nonadjacent":
        second = [at for at, kind, _ in records if kind == 0xEB][1]
        struct.pack_into("<H", book, second, 0x3C)
    with pytest.raises(ValueError, match="one global drawing group"):
        inspect_art(
            CompoundFile(container(source, {**source.streams, WORKBOOK: bytes(book)})), budget()
        )


@pytest.mark.parametrize("name", ADDITIONAL_ART_ORIGINALS)
def test_additional_originals_complete_art_preservation(name):
    source = read_compound(str(EXTENDED / name))
    before = inspect_art(source, budget())
    changes, _ = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after)
    if name == "28774.xls":
        records = biff(before.adapter.data)
        assert any(kind == 0xFD for _, kind, _ in records)
        assert any(kind == 0xFC and payload[:8] != b"\0" * 8 for _, kind, payload in records)
        assert [(k, p) for _, k, p in records if k in (0xFD, 0xFC, 0x208, 0xEC)] == [
            (k, p) for _, k, p in biff(after.adapter.data) if k in (0xFD, 0xFC, 0x208, 0xEC)
        ]


def test_original_mixed_qualified_and_opaque_rasters_preserve_all_eight_images():
    source = read_compound(str(EXTENDED / "nissl-lab-multimedia.doc"))
    before = inspect_art(source, budget())
    assert len(before.adapter.pictures) == 8 and len(before.rasters) == 7
    assert any("critical/unsafe PNG chunk" in reason for reason in before.raster_skips)
    opaque = [i for i, picture in enumerate(before.adapter.pictures) if picture.raster is None]
    assert len(opaque) == 1
    changes, details = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**source.streams, **changes})), budget())
    assert equal_art(before, after) and details["recompressed_rasters"] > 0
    assert len(after.adapter.pictures) == 8
    for index in opaque:
        assert before.adapter.pictures[index].original() == after.adapter.pictures[index].original()


def tertiary_book(source):
    book = bytearray(source.streams[WORKBOOK])
    layout = inspect_art(source, budget()).adapter
    drawing, fields = bytearray(), []
    for at, kind, payload in biff(bytes(book)):
        if at >= layout.stop and kind in (0xEC, 0x3C):
            drawing.extend(payload)
            fields.extend(range(at + 4, at + 4 + len(payload)))
    at = next(at for at, record in read_records(bytes(drawing)).items() if record.kind == 0xF122)
    assert fields[at : at + 14] == list(range(fields[at], fields[at] + 14))
    return book, fields[at]


@pytest.mark.parametrize("fault", ("version", "count", "property", "blip", "complex"))
def test_unqualified_tertiary_property_variants_are_rejected(fault):
    source = read_compound(str(EXTENDED / "28774.xls"))
    book, at = tertiary_book(source)
    offset, value = {
        "version": (0, 0x12),
        "count": (0, 0x23),
        "property": (8, 0x186),
        "blip": (8, 0x41BF),
        "complex": (8, 0x81BF),
    }[fault]
    struct.pack_into("<H", book, at + offset, value)
    with pytest.raises(ValueError, match="worksheet drawing|tertiary worksheet"):
        inspect_art(
            CompoundFile(container(source, {**source.streams, WORKBOOK: bytes(book)})), budget()
        )


def test_tertiary_display_changes_fail_identity_and_dedup_stays_excluded():
    source = read_compound(str(EXTENDED / "28774.xls"))
    before = inspect_art(source, budget())
    book, at = tertiary_book(source)
    book[at + 10] ^= 1  # Another valid fixed-width value, different display state.
    after = inspect_art(
        CompoundFile(container(source, {**source.streams, WORKBOOK: bytes(book)})), budget()
    )
    assert not equal_art(before, after)
    with pytest.raises(ValueError, match="secondary/private"):
        inspect_dedup(source, budget())


def test_worksheet_drawing_records_share_the_cumulative_root_budget():
    leaf = struct.pack("<HHI", 2, 0xF00A, 8) + b"\0" * 8
    drawing = struct.pack("<HHI", 15, 0xF002, len(leaf) * 100) + leaf * 100
    bounds = Budget(FormatLimits(nodes=105))
    bounds.consume(nodes=5)  # Other host/store records already inspected.
    with pytest.raises(FormatLimit, match="cumulative.*record budget"):
        worksheet_drawing([drawing], Parser(bounds))


@pytest.mark.parametrize(
    "name,reason",
    (("DrawingContinue.xls", "0x87c"),
     ("FloatingPictures.doc", "unsupported Word property: 0x484b")),
)
def test_original_unknown_host_families_remain_rejected(name, reason):
    with pytest.raises(ValueError, match=reason):
        inspect_art(read_compound(str(EXTENDED / name)), budget())
