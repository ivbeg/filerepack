"""DOC refiltering controls include exact samples, history and live consumers."""

import struct
import zlib
from pathlib import Path

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.format_support import FormatLimit, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_officeart import MAX_TOTAL, Parser, header
from filerepack.ole_raster import PngIdentity, png_data
from filerepack.ole_verify import CompoundFile, read_compound
from filerepack.verification import preservation_equal
from test.ole_art_fixtures import DATA, WORD, container, control
from test.ole_fixtures import CORPUS
from test.test_ole import native_writer as _native_writer
from test.test_ole_png_refilter import budget, fake_encoder, filtered_png
from test.test_ole_raster import png

native_writer = _native_writer


def word_png(data, *, floating=False, history=False):
    source = read_compound(str(CORPUS / "PngPicture.doc")) if floating else \
        control("vector_image.doc")
    layout = inspect_art(source, budget())
    if floating:
        record = layout.rasters[0]
        replacements = layout.adapter.rebuild({id(record): data})
    else:
        start, prefix, records = layout.adapter.blocks[0]
        uid = layout.metafiles[0].body[:16]
        blip = header(0x6E00, 0xF01E, uid + b"\xff" + data)
        fbse = bytearray(records[1].body[:36])
        fbse[:2] = b"\x06\x06"
        struct.pack_into("<I", fbse, 20, len(blip))
        shape = records[0].original()
        body = shape + header(0x62, 0xF007, bytes(fbse) + blip)
        framed = bytearray(prefix)
        struct.pack_into("<I", framed, 0, len(framed) + len(body))
        previous_size = struct.unpack_from("<I", source.streams[DATA], start)[0]
        opaque = source.streams[DATA][start : start + previous_size] if history else b""
        word = bytearray(source.streams[WORD])
        for field in layout.adapter.refs:
            struct.pack_into("<I", word, field, len(opaque))
        replacements = {WORD: bytes(word), DATA: opaque + framed + body + layout.adapter.padding}
    return CompoundFile(container(source, {**source.streams, **replacements}))


def rebuilt(source, layout, image):
    replacements = layout.adapter.rebuild({id(layout.rasters[0]): image})
    return CompoundFile(container(source, {**source.streams, **replacements}))


@pytest.mark.parametrize("floating", [False, True])
@pytest.mark.parametrize("color", [0, 2, 3, 4, 6])
def test_doc_different_filters_preserve_samples_metadata_and_picture_consumers(floating, color):
    original, _ = filtered_png(color, filtering=4)
    alternate, _ = filtered_png(color, filtering=1)
    alternate = png_data(alternate, budget()).rebuild(
        zlib.compress(png_data(alternate, budget()).raw, 9)
    )
    source = word_png(original, floating=floating, history=not floating)
    before = inspect_art(source, budget())
    assert isinstance(before.rasters[0].raster.parsed, PngIdentity)
    assert before.rasters[0].raster.parsed.refilter
    after = inspect_art(rebuilt(source, before, alternate), budget())
    assert equal_art(before.identity(), after)
    if not floating:
        assert before.adapter.blocks[0][1] == after.adapter.blocks[0][1]
        # A retained leading block fixes this picture's start; only its end moves.
        assert before.adapter.refs == after.adapter.refs
        assert len(after.adapter.data) < len(before.adapter.data)


@pytest.mark.parametrize("floating", [False, True])
@pytest.mark.parametrize("fault", ["sample", "hidden-rgb", "metadata", "palette", "depth"])
def test_doc_final_verification_rejects_sample_and_metadata_changes(floating, fault):
    original, _ = filtered_png(color=3 if fault == "palette" else 6, filtering=0)
    parsed = png_data(original, budget())
    if fault == "hidden-rgb":
        raw = bytearray(parsed.raw)
        raw[4] = 0
        original = parsed.rebuild(zlib.compress(raw, 0))
        parsed = png_data(original, budget())
    if fault in {"sample", "hidden-rgb"}:
        raw = bytearray(parsed.raw)
        raw[1] ^= 1
        changed = parsed.rebuild(zlib.compress(raw, 9))
    elif fault == "depth":
        changed = png(depth=16)
    else:
        chunks = list(parsed.chunks)
        index = next(i for i, (kind, _) in enumerate(chunks)
                     if kind == (b"PLTE" if fault == "palette" else b"tEXt"))
        kind, payload = chunks[index]
        chunks[index] = kind, bytes([payload[0] ^ 1]) + payload[1:]
        from filerepack.ole_raster import PngData

        changed = PngData(tuple(chunks), parsed.raw).rebuild(zlib.compress(parsed.raw, 9))
    source = word_png(original, floating=floating)
    before = inspect_art(source, budget())
    after = inspect_art(rebuilt(source, before, changed), budget())
    assert not equal_art(before.identity(), after)


@pytest.mark.parametrize("floating", [False, True])
def test_doc_encoder_uses_verified_refiltered_idat_and_preserves_history(monkeypatch, floating):
    original, _ = filtered_png(filtering=0)
    alternate, _ = filtered_png(filtering=4)
    alternate = png_data(alternate, budget()).rebuild(
        zlib.compress(png_data(alternate, budget()).raw, 9)
    )
    monkeypatch.setattr("filerepack.ole_officeart._zopfli", lambda: None)
    monkeypatch.setattr("filerepack.tools.resolve_tool", lambda _: "test-tool")
    fake_encoder(monkeypatch, alternate)
    source = word_png(original, floating=floating, history=not floating)
    before = inspect_art(source, budget())
    replacements, details = before.reencode(budget())
    assert details["raster_encoders"] == ["png-oxipng10.2.0"]
    candidate = CompoundFile(container(source, {**source.streams, **replacements}))
    after = inspect_art(candidate, budget())
    assert equal_art(before, after)
    if not floating:
        assert before.adapter.blocks[0][1] == after.adapter.blocks[0][1]


@pytest.mark.parametrize("depth,interlace", [(16, 0), (8, 1), (1, 0)])
def test_doc_other_png_layouts_keep_exact_filtered_contract(depth, interlace):
    source = word_png(png(depth=depth, color=0, interlace=interlace))
    image = inspect_art(source, budget()).rasters[0].raster
    assert isinstance(image.parsed, PngIdentity) and not image.parsed.refilter


def test_doc_root_reservation_and_existing_aggregate_bound_retain_unselected_bytes():
    parser = Parser(budget(decoded=4096 * 5), bounded_png=True, word_properties=True)
    assert parser.png_allowance == 4096
    first = header(0x6E00, 0xF01E, b"u" * 16 + b"\xff" + png())
    second = header(0x6E00, 0xF01E, b"v" * 16 + b"\xff" + png(width=16))
    records = parser.sequence(first + second)
    assert records[0].original() == first and records[0].raster is None
    assert len(parser.rasters) == 1 and parser.raster_skips
    assert Parser(budget(), bounded_png=True, word_properties=True).png_allowance == MAX_TOTAL
    assert Parser(budget(), bounded_png=True).png_allowance == FormatLimits().decoded // 5
    with pytest.raises(FormatLimit):
        Parser(budget(decoded=8192), bounded_png=True, word_properties=True).sequence(first)


def test_doc_public_output_and_dryrun_keep_sources_exact(native_writer, tmp_path, monkeypatch):
    monkeypatch.setenv("FILEREPACK_OLE_COMPACTOR", native_writer)
    source = tmp_path / "original.doc"
    output = tmp_path / "refiltered.doc"
    data, _ = filtered_png(filtering=0)
    source.write_bytes(word_png(data, history=True).data)
    original = source.read_bytes()
    options = RepackOptions(ole_recompress=True)
    result = FileRepacker().repack(str(source), outfile=str(output), options=options).results[0]
    assert result.details["strategy"] == "ole-officeart-recompression"
    assert output.stat().st_size < source.stat().st_size
    assert preservation_equal(str(source), str(output), "officeart")
    assert source.read_bytes() == original
    prediction = FileRepacker().repack(
        str(source), options=RepackOptions(ole_recompress=True, dryrun=True)
    ).results[0]
    assert prediction.outsize < prediction.insize and source.read_bytes() == original
    assert not list(Path(tmp_path).glob("*.tmp"))
