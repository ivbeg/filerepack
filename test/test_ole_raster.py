"""Real-image coefficient checks and independently constructed PNG controls."""

import struct
import zlib

import pytest

from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_officeart import encode_metafiles, header
from filerepack.ole_raster import PNG, chunk, jpeg_data, optimize_jpeg, optimize_png, png_data
from filerepack.ole_verify import CompoundFile, read_compound
from test.ole_art_fixtures import container
from test.ole_fixtures import CORPUS


def budget(**limits):
    return Budget(FormatLimits(**limits))


def png(depth=8, color=6, width=64, height=32, interlace=0):
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    if interlace:
        passes = [
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        ]
    else:
        passes = [(0, 0, 1, 1)]
    raw = bytearray()
    for x, y, sx, sy in passes:
        w, h = max(0, (width - x + sx - 1) // sx), max(0, (height - y + sy - 1) // sy)
        if w and h:
            raw.extend((b"\0" + b"\0" * ((w * channels * depth + 7) // 8)) * h)
    data = PNG + chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, interlace)
    )
    if color == 3:
        data += chunk(b"PLTE", b"\0\0\0\xff\xff\xff") + chunk(b"tRNS", b"\0\xff")
    data += chunk(b"tEXt", b"Author\0Preserved")
    encoded = zlib.compress(bytes(raw), 0)
    data += chunk(b"IDAT", encoded[:10]) + chunk(b"IDAT", encoded[10:])
    return data + chunk(b"IEND", b"")


@pytest.mark.parametrize(
    "depth,color", [(1, 0), (8, 0), (16, 0), (8, 2), (16, 2), (1, 3), (8, 3), (8, 4), (16, 6)]
)
@pytest.mark.parametrize("interlace", [0, 1])
def test_png_exact_samples_chunks_and_smaller_representation(depth, color, interlace):
    original = png(depth, color, interlace=interlace)
    before = png_data(original, budget())
    candidate, encoder = optimize_png(original, before, budget())
    assert encoder == "png-zlib9" and len(candidate) < len(original)
    assert before.fingerprint() == png_data(candidate, budget()).fingerprint()


@pytest.mark.parametrize("fault", ["crc", "trailing", "unsafe", "apng", "sample-size", "filter"])
def test_png_malformed_and_unqualified_inputs(fault):
    data = png()
    if fault == "crc":
        data = data[:-1] + bytes([data[-1] ^ 1])
    elif fault == "trailing":
        data += b"junk"
    elif fault in ("unsafe", "apng"):
        data = data[:-12] + chunk(b"aaAA" if fault == "unsafe" else b"acTL", b"\0" * 8) + data[-12:]
    else:
        parsed = png_data(data, budget())
        raw = parsed.raw[:-1] if fault == "sample-size" else b"\xff" + parsed.raw[1:]
        data = parsed.rebuild(zlib.compress(raw))
    with pytest.raises(ValueError):
        png_data(data, budget())


def test_png_budget_is_cumulative_and_enforced():
    data = png()
    with pytest.raises(FormatLimit):
        png_data(data, budget(decoded=64))


def test_real_jpeg_optimizer_has_exact_coefficients_and_metadata():
    original = inspect_art(read_compound(str(CORPUS / "SimpleWithImages.xls")), budget())
    records = [r for r in original.rasters if r.kind == 0xF01D]
    assert records
    image = records[0].raster
    before = jpeg_data(image.encoded, budget())
    candidate, _ = optimize_jpeg(image.encoded, before, budget())
    assert len(candidate) <= len(image.encoded)
    assert jpeg_data(candidate, budget()).fingerprint() == before.fingerprint()
    changed = image.encoded.replace(b"JFIF", b"JFIX", 1)
    assert changed != image.encoded
    assert jpeg_data(changed, budget()).fingerprint() != before.fingerprint()


def test_png_only_host_recompression_and_identity_rejection():
    original = read_compound(str(CORPUS / "vector_image.doc"))
    layout = inspect_art(original, budget())
    record = layout.metafiles[0]
    raster = header(0x6E00, 0xF01E, record.body[:16] + b"\xff" + png())
    # Independent fixture construction replaces its one inline FBSE's image kind.
    from dataclasses import replace

    block = layout.adapter.blocks[0]
    fbse = block[2][1]
    prefix = bytearray(fbse.body[:36])
    prefix[:2] = b"\x06\x06"
    struct.pack_into("<I", prefix, 20, len(raster))
    changed = replace(fbse, flags=0x62, body=bytes(prefix) + raster, children=())
    shape = block[2][0].original()
    picf = bytearray(block[1])
    struct.pack_into("<I", picf, 0, len(picf) + len(shape) + len(changed.original()))
    streams = dict(original.streams)
    streams[("Data",)] = bytes(picf) + shape + changed.original() + layout.adapter.padding
    source = CompoundFile(container(original, streams))
    before = inspect_art(source, budget())
    assert not before.metafiles and len(before.rasters) == 1
    replacements, diagnostics = before.reencode(budget())
    after = inspect_art(CompoundFile(container(source, {**streams, **replacements})), budget())
    assert equal_art(before, after) and diagnostics["recompressed_rasters"] == 1
    assert len(replacements[("Data",)]) < len(streams[("Data",)])


def test_maximum_keeps_default_and_original_when_more_iterations_are_worse(monkeypatch):
    import filerepack.ole_officeart as codec

    original = inspect_art(read_compound(str(CORPUS / "vector_image.doc")), budget())
    calls = []

    def stronger(raw, numiterations):
        calls.append(numiterations)
        return zlib.compress(raw, 9 if numiterations == 15 else 0)

    monkeypatch.setattr(codec, "_zopfli", lambda: stronger)
    default, _ = encode_metafiles(original.metafiles, budget())
    maximum, _ = encode_metafiles(original.metafiles, budget(), ultra=True)
    assert calls == [15, 15, 50] and maximum == default


def test_parent_disables_all_picture_optimization():
    with pytest.raises(ValueError, match="disables"):
        inspect_art(read_compound(str(CORPUS / "vector_image.doc")), budget(), pack_images=False)


@pytest.mark.parametrize(
    "size,expected", [(1048576, [15, 50]), (1048577, [50]), (2097152, [50]), (2097153, [])]
)
def test_maximum_effort_exact_size_cutoffs(monkeypatch, size, expected):
    from dataclasses import replace
    import filerepack.ole_officeart as codec

    record = inspect_art(read_compound(str(CORPUS / "vector_image.doc")), budget()).metafiles[0]
    raw = b"fixed bytes" * (size // 11) + b"x" * (size % 11)
    meta = replace(record.metafile, raw=raw, encoded=zlib.compress(raw, 0))
    record = replace(record, metafile=meta)
    calls = []

    def compress(data, numiterations):
        calls.append(numiterations)
        return zlib.compress(data, 9)

    monkeypatch.setattr(codec, "_zopfli", lambda: compress)
    encode_metafiles([record], budget(), ultra=True)
    assert calls == expected


def test_missing_optional_jpegtran_keeps_original(monkeypatch):
    import filerepack.tools as tools

    records = inspect_art(read_compound(str(CORPUS / "SimpleWithImages.xls")), budget()).rasters
    image = next(r.raster for r in records if r.kind == 0xF01D)
    monkeypatch.setattr(tools, "resolve_tool", lambda key: None)
    encoded, reason = optimize_jpeg(image.encoded, jpeg_data(image.encoded, budget()), budget())
    assert encoded == image.encoded and "unavailable" in reason
