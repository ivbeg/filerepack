"""Independent preservation/fault qualification for the approved OLE portfolio."""

import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import zipfile
import zlib
from dataclasses import replace

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole import inspect_ole, pack_ole
from filerepack.ole_dedup import inspect_dedup
from filerepack.ole_embedded import compare, native_wrapper, optimize, scopes
from filerepack.ole_hwp import decode_stream, inspect_hwp
from filerepack.ole_recompress import planned_native
from filerepack.ole_verify import CompoundFile, ole_fingerprint, read_compound
from test.ole_art_fixtures import BOOK, DOCUMENT, PICTURES, container, control, envelope
from test.ole_fixtures import ADDITIONAL_ART_ORIGINALS, CORPUS

EXTENDED = CORPUS.parent / "ole_extended"
HOSTS = (
    "attachment_test_msg.msg",
    "Test_Visio-Some_Random_Text.vsd",
    "Sample.pub",
    "TestZeroLengthCodePage.mpp",
    "SimpleComponent.msi",
    "sample-5017-pics.hwp",
)


def budget(**kwargs):
    return Budget(FormatLimits(**kwargs))


@pytest.fixture
def native_writer(monkeypatch):
    writer = os.environ.get("FILEREPACK_OLE_COMPACTOR") or shutil.which("filerepack-ole")
    if not writer:
        pytest.skip("native OLE helper is required")
    monkeypatch.setenv("FILEREPACK_OLE_COMPACTOR", writer)
    return writer


def test_extended_corpus_provenance():
    for entry in json.loads((EXTENDED / "provenance.json").read_text())["files"]:
        data = (EXTENDED / entry["name"]).read_bytes()
        assert (len(data), hashlib.sha256(data).hexdigest()) == (entry["bytes"], entry["sha256"])
        if "git_blob_sha1" in entry:
            blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
            assert hashlib.sha1(blob).hexdigest() == entry["git_blob_sha1"]


@pytest.mark.parametrize("name", ADDITIONAL_ART_ORIGINALS)
def test_additional_originals_public_output_preserves_complete_manifest(
    tmp_path, native_writer, name
):
    from filerepack.ole_art_layout import equal_art, inspect_art

    source, target = tmp_path / name, tmp_path / ("selected-" + name)
    data = (EXTENDED / name).read_bytes()
    source.write_bytes(data)
    FileRepacker().repack(
        str(source), outfile=str(target), options=RepackOptions(ole_recompress=True)
    )
    assert source.read_bytes() == data and target.stat().st_size <= len(data)
    assert equal_art(
        inspect_art(read_compound(str(source)), budget()),
        inspect_art(read_compound(str(target)), budget()),
    )


@pytest.mark.parametrize(
    "name",
    (
        "0113-doc.doc",
        "0670-doc.doc",
        "0771-doc.doc",
        "1825-doc.doc",
        "4128-doc.doc",
    ),
)
def test_napierone_small_doc_originals_save_beyond_strict_compaction(
    tmp_path, native_writer, name
):
    from filerepack.verification import preservation_equal

    source = tmp_path / name
    compacted = tmp_path / ("compacted-" + name)
    target = tmp_path / ("optimized-" + name)
    source.write_bytes((EXTENDED / name).read_bytes())
    compacted.touch()
    subprocess.run(
        [native_writer, str(source), str(compacted)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    result = FileRepacker().repack(
        str(source), outfile=str(target), options=RepackOptions(ole_recompress=True)
    ).results[0]

    assert result.details["strategy"] == "ole-officeart-recompression"
    assert target.stat().st_size < compacted.stat().st_size
    assert preservation_equal(str(source), str(target), "officeart")


def test_tika_original_doc_png_recompression_saves_file_sectors(
    tmp_path, native_writer
):
    from filerepack.verification import preservation_equal

    name = "testControlCharacters.doc"
    original = EXTENDED / name
    source, target = tmp_path / name, tmp_path / ("selected-" + name)
    data = original.read_bytes()
    source.write_bytes(data)
    result = FileRepacker().repack(
        str(source), outfile=str(target), options=RepackOptions(ole_recompress=True)
    ).results[0]

    assert source.read_bytes() == data
    assert result.details["strategy"] == "ole-officeart-recompression"
    assert result.details["officeart"]["recompressed_rasters"] == 1
    assert target.stat().st_size < source.stat().st_size
    assert preservation_equal(str(source), str(target), "officeart")


def test_tika_empty_ppt_vba_atom_is_eligible_as_macro_free_host():
    inspection = inspect_ole(str(EXTENDED / "testPPT_2imgs.ppt"))
    assert inspection.eligible and inspection.profile == "ppt"
    assert not inspection.unsigned_vba


def test_tika_empty_ppt_vba_atom_reports_officeart_fallback(tmp_path, native_writer):
    name = "testPPT_2imgs.ppt"
    source, target = tmp_path / name, tmp_path / ("selected-" + name)
    original = (EXTENDED / name).read_bytes()
    source.write_bytes(original)
    result = FileRepacker().repack(
        str(source), outfile=str(target), options=RepackOptions(ole_recompress=True)
    ).results[0]

    assert source.read_bytes() == original
    assert result.details["strategy"] == "ole-compaction"
    assert result.details["officeart_skip"] == (
        "PPT OLE records: unqualified extension header/owner: 4082"
    )
    assert ole_fingerprint(str(source)) == ole_fingerprint(str(target))


def test_forbidden_style_location_uses_strict_fallback_and_reports_code(tmp_path, native_writer):
    from test.test_ole_host_coverage import inherited_word

    source = tmp_path / "invalid-style.doc"
    original = inherited_word(struct.pack("<HI", 0x6A03, 0))
    source.write_bytes(original.data)
    before = ole_fingerprint(str(source))
    result = FileRepacker().repack(
        str(source), options=RepackOptions(ole_recompress=True)
    ).results[0]
    assert result.details["strategy"] == "ole-compaction"
    assert "forbidden Word style property: 0x6a03" in result.details["officeart_skip"]
    assert ole_fingerprint(str(source)) == before


@pytest.mark.parametrize("name", HOSTS)
def test_new_hosts_original_and_free_sector_control(tmp_path, native_writer, name):
    original = read_compound(str(EXTENDED / name))
    path = tmp_path / name
    path.write_bytes(container(original, original.streams, free_sectors=80))
    expected = ole_fingerprint(str(path))
    assert inspect_ole(str(path)).eligible
    result = pack_ole(str(path))
    assert result.replaced and result.savings_bytes >= 80 * 512
    assert ole_fingerprint(str(path)) == expected
    shutil.copyfile(EXTENDED / name, path)
    expected = ole_fingerprint(str(path))
    result = pack_ole(str(path))
    assert result is not None and ole_fingerprint(str(path)) == expected


@pytest.mark.parametrize("name", HOSTS)
def test_new_strict_host_root_budget_preserves_source(tmp_path, native_writer, name):
    source = tmp_path / name
    original = (EXTENDED / name).read_bytes()
    source.write_bytes(original)
    result = pack_ole(str(source), format_max_nodes=1)
    assert not result.replaced and source.read_bytes() == original
    assert "budget" in result.reason.lower()
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("extension", ("msg", "vsd", "pub", "mpp", "msi", "hwp"))
def test_new_host_impostors_are_rejected(tmp_path, extension):
    path = tmp_path / ("renamed." + extension)
    shutil.copyfile(CORPUS / "simple.doc", path)
    assert not inspect_ole(str(path)).eligible


def weak_hwp():
    source = read_compound(str(EXTENDED / "sample-5017-pics.hwp"))
    layout = inspect_hwp(source, budget())
    streams = dict(source.streams)
    for path, raw in layout.decoded.items():
        encoder = zlib.compressobj(0, zlib.DEFLATED, -15)
        streams[path] = encoder.compress(raw) + encoder.flush() + layout.trailers[path]
    return CompoundFile(container(source, streams))


def test_hwp_exact_stream_identity_and_native_nested_paths(tmp_path, native_writer):
    source, candidate = tmp_path / "source.hwp", tmp_path / "candidate.hwp"
    original = weak_hwp()
    source.write_bytes(original.data)
    candidate.touch()
    bounds = budget()
    before = inspect_hwp(original, bounds)
    replacements, details = before.reencode(bounds)
    assert details["recompressed_streams"] == 4
    after = planned_native(native_writer, str(source), str(candidate), "hwp", replacements, bounds)
    assert before.fingerprint() == inspect_hwp(after, bounds).fingerprint()
    assert len(after.data) < len(original.data)
    streams = dict(after.streams)
    raw = before.decoded["DocInfo",]
    encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
    changed = raw[:-1] + bytes([raw[-1] ^ 1])
    streams["DocInfo",] = encoder.compress(changed) + encoder.flush()
    assert (
        before.fingerprint()
        != inspect_hwp(CompoundFile(container(after, streams)), budget()).fingerprint()
    )


@pytest.mark.parametrize("fault", ("zlib-wrapper", "trailing", "concatenated", "crc", "size"))
def test_hwp_framing_faults(fault):
    encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = b"bounded data" * 100
    encoded = encoder.compress(raw) + encoder.flush()
    suffix = struct.pack("<II", zlib.crc32(raw), len(raw))
    bad = {
        "zlib-wrapper": zlib.compress(raw),
        "trailing": encoded + b"x",
        "concatenated": encoded + encoded,
        "crc": encoded + b"\0" * 8,
        "size": encoded + suffix[:-4] + struct.pack("<I", len(raw) + 1),
    }[fault]
    with pytest.raises(ValueError):
        decode_stream(bad, budget())
    assert decode_stream(encoded + suffix, budget()) == (raw, suffix)


@pytest.mark.parametrize("flag", (2, 4, 8, 16, 128, 256, 512, 1024, 8192, 1 << 18))
def test_hwp_protection_flags_fail_closed(tmp_path, flag):
    c = read_compound(str(EXTENDED / "sample-5017-pics.hwp"))
    streams = dict(c.streams)
    header = bytearray(streams["FileHeader",])
    struct.pack_into("<I", header, 36, 1 | flag)
    streams["FileHeader",] = bytes(header)
    path = tmp_path / "protected.hwp"
    path.write_bytes(container(c, streams))
    assert not inspect_ole(str(path)).eligible


def duplicate_xls():
    original = read_compound(str(CORPUS / "SimpleWithImages.xls"))
    layout = inspect_dedup(original, budget())
    entries = list(layout.store.children)
    entries[1] = entries[0]
    store = replace(layout.store, children=tuple(entries))
    group = replace(
        layout.adapter.group,
        children=tuple(store if c.kind == 0xF001 else c for c in layout.adapter.group.children),
    )
    streams = dict(original.streams)
    streams.update(replace(layout.adapter, group=group).rebuild({}))
    return CompoundFile(container(original, streams))


def duplicate_ppt():
    original = read_compound(str(CORPUS / "ole2-embedding-2003.ppt"))
    layout = inspect_dedup(original, budget())
    entries = list(layout.store.children)
    first = next(i for i, picture in enumerate(layout.images) if picture.kind)
    second = first + 1
    pic = layout.images[first].original()
    prefix = bytearray(entries[first].body)
    struct.pack_into("<I", prefix, 28, len(pic))
    entries[second] = replace(entries[first], body=bytes(prefix))
    body = b"".join(e.original() for e in entries)
    store = envelope(layout.store.flags, layout.store.kind, body)
    assert len(store) == layout.stop - layout.start
    streams = dict(original.streams)
    streams[DOCUMENT] = layout.data[: layout.start] + store + layout.data[layout.stop :]
    streams[PICTURES] = pic + pic
    return CompoundFile(container(original, streams))


@pytest.mark.parametrize("make,extension", ((duplicate_xls, "xls"), (duplicate_ppt, "ppt")))
def test_identical_store_dedup_and_wrong_valid_target_rejected(make, extension):
    original = make()
    before = inspect_dedup(original, budget())
    replacements, details = before.rebuild()
    assert details["removed_entries"] == 1
    streams = dict(original.streams)
    streams.update(replacements)
    candidate = CompoundFile(container(original, streams))
    after = inspect_dedup(candidate, budget())
    assert before.fingerprint() == after.fingerprint()
    assert len(after.images) == len(before.images) - 1
    if extension == "xls":
        fields = [at for at, index in after.consumers.items() if index in (0, 1)]
        a = next(at for at in fields if after.consumers[at] == 0)
        b = next(at for at in fields if after.consumers[at] == 1)
        data = bytearray(streams[BOOK])
        struct.pack_into("<I", data, a, 2)
        struct.pack_into("<I", data, b, 1)
        streams[BOOK] = bytes(data)
        fault = inspect_dedup(CompoundFile(container(candidate, streams)), budget())
        assert before.fingerprint() != fault.fingerprint()


@pytest.mark.parametrize("make,extension", ((duplicate_xls, "xls"), (duplicate_ppt, "ppt")))
@pytest.mark.parametrize("combined", [False, True])
def test_dedup_public_transaction(tmp_path, native_writer, make, extension, combined):
    source = tmp_path / ("document." + extension)
    original = make()
    source.write_bytes(original.data)
    result = pack_ole(
        str(source),
        ole_deduplicate_images=True,
        ole_recompress=combined,
        ole_embedded_recompress=combined,
    )
    assert result.replaced and result.details["deduplication"]["removed_entries"] == 1
    after = inspect_dedup(read_compound(str(source)), budget())
    if result.details["strategy"] == "ole-image-deduplication":
        assert inspect_dedup(original, budget()).fingerprint() == after.fingerprint()
        assert len(after.images) == len(inspect_dedup(original, budget()).images) - 1
    else:
        from filerepack.ole_ppt_records import equal_layouts, inspect_records

        assert combined and extension == "ppt"
        assert result.details["strategy"] == "ppt-ole-recompression"
        assert equal_layouts(
            inspect_records(original, budget()),
            inspect_records(read_compound(str(source)), budget()),
        )


def test_combined_options_keep_smaller_embedded_candidate(tmp_path, native_writer):
    original, _ = native_zip_parent()
    source, target = tmp_path / "parent.doc", tmp_path / "after.doc"
    source.write_bytes(original.data)
    options = {
        "ole_recompress": True,
        "ole_embedded_recompress": True,
        "ole_deduplicate_images": True,
    }
    result = FileRepacker().repack(
        str(source), outfile=str(target), options=RepackOptions(**options)
    ).results[0]
    assert result.details["strategy"] == "ole-embedded-recompression"
    assert target.stat().st_size < source.stat().st_size
    assert source.read_bytes() == original.data
    assert compare(
        str(source),
        original,
        str(target),
        read_compound(str(target)),
        native_writer,
        options,
        budget(),
    )


def native_zip_parent():
    source = read_compound(str(CORPUS / "word_with_embeded.doc"))
    _, objects = scopes(source, budget())
    scope = objects[-1]
    zip_data = io.BytesIO()
    with zipfile.ZipFile(
        zip_data, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=0
    ) as archive:
        info = zipfile.ZipInfo("payload.xml", (2020, 2, 3, 4, 5, 6))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.comment = b"private metadata"
        archive.writestr(info, b"<data>exact content</data>" * 1000, compresslevel=0)
        archive.comment = b"archive comment"
    payload = zip_data.getvalue()
    prefix = b"\2\0label\0C:\\escaped\\file.docx\0\0\0\3\0"
    command = b"C:\\escaped\\file.docx\0"
    body = prefix + struct.pack("<I", len(command)) + command + struct.pack("<I", len(payload))
    wrapper = struct.pack("<I", len(body) + len(payload) + 2) + body + payload + b"\0\0"
    streams = {p: v for p, v in source.streams.items() if p[: len(scope)] != scope}
    streams[scope + ("\x01Ole10Native",)] = wrapper
    streams[scope + ("\x01Ole",)] = bytes.fromhex("0100000200000000000000000000000000000000")
    streams[scope + ("\x01CompObj",)] = b"\0" * 28 + (struct.pack("<I", 8) + b"Package\0") * 3
    metadata = {
        e.path: (e.clsid, e.state, e.created, e.modified)
        for e in source.entries
        if e.kind != 5 and (e.path[: len(scope)] != scope or e.path == scope)
    }
    metadata[scope] = (bytes.fromhex("0c00030000000000c000000000000046"), 0, 0, 0)
    from test.ole_fixtures import compound_bytes

    return CompoundFile(compound_bytes(streams, storages=metadata)), scope


def test_wrapped_archive_exact_metadata_and_parent_verifier(tmp_path, native_writer):
    original, scope = native_zip_parent()
    source, target = tmp_path / "parent.doc", tmp_path / "after.doc"
    source.write_bytes(original.data)
    replacements, details = optimize(
        str(source), original, native_writer, {"pack_archives": True}, budget()
    )
    assert len(replacements) == 1
    target.touch()
    after = planned_native(
        native_writer, str(source), str(target), "doc-object", replacements, budget()
    )
    assert compare(str(source), original, str(target), after, native_writer, {}, budget())
    path = scope + ("\x01Ole10Native",)
    assert (
        native_wrapper(original.streams[path]).identity()
        == native_wrapper(after.streams[path]).identity()
    )
    streams = dict(after.streams)
    streams[scope + ("\x01CompObj",)] += b"fault"
    assert not compare(
        str(source),
        original,
        str(target),
        CompoundFile(container(after, streams)),
        native_writer,
        {},
        budget(),
    )
    unchanged, report = optimize(
        str(source), original, native_writer, {"pack_archives": False}, budget()
    )
    assert not unchanged


def test_direct_substorage_officeart_is_independently_verified(tmp_path, native_writer):
    original = read_compound(str(CORPUS / "word_with_embeded.doc"))
    child = control("SimpleWithImages.xls")
    scope = ("ObjectPool", "_1269427460")
    streams = {p: v for p, v in original.streams.items() if p[: len(scope)] != scope}
    streams.update({scope + p: v for p, v in child.streams.items()})
    parent = CompoundFile(container(original, streams))
    source, target = tmp_path / "parent.doc", tmp_path / "after.doc"
    source.write_bytes(parent.data)
    changes, details = optimize(
        str(source), parent, native_writer, {"ole_recompress": True}, budget()
    )
    assert changes and all(p[:2] == scope for p in changes)
    target.touch()
    after = planned_native(native_writer, str(source), str(target), "doc-object", changes, budget())
    assert compare(
        str(source), parent, str(target), after, native_writer, {"ole_recompress": True}, budget()
    )
    assert not compare(str(source), parent, str(target), after, native_writer, {}, budget())


def test_hwp_and_nested_root_budgets():
    with pytest.raises(FormatLimit):
        inspect_hwp(weak_hwp(), budget(decoded=100))
    parent, _ = native_zip_parent()
    from filerepack.ole_embedded import zip_identity

    wrapper = next(v for p, v in parent.streams.items() if p[-1] == "\x01Ole10Native")
    with pytest.raises(FormatLimit):
        zip_identity(native_wrapper(wrapper).payload, budget(decoded=100))


@pytest.mark.parametrize(
    "name,flag",
    (
        ("source.hwp", "ole_recompress"),
        ("source.xls", "ole_deduplicate_images"),
        ("source.doc", "ole_embedded_recompress"),
    ),
)
def test_new_modes_dryrun_and_output(tmp_path, native_writer, name, flag):
    data = (
        weak_hwp().data
        if name.endswith("hwp")
        else (duplicate_xls().data if name.endswith("xls") else native_zip_parent()[0].data)
    )
    source, output = tmp_path / name, tmp_path / ("out-" + name)
    source.write_bytes(data)
    result = FileRepacker().repack(str(source), options=RepackOptions(dryrun=True, **{flag: True}))
    assert source.read_bytes() == data and result.results and not result.results[0].replaced
    result = FileRepacker().repack(
        str(source), outfile=str(output), options=RepackOptions(**{flag: True})
    )
    assert source.read_bytes() == data and output.exists()
    assert result.results[0].savings_bytes > 0


@pytest.mark.parametrize("fault", ("length", "suffix", "class", "link", "zip-trailing"))
def test_wrapper_class_length_and_envelope_faults_keep_object(tmp_path, native_writer, fault):
    source, scope = native_zip_parent()
    streams = dict(source.streams)
    path = scope + ("\x01Ole10Native",)
    wrapper = bytearray(streams[path])
    if fault == "length":
        struct.pack_into("<I", wrapper, 0, len(wrapper))
    elif fault == "suffix":
        wrapper[-1] = 1
    elif fault == "zip-trailing":
        parsed = native_wrapper(bytes(wrapper))
        wrapper = bytearray(parsed.rebuild(parsed.payload + b"ignored trailer"))
    elif fault == "class":
        streams[scope + ("\x01CompObj",)] = b"not a Package"
    else:
        streams[scope + ("\x01Ole",)] = b"unknown linked object"
    streams[path] = bytes(wrapper)
    original = CompoundFile(container(source, streams))
    file = tmp_path / "source.doc"
    file.write_bytes(original.data)
    changes, report = optimize(str(file), original, native_writer, {}, budget())
    assert not changes and any(r.get("skip") for r in report["objects"])


def test_recursive_serialized_cfb_and_cumulative_depth(tmp_path, native_writer):
    original, scope = native_zip_parent()
    # The child is itself a qualified DOC containing a weak ZIP Package.
    streams = dict(original.streams)
    path = scope + ("\x01Ole10Native",)
    parsed = native_wrapper(streams[path])
    streams[path] = parsed.rebuild(original.data)
    parent = CompoundFile(container(original, streams))
    source, target = tmp_path / "recursive.doc", tmp_path / "candidate.doc"
    source.write_bytes(parent.data)
    target.touch()
    changes, report = optimize(str(source), parent, native_writer, {}, budget())
    assert path in changes
    after = planned_native(native_writer, str(source), str(target), "doc-object", changes, budget())
    assert compare(str(source), parent, str(target), after, native_writer, {}, budget())
    wrapped = native_wrapper(after.streams[path])
    child = CompoundFile(wrapped.payload)
    assert len(native_wrapper(child.streams[path]).payload) < len(parsed.payload)
    with pytest.raises(ValueError, match="depth"):
        optimize(str(source), parent, native_writer, {}, budget(), depth=5)
    with pytest.raises(ValueError, match="cyclic"):
        optimize(
            str(source),
            parent,
            native_writer,
            {},
            budget(),
            ancestors=frozenset({hashlib.sha256(parent.data).digest()}),
        )


@pytest.mark.parametrize("deep", (False, True))
def test_public_deep_option_controls_recursive_cfb_children(tmp_path, native_writer, deep):
    child, scope = native_zip_parent()
    path = scope + ("\x01Ole10Native",)
    wrapped = native_wrapper(child.streams[path])
    streams = {**child.streams, path: wrapped.rebuild(child.data)}
    source, target = tmp_path / "recursive.doc", tmp_path / "candidate.doc"
    source.write_bytes(container(child, streams))
    original = source.read_bytes()
    FileRepacker().repack(
        str(source),
        outfile=str(target),
        options=RepackOptions(ole_embedded_recompress=True, deep_walking=deep),
    )
    assert source.read_bytes() == original
    parent = read_compound(str(target))
    after = CompoundFile(native_wrapper(parent.streams[path]).payload)
    payload = native_wrapper(after.streams[path]).payload
    assert (len(payload) < len(wrapped.payload)) is deep
    if not deep:
        assert payload == wrapped.payload


@pytest.mark.parametrize(
    "name,make,flag",
    (
        ("a.xls", duplicate_xls, "ole_deduplicate_images"),
        ("a.doc", lambda: native_zip_parent()[0], "ole_embedded_recompress"),
        ("a.hwp", weak_hwp, "ole_recompress"),
    ),
)
def test_new_mode_archive_bulk_and_threshold_policies(tmp_path, native_writer, name, make, flag):
    from filerepack.jobs import process_file_job

    source = tmp_path / name
    data = make().data
    source.write_bytes(data)
    result = pack_ole(str(source), min_savings=100, **{flag: True})
    assert not result.replaced and source.read_bytes() == data
    result = (
        FileRepacker()
        .repack(str(source), options=RepackOptions(backup=True, **{flag: True}))
        .results[0]
    )
    assert result.replaced and (tmp_path / (name + ".bak")).read_bytes() == data
    source.write_bytes(data)
    result = process_file_job({"filepath": str(source), flag: True})
    assert result["final_size"] < result["original_size"]
    archive = tmp_path / "parent.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, data)
        output.writestr("opaque.bin", b"unchanged")
    FileRepacker().repack(str(archive), options=RepackOptions(**{flag: True}))
    with zipfile.ZipFile(archive) as output:
        assert len(output.read(name)) < len(data)
        assert output.read("opaque.bin") == b"unchanged"


def test_real_xls_object_reference_class_graph_is_bounded():
    from filerepack.ole_embedded import xls_objects

    view = read_compound(str(CORPUS / "WithEmbeddedObjects.xls"))
    assert xls_objects(view, budget()) == {("MBD001805CA",), ("MBD001805CB",)}
    assert inspect_ole(str(CORPUS / "WithEmbeddedObjects.xls")).eligible


@pytest.mark.parametrize(
    "name,flag",
    (
        ("bad.hwp", "ole_recompress"),
        ("bad.xls", "ole_deduplicate_images"),
        ("bad.doc", "ole_embedded_recompress"),
    ),
)
def test_root_worker_limits_preserve_source_and_cleanup(tmp_path, native_writer, name, flag):
    data = (
        weak_hwp().data
        if name.endswith("hwp")
        else (duplicate_xls().data if name.endswith("xls") else native_zip_parent()[0].data)
    )
    source = tmp_path / name
    source.write_bytes(data)
    result = pack_ole(str(source), format_max_nodes=1, **{flag: True})
    assert not result.replaced and source.read_bytes() == data
    assert "budget" in result.reason.lower()
    assert sorted(p.name for p in tmp_path.iterdir()) == [name]


@pytest.mark.parametrize(
    "host,path",
    (
        ("doc", ("1Table", "nested")),
        ("xls", ("WordDocument",)),
        ("hwp", ("FileHeader",)),
        ("doc-object", ("ObjectPool", "_1", "..", "Workbook")),
    ),
)
def test_native_plan_rejects_unknown_or_escaping_scope(tmp_path, native_writer, host, path):
    original = read_compound(str(CORPUS / "word_with_embeded.doc"))
    source, target = tmp_path / "source.doc", tmp_path / "candidate.doc"
    source.write_bytes(original.data)
    target.touch()
    with pytest.raises(ValueError):
        planned_native(native_writer, str(source), str(target), host, {path: b"bad"}, budget())
    assert source.read_bytes() == original.data and not target.read_bytes()


@pytest.mark.parametrize("make,path", ((duplicate_xls, BOOK), (duplicate_ppt, DOCUMENT)))
def test_dedup_display_crop_fault_changes_normalized_manifest(make, path):
    original = make()
    layout = inspect_dedup(original, budget())
    changes, _ = layout.rebuild()
    after = CompoundFile(container(original, {**original.streams, **changes}))
    final_layout = inspect_dedup(after, budget())
    expected = final_layout.fingerprint()
    data = bytearray(after.streams[path])
    # Every byte outside index/count/store location spans stays exact. Pick an
    # audited host drawing FOPT crop/identity property rather than compressed data.
    if path == BOOK:
        from filerepack.ole_xls_art import biff

        fragments, fields = [], []
        for at, kind, body in biff(bytes(data)):
            if kind in (0xEC, 0x3C) and at > final_layout.adapter.stop:
                fragments.append(body)
                fields.extend(range(at + 4, at + 4 + len(body)))
            elif kind == 0xA and fragments:
                break
        from filerepack.ole_ppt import read_records

        records = read_records(b"".join(fragments))
        prop = next(a for a, r in records.items() if r.kind == 0xF00B)
        value = fields[prop + 8 + 2]
    else:
        from filerepack.ole_ppt import read_records

        records = read_records(bytes(data))
        prop = next(a for a, r in records.items() if r.kind == 0xF00B)
        value = prop + 8 + 2
    data[value] ^= 1
    streams = {**after.streams, path: bytes(data)}
    try:
        actual = inspect_dedup(CompoundFile(container(after, streams)), budget()).fingerprint()
    except ValueError:
        return
    assert actual != expected


@pytest.mark.parametrize("name,count", (("pagedefs.hwp", 3), ("sample-5017.hwp", 4)))
def test_real_hwp_multiple_sections_and_compressed_bindata(name, count):
    before = read_compound(str(EXTENDED / name))
    source = inspect_hwp(before, budget())
    assert len(source.decoded) == count
    changes, _ = source.reencode(budget())
    after = inspect_hwp(CompoundFile(container(before, {**before.streams, **changes})), budget())
    assert source.fingerprint() == after.fingerprint()
