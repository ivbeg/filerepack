"""Production OfficeArt discovery, independent controls and publication gates."""

import json
import shutil
import struct
import subprocess
import threading
import zipfile
import zlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole import pack_ole
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_officeart import Parser, encode_metafiles, header
from filerepack.ole_recompress import operate
from filerepack.ole_verify import CompoundFile, ole_fingerprint, read_compound
from filerepack.ole_word_art import fkps, style_properties
from filerepack.ole_xls_art import biff
from filerepack.verification import verify_preservation
from test.ole_art_fixtures import (
    BOOK,
    DATA,
    DOCUMENT,
    NAMES,
    WORD,
    container,
    control,
    envelope,
)
from test.ole_fixtures import CORPUS, compound_bytes
from test.test_ole import native_writer as _native_writer

native_writer = _native_writer


def budget(**limits):
    return Budget(FormatLimits(**limits))


def parsed(name):
    return inspect_art(read_compound(str(CORPUS / name)), budget())


def mutate(compound, path, offset, fmt=None, value=None):
    streams = dict(compound.streams)
    data = bytearray(streams[path])
    if fmt:
        struct.pack_into(fmt, data, offset, value)
    else:
        data[offset] ^= 1
    streams[path] = bytes(data)
    return CompoundFile(container(compound, streams))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("level", [0, 1])
def test_generic_adapters_accept_independent_controls_and_preserve(name, level, monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "_zopfli", lambda: None)
    source = control(name, level)
    before = inspect_art(source, budget())
    replacements, details = before.reencode(budget())
    after = inspect_art(
        CompoundFile(container(source, {**source.streams, **replacements})), budget()
    )
    assert equal_art(before, after)
    assert source.manifest != after.compound.manifest
    assert details["recompressed_metafiles"] > 0 and details["stream_savings_bytes"] > 0
    assert all(
        len(a.metafile.encoded) <= len(b.metafile.encoded)
        for a, b in zip(after.metafiles, before.metafiles)
    )
    assert all(a.metafile.raw == b.metafile.raw for a, b in zip(after.metafiles, before.metafiles))


def test_doc_reference_discovery_moves_formatting_pages_without_checksums():
    source = read_compound(str(CORPUS / "word_with_embeded.doc"))
    streams = dict(source.streams)
    word, table = bytearray(streams[WORD]), bytearray(streams[("1Table",)])
    for index in (12, 13):
        at, length = struct.unpack_from("<II", word, 154 + 8 * index)
        assert length == 12
        page = struct.unpack_from("<I", table, at + 8)[0]
        new_page = len(word) // 512
        word.extend(word[page * 512 : (page + 1) * 512])
        struct.pack_into("<I", table, at + 8, new_page)
    streams.update({WORD: bytes(word), ("1Table",): bytes(table)})
    layout = inspect_art(CompoundFile(container(source, streams)), budget())
    assert set(layout.adapter.refs.values()) == {0, 1129, 2247, 4264}
    assert min(layout.adapter.refs) >= len(source.streams[WORD])
    replacements, _ = layout.reencode(budget())
    # U+0014 operands identify OLE objects, even though their opcode is CPicLocation.
    assert replacements[WORD][2560:3072] == source.streams[WORD][2560:3072]
    assert equal_art(
        layout, inspect_art(CompoundFile(container(source, {**streams, **replacements})), budget())
    )


@pytest.mark.parametrize(
    "fault",
    [
        "decoded-size",
        "saved-size",
        "filter",
        "compression",
        "version",
        "instance",
        "length",
        "truncated",
        "checksum",
        "raw-deflate",
        "trailing",
        "concatenated",
    ],
)
@pytest.mark.parametrize("name", NAMES)
def test_common_envelope_faults_are_rejected(name, fault):
    record = parsed(name).metafiles[0]
    flags, body = record.flags, bytearray(record.body)
    uid = len(record.metafile.prefix) - 34
    if fault in ("decoded-size", "saved-size"):
        field = uid + (0 if fault == "decoded-size" else 28)
        struct.pack_into("<I", body, field, struct.unpack_from("<I", body, field)[0] + 1)
    elif fault in ("filter", "compression"):
        body[uid + (33 if fault == "filter" else 32)] ^= 1
    elif fault in ("version", "instance"):
        flags ^= 1 if fault == "version" else 0x1000
    elif fault == "checksum":
        body[-1] ^= 1
    elif fault in ("raw-deflate", "trailing", "concatenated"):
        encoded = bytes(body[uid + 34 :])
        if fault == "raw-deflate":
            engine = zlib.compressobj(wbits=-15)
            encoded = engine.compress(record.metafile.raw) + engine.flush()
        else:
            encoded += b"x" if fault == "trailing" else zlib.compress(b"extra")
        body[uid + 34 :] = encoded
        struct.pack_into("<I", body, uid + 28, len(encoded))
    data = envelope(flags, record.kind, body)
    if fault == "length":
        data = data[:4] + struct.pack("<I", len(body) + 1) + data[8:]
    elif fault == "truncated":
        data = data[:-1]
    with pytest.raises(ValueError):
        Parser(budget()).sequence(data)


@pytest.mark.parametrize("fault", ["raw", "uid", "geometry", "raster", "unrelated", "metadata"])
def test_intended_verifier_rejects_valid_but_changed_content(fault, monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "_zopfli", lambda: None)
    source = control("SimpleWithImages.xls")
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    streams = {**source.streams, **replacements}
    if fault in ("raw", "uid", "geometry"):
        record = before.metafiles[0]
        prefix = bytearray(record.metafile.prefix)
        raw = record.metafile.raw
        if fault == "raw":
            raw = raw[:-1] + bytes([raw[-1] ^ 1])
        else:
            prefix[0 if fault == "uid" else len(prefix) - 30] ^= 1
        encoded = zlib.compress(raw, 9)
        struct.pack_into("<I", prefix, len(prefix) - 6, len(encoded))
        blob = header(record.flags, record.kind, bytes(prefix) + encoded)
        old_blob = record.encode({id(record): zlib.compress(record.metafile.raw, 9)})
        # Equal-size metadata changes can be spliced into the independently rebuilt group.
        group = before.adapter.group.encode(
            {id(r): zlib.compress(r.metafile.raw, 9) for r in before.metafiles}
        )
        assert old_blob in group
        group = group.replace(old_blob, blob, 1)
        if len(blob) != len(old_blob):
            # Raw changes need all enclosing lengths repaired by a structurally valid plan.
            from dataclasses import replace

            changed = replace(record, metafile=replace(record.metafile, raw=raw))
            payloads = {id(record): encoded}
            streams.update(before.adapter.rebuild(payloads))
            altered = inspect_art(CompoundFile(container(source, streams)), budget())
            assert changed.metafile.raw == altered.metafiles[0].metafile.raw
        else:
            book = bytearray(streams[BOOK])
            # First WMF header is wholly inside the second 8224-byte fragment.
            position = book.find(old_blob[:50])
            assert position > 0
            book[position : position + 50] = blob[:50]
            if fault == "uid":
                book[position - 34 : position - 18] = blob[8:24]
            streams[BOOK] = bytes(book)
    elif fault == "raster":
        book = bytearray(streams[BOOK])
        book[1408 + 4 + 130] ^= 1  # JPEG payload; retained verbatim.
        streams[BOOK] = bytes(book)
    elif fault == "unrelated":
        streams[("\x05SummaryInformation",)] += b"changed"
    if fault == "metadata":
        candidate = CompoundFile(compound_bytes(streams, root=(b"\0" * 16, 1, 0, 0)))
    else:
        candidate = CompoundFile(container(source, streams))
    assert not equal_art(before, inspect_art(candidate, budget()))


@pytest.mark.parametrize(
    "fault",
    [
        "prm",
        "cp",
        "text-fib",
        "page-alias",
        "style",
        "extended-version",
        "unknown-property",
        "binary-data",
        "toggle",
        "reference",
        "tail",
    ],
)
def test_doc_ambiguous_or_unqualified_layouts_rejected(fault):
    source = read_compound(str(CORPUS / "vector_image.doc"))
    table = ("1Table",)
    changes = {
        "prm": (table, 1027 + 19, "<H", 1),
        "cp": (table, 1027 + 9, "<I", 0),
        "text-fib": (table, 1027 + 15, "<I", 0x40000000),
        "page-alias": (table, 562 + 8, "<I", 5),
        "style": (WORD, 3580, "<H", 10),
        "extended-version": (WORD, 1244, "<H", 0xFFFF),
        "unknown-property": (WORD, 3055, "<H", 0xFFFF),
        "binary-data": (WORD, 3055, "<H", 0x0806),
        "toggle": (WORD, 3069, "<B", 128),
        "reference": (WORD, 3057, "<I", 1),
        "tail": (DATA, 4095, "<B", 1),
    }
    path, at, fmt, value = changes[fault]
    with pytest.raises(ValueError):
        inspect_art(mutate(source, path, at, fmt, value), budget())


@pytest.mark.parametrize("kind", [0x85, 0x20B])
def test_xls_stale_pointer_and_valid_wrong_target_are_distinct(kind):
    source = control("SimpleWithImages.xls")
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    candidate = CompoundFile(container(source, {**source.streams, **replacements}))
    records = [(at, data) for at, k, data in biff(candidate.streams[BOOK]) if k == kind]
    field = records[0][0] + (4 if kind == 0x85 else 16)
    with pytest.raises(ValueError):
        inspect_art(mutate(candidate, BOOK, field, "<I", 1), budget())
    target = struct.unpack_from("<I", records[1][1], 0 if kind == 0x85 else 12)[0]
    changed = inspect_art(mutate(candidate, BOOK, field, "<I", target), budget())
    assert not equal_art(before, changed)


@pytest.mark.parametrize("fault", ["unknown", "sst", "extsst", "index", "linked-object"])
def test_unqualified_xls_record_families_rejected(fault):
    source = read_compound(str(CORPUS / "SimpleWithImages.xls"))
    changes = {
        "unknown": (0, "<H", 0xFFFF),
        "sst": (36523, "<I", 1),
        "extsst": (36535, "<H", 0),
        "index": (36590, "<I", 1),
        "linked-object": (36944, "<H", 7),
    }
    at, fmt, value = changes[fault]
    if fault == "linked-object":
        at = next(at + 8 for at, kind, _ in biff(source.streams[BOOK]) if kind == 0x5D)
    with pytest.raises(ValueError):
        inspect_art(mutate(source, BOOK, at, fmt, value), budget())


@pytest.mark.parametrize(
    "at,fmt,value",
    [
        (864, "<I", 1),
        (856, "<I", 1),
        (908, "<I", 0),
        (860, "<I", 7),
        (833, "<B", 1),
        (869, "<B", 2),
    ],
)
def test_ppt_delay_size_uid_alias_and_named_references_rejected(at, fmt, value):
    source = read_compound(str(CORPUS / "ole2-embedding-2003.ppt"))
    with pytest.raises(ValueError):
        inspect_art(mutate(source, DOCUMENT, at, fmt, value), budget())


def test_two_uid_variant_and_codec_limits(monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "_zopfli", lambda: None)
    original = parsed("vector_image.doc").metafiles[0]
    blob = header(original.flags + 16, original.kind, bytes(range(16)) + original.body)
    parser = Parser(budget())
    record = parser.sequence(blob)[0]
    payloads, _ = encode_metafiles(parser.metafiles, budget())
    rewritten = Parser(budget()).sequence(record.encode(payloads))[0]
    assert record.fingerprint() == rewritten.fingerprint()
    assert rewritten.body[:32] == bytes(range(16)) + original.body[:16]
    with pytest.raises(FormatLimit):
        Parser(budget()).sequence(blob * 65)
    oversized = bytearray(original.body)
    struct.pack_into("<I", oversized, 16, 16 * 1024 * 1024 + 1)
    with pytest.raises(FormatLimit):
        Parser(budget()).sequence(header(original.flags, original.kind, oversized))


@pytest.mark.parametrize("limits", [{"decoded": 10}, {"memory": 1000}, {"nodes": 5}])
def test_root_parser_budgets(limits):
    with pytest.raises(FormatLimit):
        inspect_art(control("word_with_embeded.doc"), budget(**limits))


def test_optional_encoder_version_and_bad_encoder(monkeypatch):
    import filerepack.ole_officeart as codec

    monkeypatch.setattr(codec, "version", lambda _: "unqualified")
    assert codec._zopfli() is None
    layout = inspect_art(control("vector_image.doc"), budget())
    monkeypatch.setattr(codec, "_zopfli", lambda: lambda raw, **kw: zlib.compress(b"bad", 9))
    with pytest.raises(ValueError):
        layout.reencode(budget())


def test_style_inheritance_resolved_and_partially_aliased_formatting_rejected():
    base = bytearray(18)
    struct.pack_into("<H", base, 2, 0xFFF1)  # Root paragraph style.
    struct.pack_into("<H", base, 4, 2)
    body = base + b"\0\0\0\0" + b"\x02\0\0\0" + struct.pack("<3H", 4, 0x4A43, 24)
    struct.pack_into("<H", body, 6, len(body))
    styles = struct.pack("<H9H", 18, 15, 18, *([0] * 7))
    styles += struct.pack("<H", len(body)) + body + b"\0\0" * 14
    resolved = {}
    assert style_properties(styles, budget(), resolved=resolved) == {0: 1}
    assert resolved[0][0x4A43][0] < 0 and resolved[0][0x4A43][1] == b"\x18\0"
    page = bytearray(512)
    struct.pack_into("<5I", page, 0, 100, 101, 102, 103, 104)
    page[20:24] = bytes([50, 52, 0, 0])
    page[100], page[104], page[511] = 8, 4, 4
    # The second property's length header aliases the first property's payload.
    table = struct.pack("<III", 100, 104, 0)
    word = bytearray(page)
    word.extend(b"\0" * 512)
    struct.pack_into("<II", word, 154 + 8 * 12, 0, len(table))
    with pytest.raises(ValueError, match="aliased FKP"):
        fkps(bytes(word), table, 12, budget())


@pytest.mark.parametrize(
    "name",
    [
        "SimpleMacro.doc",
        "SimpleMacro.xls",
        "SimpleMacro.ppt",
        "PasswordProtected.doc",
        "password.xls",
        "Password_Protected-hello.ppt",
    ],
)
def test_protected_or_macro_payload_profiles_rejected(name):
    with pytest.raises(ValueError):
        inspect_art(read_compound(str(CORPUS / name)), budget())


def test_independent_cfb_reader_disagreement_is_fatal(monkeypatch):
    import filerepack.ole_art_layout as module

    monkeypatch.setattr(
        module,
        "independent_manifest",
        lambda *a: (_ for _ in ()).throw(ValueError("reader disagreement")),
    )
    with pytest.raises(ValueError, match="disagreement"):
        inspect_art(read_compound(str(CORPUS / NAMES[0])), budget())


@pytest.mark.parametrize(
    "ext,name",
    [
        ("doc", NAMES[0]),
        ("dot", NAMES[0]),
        ("xls", NAMES[2]),
        ("xlt", NAMES[2]),
        ("xla", NAMES[2]),
        ("ppt", NAMES[3]),
        ("pot", NAMES[3]),
        ("pps", NAMES[3]),
    ],
)
def test_public_aliases_use_independently_verified_officeart(tmp_path, native_writer, ext, name):
    pytest.importorskip("psutil")
    source, candidate = tmp_path / ("source." + ext), tmp_path / ("output." + ext)
    source.write_bytes(control(name).data)
    original = source.read_bytes()
    summary = FileRepacker().repack(
        str(source), outfile=str(candidate), options=RepackOptions(ole_recompress=True)
    )
    result = summary.results[0]
    assert result.details["strategy"] == "ole-officeart-recompression"
    assert candidate.stat().st_size < source.stat().st_size
    assert source.read_bytes() == original
    assert verify_preservation(str(source), str(candidate), "officeart")
    assert not verify_preservation(str(source), str(candidate), "ole")


@pytest.mark.parametrize(
    "name,strategy",
    [
        (NAMES[0], "ole-compaction"),
        (NAMES[1], "ole-officeart-recompression"),
        (NAMES[2], "ole-officeart-recompression"),
        (NAMES[3], "ppt-ole-recompression"),
    ],
)
def test_physical_candidate_selection_on_real_originals(tmp_path, native_writer, name, strategy):
    from filerepack.ole_officeart import _zopfli

    if _zopfli() is None and name in (NAMES[2], NAMES[3]):
        strategy = "ole-compaction"  # Portable zlib9 saves no additional sectors here.
    path = tmp_path / name
    shutil.copyfile(CORPUS / name, path)
    result = pack_ole(str(path), ole_recompress=True)
    assert result.details["strategy"] == strategy
    if strategy == "ole-compaction":
        assert result.details["officeart"]["stream_savings_bytes"] >= 0
        assert result.details["officeart_skip"]


@pytest.mark.parametrize(
    "options",
    [
        {"dryrun": True},
        {"min_savings": 99.0},
        {"format_max_decoded_bytes": 10},
        {"format_timeout": 0.02},
        {"format_max_scratch_bytes": 100},
        {"format_max_memory_bytes": 1024},
    ],
)
def test_publication_rejection_keeps_source_and_cleans_scratch(tmp_path, native_writer, options):
    source = tmp_path / "source.doc"
    source.write_bytes(control(NAMES[0]).data)
    before = source.read_bytes()
    result = pack_ole(str(source), ole_recompress=True, **options)
    assert not result.replaced and source.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["source.doc"]


def test_cancel_event_reaches_officeart_worker(tmp_path, native_writer):
    source = tmp_path / "source.doc"
    source.write_bytes(control(NAMES[0]).data)
    before = source.read_bytes()
    event = threading.Event()
    event.set()
    result = pack_ole(str(source), ole_recompress=True, _cancel_event=event)
    assert not result.replaced and "cancelled" in result.reason
    assert source.read_bytes() == before


def test_interrupt_and_missing_worker_dependency_leave_source(tmp_path, native_writer, monkeypatch):
    import filerepack.ole_recompress as module
    import sys

    source = tmp_path / "source.doc"
    source.write_bytes(control(NAMES[0]).data)
    before = source.read_bytes()
    directories = []
    factory = module.tempfile.TemporaryDirectory

    def track(*args, **kwargs):
        result = factory(*args, **kwargs)
        directories.append(result.name)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(module.tempfile, "TemporaryDirectory", track)
        patch.setattr(
            module, "run_art_operation", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt())
        )
        with pytest.raises(KeyboardInterrupt):
            pack_ole(str(source), ole_recompress=True)
    assert source.read_bytes() == before and all(not Path(p).exists() for p in directories)
    monkeypatch.setitem(sys.modules, "psutil", None)
    result = pack_ole(str(source), ole_recompress=True)
    assert not result.replaced and source.read_bytes() == before
    assert "ole-recompress" in result.reason


def test_nested_archives_and_destination_metadata(tmp_path, native_writer):
    source = tmp_path / "source.doc"
    source.write_bytes(control(NAMES[0]).data)
    before = source.read_bytes()
    output = tmp_path / "output.doc"
    summary = FileRepacker().repack(
        str(source), outfile=str(output), options=RepackOptions(ole_recompress=True, backup=True)
    )
    assert summary.results and source.read_bytes() == before
    assert output.stat().st_size < len(before)
    archive = tmp_path / "documents.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("nested.doc", before)
        package.writestr("unknown.bin", b"opaque")
    FileRepacker().repack(str(archive), options=RepackOptions(ole_recompress=True))
    with zipfile.ZipFile(archive) as package:
        assert len(package.read("nested.doc")) < len(before)
        assert package.read("unknown.bin") == b"opaque"


def test_old_helper_fallback_and_faulty_writer_rejection(tmp_path, native_writer, monkeypatch):
    import filerepack.ole_recompress as module

    source, candidate = tmp_path / "source.doc", tmp_path / "candidate.doc"
    source.write_bytes(control(NAMES[0]).data)
    candidate.touch()
    command = module._command
    monkeypatch.setattr(
        module,
        "_command",
        lambda args, bounds: subprocess.CompletedProcess(args, 0, b"compact-v3", b"")
        if args[-1] == "--capabilities"
        else command(args, bounds),
    )
    info = operate(
        "officeart", "rewrite", str(source), str(candidate), {"ole_writer": native_writer}, budget()
    )
    assert info["verify"] == "ole" and "0.3.0" in info["details"]["officeart_skip"]
    assert ole_fingerprint(str(source)) == ole_fingerprint(str(candidate))

    def corrupt(args, bounds):
        if "--replace-officeart-streams" in args:
            word = Path(args[3])
            data = bytearray(word.read_bytes())
            data[-1] ^= 1
            word.write_bytes(data)
        return command(args, bounds)

    monkeypatch.setattr(module, "_command", corrupt)
    candidate.write_bytes(b"")
    with pytest.raises(ValueError, match="intended content"):
        operate(
            "officeart",
            "rewrite",
            str(source),
            str(candidate),
            {"ole_writer": native_writer},
            budget(),
        )
    assert source.read_bytes() == control(NAMES[0]).data


def test_native_fixed_stream_plan_preserves_nested_duplicates_and_metadata(tmp_path, native_writer):
    original = control(NAMES[0])
    streams = {
        **original.streams,
        ("nested", "WordDocument"): b"opaque nested word",
        ("nested", "Data"): b"opaque nested data",
    }
    meta = (bytes(range(16)), 0xDA123456, 133000000000000001, 133000000000000002)
    source, candidate = tmp_path / "source.doc", tmp_path / "candidate.doc"
    source.write_bytes(
        compound_bytes(
            streams,
            storages={
                ("nested",): meta,
                ("empty",): meta,
                WORD: (b"\0" * 16, meta[1], 0, 0),
                DATA: (b"\0" * 16, meta[1], 0, 0),
            },
            root=(meta[0], meta[1], 0, meta[3]),
        )
    )
    layout = inspect_art(original, budget())
    replacements, _ = layout.reencode(budget())
    inputs = []
    for name in (WORD, DATA):
        path = tmp_path / name[0]
        path.write_bytes(replacements[name])
        inputs.append(str(path))
    candidate.touch()
    subprocess.run(
        [native_writer, "--replace-officeart-streams", "doc", *inputs, str(source), str(candidate)],
        check=True,
        capture_output=True,
    )
    before, after = read_compound(str(source)), read_compound(str(candidate))
    for entry in before.manifest.entries:
        other = next(e for e in after.manifest.entries if e.path == entry.path)
        assert (entry.clsid, entry.state, entry.created, entry.modified) == (
            other.clsid,
            other.state,
            other.created,
            other.modified,
        )
    assert all(after.streams[p] == value for p, value in streams.items() if p not in replacements)
    assert all(after.streams[p] == value for p, value in replacements.items())
    # Existing output bytes and arbitrary host/stream plans are refused.
    result = subprocess.run(
        [native_writer, "--replace-officeart-streams", "doc", *inputs, str(source), str(candidate)],
        capture_output=True,
    )
    assert result.returncode
    candidate.write_bytes(b"")
    result = subprocess.run(
        [
            native_writer,
            "--replace-officeart-streams",
            "unknown",
            *inputs,
            str(source),
            str(candidate),
        ],
        capture_output=True,
    )
    assert result.returncode and candidate.read_bytes() == b""


@pytest.mark.parametrize("command", ["repack", "bulk"])
def test_verbose_and_json_payload_diagnostics(tmp_path, native_writer, command):
    path = tmp_path / "source.doc"
    path.write_bytes(control(NAMES[0]).data)
    target = str(path if command == "repack" else tmp_path)
    extra = ["--no-progress"] if command == "repack" else ["--jobs", "1"]
    runner = CliRunner()
    result = runner.invoke(
        app, [command, target, "--ole-recompress", "--dryrun", "--verbose", *extra]
    )
    assert result.exit_code == 0, result.output
    assert "OfficeArt: 1 EMF/WMF payloads, 1 recompressed" in result.stdout
    assert "Additional file savings beyond compaction:" in result.stdout
    result = runner.invoke(app, [command, target, "--ole-recompress", "--dryrun", "--json", *extra])
    assert result.exit_code == 0, result.output
    record = json.loads(result.stdout)["files"][0]
    assert record["details"]["officeart"]["metafile_count"] == 1
