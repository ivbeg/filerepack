"""Notes graph, bounded shared Pictures and independently checked byte mutations."""

import io
import struct

import pytest

from filerepack import FileRepacker, RepackOptions, ole
from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_records import inspect_records
from filerepack.ole_raster import PngIdentity
from filerepack.ole_verify import CompoundFile, independent_manifest, read_compound
from filerepack.verification import verify_preservation
from test.ole_fixtures import CORPUS, compound_bytes
from test.ole_ppt_notes_fixtures import presentation, record
from test.test_ole import native_writer as _native_writer

native_writer = _native_writer
DOCUMENT, PICTURES = ("PowerPoint Document",), ("Pictures",)


def budget(**limits):
    return Budget(FormatLimits(**limits))


@pytest.mark.parametrize("notes,legacy", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("embedded", [False, True])
def test_notes_and_master_objects_are_immutable_while_shared_pngs_shrink(notes, legacy, embedded):
    source = presentation(notes=notes, legacy=legacy, embedded=embedded)
    before = inspect_art(source, budget())
    assert len(before.rasters) == 2
    assert all(isinstance(r.raster.parsed, PngIdentity) for r in before.rasters)
    replacements, details = before.reencode(budget())
    streams = {**source.streams, **replacements}
    after = inspect_art(CompoundFile(compound_bytes(streams)), budget())
    assert equal_art(before, after) and details["recompressed_rasters"] == 2
    assert equal_art(before.identity(), after)
    assert len(streams[PICTURES]) < len(source.streams[PICTURES])
    assert streams[("Current User",)] == source.streams[("Current User",)]
    records = read_records(source.streams[DOCUMENT])
    for pos, item in records.items():
        if item.kind in (1008, 4113):
            end = pos + 8 + item.size
            assert streams[DOCUMENT][pos:end] == source.streams[DOCUMENT][pos:end]
    if embedded:
        with pytest.raises(ValueError):
            inspect_records(source, budget())


@pytest.mark.parametrize(
    "fault",
    [
        "notes-id",
        "reverse-id",
        "master-id",
        "master-fields",
        "master-flags",
        "notes-version",
        "color-instance",
        "drawing-instance",
        "notes-target",
        "slide-master-id",
        "notes-list-instance",
        "shared-count",
        "consumer-index",
        "consumer-flag",
        "fbse-uid",
        "fbse-size",
        "fbse-delay",
        "storage-identity",
        "object-type",
        "unknown-record",
        "wrong-owner",
    ],
)
def test_bad_graphs_and_picture_ownership_fail_closed(fault):
    source = presentation(legacy=True)
    data = bytearray(source.streams[DOCUMENT])
    records = read_records(data)

    def find(kind):
        return sorted(p for p, r in records.items() if r.kind == kind)

    master, note = find(1009)
    slide = next(p for p in find(1007) if records[records[p].parent].kind == 1006)
    if fault == "notes-id":
        struct.pack_into("<I", data, slide + 24, 999)
    elif fault == "reverse-id":
        struct.pack_into("<I", data, note + 8, 999)
    elif fault == "master-id":
        struct.pack_into("<I", data, find(1001)[0] + 32, 5)
    elif fault == "master-fields":
        struct.pack_into("<I", data, master + 8, 256)
    elif fault == "master-flags":
        struct.pack_into("<H", data, master + 12, 3)
    elif fault == "notes-version":
        struct.pack_into("<H", data, note, 0)
    elif fault in ("color-instance", "drawing-instance"):
        kind = 2032 if fault == "color-instance" else 1036
        pos = next(p for p in find(kind) if records[records[p].parent].kind == 1008)
        struct.pack_into("<H", data, pos, 0 if kind == 2032 else 31)
    elif fault == "notes-target":
        persist = next(p for p in find(1011) if records[records[p].parent].flags == 47)
        struct.pack_into("<I", data, persist + 8, 5)
    elif fault == "slide-master-id":
        struct.pack_into("<I", data, slide + 20, 0x80000002)
    elif fault == "notes-list-instance":
        pos = next(p for p in find(4080) if records[p].flags == 47)
        struct.pack_into("<H", data, pos, 63)
    elif fault.startswith("fbse") or fault == "shared-count":
        pos = find(0xF007)[0]
        offset = {"fbse-uid": 10, "fbse-size": 28, "fbse-delay": 36, "shared-count": 32}[fault]
        data[pos + offset] ^= 1
    elif fault.startswith("consumer"):
        pos = find(0xF00B)[0]
        struct.pack_into(
            "<I" if fault == "consumer-index" else "<H",
            data,
            pos + (10 if fault == "consumer-index" else 8),
            99 if fault == "consumer-index" else 0x104,
        )
    elif fault in ("storage-identity", "object-type"):
        pos = find(4035)[0]
        struct.pack_into("<I", data, pos + (16 if fault == "storage-identity" else 12), 99)
    else:
        struct.pack_into("<H", data, note + 2, 9999 if fault == "unknown-record" else 1052)
    changed = CompoundFile(compound_bytes({**source.streams, DOCUMENT: bytes(data)}))
    with pytest.raises(ValueError):
        inspect_art(changed, budget())


@pytest.mark.parametrize("kind", [1009, 4035, 4113, 0xF00B, 0xF007, 4085])
def test_verifier_rejects_changes_outside_exact_write_mask(kind):
    source = presentation(legacy=True)
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    identity = before.identity()
    del before
    data = bytearray(replacements[DOCUMENT])
    records = read_records(data)
    pos = next(p for p, r in records.items() if r.kind == kind)
    # Change opaque/reserved content where possible, so equality (not solely
    # structural rejection) is exercised for NotesAtom, wrappers and edit data.
    offset = {1009: 14, 4035: 28, 4113: 16, 0xF00B: 8, 0xF007: 26, 4085: 8}[kind]
    data[pos + offset] ^= 1
    mutated = CompoundFile(
        compound_bytes({**source.streams, **replacements, DOCUMENT: bytes(data)})
    )
    try:
        after = inspect_art(mutated, budget())
    except ValueError:
        return
    assert not equal_art(identity, after)


def test_unselected_picture_bytes_and_selection_are_exact():
    source = presentation()
    # First PNG needs 8224 sample bytes; second needs 2064. The larger first
    # image stays untouched, while the second fits this test's small allowance.
    def limited():
        return budget(decoded=4096 * 5)

    before = inspect_art(source, limited())
    assert len(before.rasters) == 1 and len(before.raster_skips) == 1
    replacements, _ = before.reencode(limited())
    first_size = 8 + struct.unpack_from("<I", source.streams[PICTURES], 4)[0]
    assert replacements[PICTURES][:first_size] == source.streams[PICTURES][:first_size]
    after = inspect_art(CompoundFile(compound_bytes({**source.streams, **replacements})), limited())
    assert equal_art(before, after)
    changed = bytearray(replacements[PICTURES])
    changed[8] ^= 1
    # Make matching BStore UID also change: valid ownership still cannot hide
    # an unintended mutation to the unselected BLIP.
    document = bytearray(replacements[DOCUMENT])
    pos = min(p for p, r in read_records(document).items() if r.kind == 0xF007)
    document[pos + 10] ^= 1
    altered = inspect_art(
        CompoundFile(
            compound_bytes({**source.streams, DOCUMENT: bytes(document), PICTURES: bytes(changed)})
        ),
        limited(),
    )
    assert not equal_art(before, altered)


def test_root_decoded_budget_is_not_swallowed():
    with pytest.raises(FormatLimit):
        inspect_art(presentation(), budget(decoded=8192))


@pytest.mark.parametrize("notes", [False, True])
def test_legacy_ppt_jpeg_codec_remains_qualified_and_notes_profile_retains_jpeg(notes):
    from test.test_ole_raster import png

    workbook = inspect_art(read_compound(str(CORPUS / "SimpleWithImages.xls")), budget())
    jpeg = next(r.raster for r in workbook.rasters if r.kind == 0xF01D)
    source = presentation(notes=notes, images=[bytes(jpeg.encoded), png()])
    before = inspect_art(source, budget())
    assert len(before.rasters) == (1 if notes else 2)
    assert any(r.kind == 0xF01D for r in before.rasters) is not notes
    replacements, _ = before.reencode(budget())
    after = inspect_art(CompoundFile(compound_bytes({**source.streams, **replacements})), budget())
    assert equal_art(before, after)
    if notes:
        size = 8 + struct.unpack_from("<I", source.streams[PICTURES], 4)[0]
        assert replacements[PICTURES][:size] == source.streams[PICTURES][:size]


def tag(name, blob):
    return record(15, 5002, record(0, 4026, name.encode("utf-16le")) + record(0, 5003, blob))


@pytest.mark.parametrize("name", ["___PPT9", "___PPT10", "___PPT12"])
def test_audited_programmable_document_tags_are_retained(name):
    blob = {
        "___PPT9": record(47, 4040, record(48, 4050, b"\0" * 4)),
        "___PPT10": record(0, 1037, b"\0" * 8),
        "___PPT12": record(0, 1061, b"\0"),
    }[name]
    source = presentation(document_info=record(15, 5000, tag(name, blob)))
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    after = inspect_art(CompoundFile(compound_bytes({**source.streams, **replacements})), budget())
    assert equal_art(before, after)
    assert tag(name, blob) in replacements[DOCUMENT]


@pytest.mark.parametrize(
    "fault", ["name", "record", "version", "owner", "length", "duplicate", "unowned"]
)
def test_unqualified_programmable_tags_fail_closed(fault):
    name = "___BAD10" if fault == "name" else "___PPT10"
    kind = {"record": 9999, "owner": 12011}.get(fault, 1037)
    blob = record(1 if fault == "version" else 0, kind, b"\0" * 8)
    if fault == "length":
        blob = blob[:-1]
    content = tag(name, blob)
    if fault == "duplicate":
        content += content
    if fault != "unowned":
        content = record(15, 5000, content)
    source = presentation(document_info=content)
    with pytest.raises(ValueError):
        inspect_art(source, budget())


def test_notes_recompression_without_sector_gain_retains_strict_compaction(tmp_path, native_writer):
    from filerepack.ole_recompress import operate

    original = presentation(legacy=True)
    replacements, _ = inspect_art(original, budget()).reencode(budget())
    source = tmp_path / "already-compressed.ppt"
    source.write_bytes(compound_bytes({**original.streams, **replacements}))
    raw = source.read_bytes()
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()
    info = operate(
        "ppt-ole", "rewrite", str(source), str(candidate), {"ole_writer": native_writer}, budget()
    )
    assert info["verify"] == "ole" and info["details"]["additional_savings_bytes"] == 0
    assert verify_preservation(str(source), str(candidate), "ole")
    assert source.read_bytes() == raw


@pytest.mark.parametrize("extension", ["ppt", "pot", "pps"])
def test_native_notes_aliases_dryrun_and_independent_verification(
    tmp_path, native_writer, extension
):
    original = presentation(legacy=True)
    source = tmp_path / ("source." + extension)
    source.write_bytes(original.data)
    raw = source.read_bytes()
    result = ole.pack_ole(str(source), ole_recompress=True, dryrun=True)
    assert not result.replaced and result.details["strategy"] == "ole-officeart-recompression"
    assert source.read_bytes() == raw
    candidate = tmp_path / ("candidate." + extension)
    result = FileRepacker().repack(
        str(source), outfile=str(candidate), options=RepackOptions(ole_recompress=True)
    )
    assert result.results and candidate.stat().st_size < source.stat().st_size
    assert source.read_bytes() == raw
    assert verify_preservation(str(source), str(candidate), "officeart")
    assert not verify_preservation(str(source), str(candidate), "ole")


def test_combined_options_release_outer_source_during_content_encoding(
    tmp_path, native_writer, monkeypatch
):
    import gc
    import weakref

    from filerepack import ole_art_layout, ole_transform

    source = tmp_path / "notes.ppt"
    source.write_bytes(presentation(legacy=True).data)
    raw = source.read_bytes()
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()
    read, rewrite = ole_transform._read, ole_transform._rewrite_all
    additional, reencode = ole_transform._additional, ole_art_layout.ArtLayout.reencode
    references = []

    def tracked_read(*args):
        parsed = read(*args)
        references.append(weakref.ref(parsed))
        return parsed

    def checked_rewrite(*args, **kwargs):
        gc.collect()
        assert references[0]() is None, "Outer source remains resident during PNG encoding"
        return rewrite(*args, **kwargs)

    def checked_additional(*args):
        references.append(weakref.ref(args[4]))
        return additional(*args)

    def checked_reencode(*args, **kwargs):
        gc.collect()
        assert all(ref() is None for ref in references), "Source carrier remains resident"
        return reencode(*args, **kwargs)

    monkeypatch.setattr(ole_transform, "_read", tracked_read)
    monkeypatch.setattr(ole_transform, "_rewrite_all", checked_rewrite)
    monkeypatch.setattr(ole_transform, "_additional", checked_additional)
    monkeypatch.setattr(ole_art_layout.ArtLayout, "reencode", checked_reencode)
    info = ole_transform.rewrite(
        str(source),
        str(candidate),
        {
            "ole_writer": native_writer,
            "ole_recompress": True,
            "ole_embedded_recompress": True,
            "ole_deduplicate_images": True,
        },
        budget(),
    )
    assert info["verify"] == "officeart"
    assert "DOC/XLS host" in info["details"]["embedded_skip"]
    assert "1008" in info["details"]["deduplication_skip"]
    assert len(references) == 2
    assert verify_preservation(str(source), str(candidate), "officeart")
    assert source.read_bytes() == raw


def test_combined_options_recheck_source_manifest_between_passes(
    tmp_path, native_writer, monkeypatch
):
    from filerepack import ole_transform

    source = tmp_path / "notes.ppt"
    source.write_bytes(presentation(legacy=True).data)
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()
    read = ole_transform._read

    def changed_source_after_first_read(*args):
        parsed = read(*args)
        source.write_bytes(compound_bytes({**parsed.streams, ("unrelated",): b"changed"}))
        return parsed

    monkeypatch.setattr(ole_transform, "_read", changed_source_after_first_read)
    with pytest.raises(ValueError, match="source changed between"):
        ole_transform.rewrite(
            str(source),
            str(candidate),
            {"ole_writer": native_writer, "ole_recompress": True},
            budget(),
        )


def test_large_independent_fat_reader_does_not_trust_strict_reader(monkeypatch):
    import olefile

    raw = compound_bytes({("large",): b"exact" * 250000})
    original = CompoundFile(raw)
    assert independent_manifest(io.BytesIO(raw), original) == original.manifest
    getsect = olefile.OleFileIO.getsect

    def different(reader, sector):
        data = getsect(reader, sector)
        return b"X" + data[1:] if data.startswith(b"exact") else data

    monkeypatch.setattr(olefile.OleFileIO, "getsect", different)
    with pytest.raises(ValueError, match="independent stream bytes"):
        independent_manifest(io.BytesIO(raw), original)


@pytest.mark.parametrize("fault", ["early-end", "cycle", "bounds", "late-end"])
def test_large_independent_fat_chain_is_fully_checked(monkeypatch, fault):
    import olefile

    raw = compound_bytes({("large",): b"exact" * 250000})
    original = CompoundFile(raw)
    listdir = olefile.OleFileIO.listdir

    def different(reader, *args, **kwargs):
        result = listdir(reader, *args, **kwargs)
        start = reader.direntries[reader._find(["large"])].isectStart
        if fault == "late-end":
            sector = start
            while reader.fat[sector] != 0xFFFFFFFE:
                sector = reader.fat[sector]
            reader.fat[sector] = start
        else:
            reader.fat[start] = {
                "early-end": 0xFFFFFFFE,
                "cycle": start,
                "bounds": len(reader.fat),
            }[fault]
        return result

    monkeypatch.setattr(olefile.OleFileIO, "listdir", different)
    with pytest.raises(ValueError, match="independent.*(FAT|chain)"):
        independent_manifest(io.BytesIO(raw), original)


def test_root_view_patches_split_reads_only_and_preserves_reader_position():
    from filerepack.ole_root import root_name_view
    from test.test_ole import legacy_root

    canonical = presentation().data
    original = legacy_root(canonical)
    source = io.BytesIO(original)
    source.seek(37)
    offset = (struct.unpack_from("<I", original, 48)[0] + 1) * 512
    with root_name_view(source) as view:
        view.seek(offset - 7)
        pieces = [view.read(n) for n in (8, 5, 28, 16, 9, 12)]
        assert b"".join(pieces) == canonical[offset - 7 : offset - 7 + sum((8, 5, 28, 16, 9, 12))]
    assert source.tell() == 37 and source.getvalue() == original
