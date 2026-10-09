"""Opt-in PPT record preservation, relocation, native writer and publication gates."""

import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole import pack_ole
from filerepack.ole_ppt_records import CURRENT, DOCUMENT, equal_layouts, inspect_records, reencode
from filerepack.ole_recompress import operate
from filerepack.ole_verify import CompoundFile, ole_fingerprint, read_compound
from filerepack.verification import verify_preservation
from test.ole_fixtures import CORPUS, compound_bytes, ppt_embedded_streams
from test.test_ole import legacy_root, native_writer as _native_writer

native_writer = _native_writer


def budget(**limits):
    return Budget(FormatLimits(**limits))


@pytest.fixture(scope="module")
def original():
    return read_compound(str(CORPUS / "ole2-embedding-2003.ppt"))


@pytest.fixture(scope="module")
def objects(original):
    return inspect_records(original, budget()).objects


def poorly_encoded(objects):
    import zlib

    return ppt_embedded_streams([zlib.compress(obj.raw, 0) for obj in objects])


def source_file(tmp_path, objects, name="sample.ppt"):
    path = tmp_path / name
    path.write_bytes(compound_bytes(poorly_encoded(objects)))
    return path


def test_generic_profile_and_exact_contract(original, objects, monkeypatch):
    import zlib

    monkeypatch.setitem(sys.modules, "zopfli.zlib", None)
    # This source has different wrapper lengths, metadata and an opaque stream.
    streams = poorly_encoded(objects)
    streams[("opaque stream",)] = b"unknown bytes"
    metadata = {
        ("empty storage",): (bytes(range(16)), 0xAA000003, 133000000000000001, 133000000000000002)
    }
    source = CompoundFile(compound_bytes(streams, storages=metadata))
    before = inspect_records(source, budget())
    document, current, encoders = reencode(before, budget())
    assert encoders == ["zlib9", "zlib9"]
    expected = ppt_embedded_streams([zlib.compress(obj.raw, 9) for obj in objects])
    assert document == expected[DOCUMENT] and current == expected[CURRENT]
    assert document != original.streams[DOCUMENT]
    streams[DOCUMENT], streams[CURRENT] = document, current
    candidate = CompoundFile(
        compound_bytes(
            streams,
            storages={
                ("empty storage",): (
                    bytes(range(16)),
                    0xAA000003,
                    133000000000000001,
                    133000000000000002,
                )
            },
        )
    )
    after = inspect_records(candidate, budget())
    assert equal_layouts(before, after) and source.manifest != candidate.manifest


@pytest.mark.parametrize(
    "fault",
    [
        "stale-current",
        "stale-index",
        "stale-edit",
        "duplicate-target",
        "duplicate-identity",
        "duplicate-reference",
        "nested-reference",
        "unknown-record",
        "unknown-tag",
        "unknown-tag-data",
        "linked-object",
        "wrong-subtype",
        "uncompressed-wrapper",
        "decoded-size",
        "checksum",
        "extra-edit",
        "extra-tail",
    ],
)
def test_invalid_profile_or_wrapper_is_rejected(original, fault):
    streams = dict(original.streams)
    data = bytearray(streams[DOCUMENT])
    changes = {
        "stale-index": ("<I", 9797 + 20, 7196),
        "stale-edit": ("<I", 9829 + 20, 9798),
        "duplicate-target": ("<I", 9797 + 20, 4568),
        "duplicate-identity": ("<I", 272 + 16, 1),
        "duplicate-reference": ("<I", 4372 + 8, 1),
        "nested-reference": ("<I", 9797 + 16, 100),
        "unknown-record": ("<H", 132 + 2, 65000),
        "unknown-tag-data": ("<H", 1295 + 10, 65000),
        "linked-object": ("<I", 100 + 12, 1),
        "wrong-subtype": ("<I", 100 + 20, 3),
        "uncompressed-wrapper": ("<H", 4568, 0),
        "decoded-size": ("<I", 4568 + 8, 512),
    }
    if fault in changes:
        fmt, position, value = changes[fault]
        struct.pack_into(fmt, data, position, value)
    elif fault == "stale-current":
        current = bytearray(streams[CURRENT])
        struct.pack_into("<I", current, 16, 1)
        streams[CURRENT] = bytes(current)
    elif fault == "unknown-tag":
        data[1271 + 8] = ord("X")
    elif fault == "checksum":
        data[7194] ^= 1
    elif fault == "extra-edit":
        data.extend(original.streams[DOCUMENT][9829:])
    elif fault == "extra-tail":
        data.extend(b"\0" * 8)
    streams[DOCUMENT] = bytes(data)
    with pytest.raises(ValueError):
        inspect_records(CompoundFile(compound_bytes(streams)), budget())


@pytest.mark.parametrize(
    "name",
    [
        "SimpleMacro.ppt",
        "ppt_with_embeded.ppt",
        "testPPT_oleWorkbook.ppt",
        "Password_Protected-hello.ppt",
    ],
)
def test_unqualified_real_profiles(name):
    with pytest.raises(ValueError):
        inspect_records(read_compound(str(CORPUS / name)), budget())


@pytest.mark.parametrize("limits", [{"decoded": 40000}, {"memory": 10000}, {"nodes": 20}])
def test_parser_budget_is_not_waived(original, limits):
    with pytest.raises(FormatLimit):
        inspect_records(original, budget(**limits))


@pytest.mark.parametrize("fault", ["trailing", "concatenated", "truncated", "expansion"])
def test_invalid_wrapper_with_consistent_offsets_is_rejected(objects, fault):
    encoded = [obj.encoded for obj in objects]
    sizes = [len(obj.raw) for obj in objects]
    if fault == "trailing":
        encoded[0] += b"extra"
    elif fault == "concatenated":
        encoded[0] += objects[1].encoded
    elif fault == "truncated":
        encoded[0] = encoded[0][:-1]
    else:
        sizes[0] = 512
    source = CompoundFile(compound_bytes(ppt_embedded_streams(encoded, sizes)))
    with pytest.raises(ValueError):
        inspect_records(source, budget())


def test_readers_must_agree(original, monkeypatch):
    import filerepack.ole_ppt_records as module

    monkeypatch.setattr(
        module,
        "independent_manifest",
        lambda *a: (_ for _ in ()).throw(ValueError("reader disagreement")),
    )
    with pytest.raises(ValueError, match="disagreement"):
        inspect_records(original, budget())


@pytest.mark.parametrize("extension", ["ppt", "pot", "pps"])
@pytest.mark.parametrize("legacy_names", [False, True])
def test_native_opt_in_and_aliases(tmp_path, objects, native_writer, extension, legacy_names):
    pytest.importorskip("psutil")
    path = source_file(tmp_path, objects, "presentation." + extension)
    if legacy_names:
        streams = read_compound(str(path)).streams
        streams[("MsoDataStore", "ß")] = b"opaque payload"
        path.write_bytes(legacy_root(compound_bytes(streams)))
    before = inspect_records(read_compound(str(path)), budget())
    result = pack_ole(str(path), ole_recompress=True)
    assert result is not None and result.replaced
    assert result.details["strategy"] == "ppt-ole-recompression"
    assert result.details["additional_savings_bytes"] > 49000
    assert equal_layouts(before, inspect_records(read_compound(str(path)), budget()))


def test_default_stays_strict(tmp_path, objects, native_writer):
    path = source_file(tmp_path, objects)
    before = ole_fingerprint(str(path))
    result = pack_ole(str(path))
    assert result is not None and result.details["strategy"] == "ole-compaction"
    assert ole_fingerprint(str(path)) == before


@pytest.mark.parametrize("mode", ["dryrun", "min_savings"])
def test_rejected_or_dryrun_candidate_leaves_source(tmp_path, objects, native_writer, mode):
    pytest.importorskip("psutil")
    path = source_file(tmp_path, objects)
    before = path.read_bytes()
    options = {mode: True if mode == "dryrun" else 99.0}
    result = pack_ole(str(path), ole_recompress=True, **options)
    assert result is not None and not result.replaced and path.read_bytes() == before


def test_old_helper_falls_back_to_verified_compaction(
    tmp_path, objects, native_writer, monkeypatch
):
    import filerepack.ole_recompress as module

    source = source_file(tmp_path, objects)
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()
    command = module._command
    monkeypatch.setattr(
        module,
        "_command",
        lambda args, bounds: subprocess.CompletedProcess(args, 2, b"", b"old helper")
        if args[-1] == "--capabilities"
        else command(args, bounds),
    )
    info = operate(
        "ppt-ole", "rewrite", str(source), str(candidate), {"ole_writer": native_writer}, budget()
    )
    assert info["verify"] == "ole" and info["details"]["strategy"] == "ole-compaction"
    assert ole_fingerprint(str(source)) == ole_fingerprint(str(candidate))


def test_faulty_native_replacement_cannot_publish(tmp_path, objects, native_writer, monkeypatch):
    import filerepack.ole_recompress as module

    source = source_file(tmp_path, objects)
    before = source.read_bytes()
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()
    command = module._command

    def corrupt(args, bounds):
        if "--replace-ppt-streams" in args:
            current = Path(args[3])
            raw = bytearray(current.read_bytes())
            raw[-1] ^= 1
            current.write_bytes(raw)
        return command(args, bounds)

    monkeypatch.setattr(module, "_command", corrupt)
    with pytest.raises(ValueError, match="intended content"):
        operate(
            "ppt-ole",
            "rewrite",
            str(source),
            str(candidate),
            {"ole_writer": native_writer},
            budget(),
        )
    assert source.read_bytes() == before


def test_mode_contract_rejects_unrelated_changes(tmp_path, objects, native_writer):
    pytest.importorskip("psutil")
    source = source_file(tmp_path, objects)
    candidate = tmp_path / "rewritten.ppt"
    shutil.copyfile(source, candidate)
    assert pack_ole(str(candidate), ole_recompress=True).replaced
    assert verify_preservation(str(source), str(candidate), "ppt-ole")
    assert not verify_preservation(str(source), str(candidate), "ole")
    streams = read_compound(str(candidate)).streams
    streams[("Pictures",)] += b"changed"
    candidate.write_bytes(compound_bytes(streams))
    assert not verify_preservation(str(source), str(candidate), "ppt-ole")


def test_cli_and_bulk_worker_propagate_opt_in(tmp_path, objects, native_writer):
    pytest.importorskip("psutil")
    first = source_file(tmp_path, objects, "cli.ppt")
    runner = CliRunner()
    result = runner.invoke(app, ["repack", str(first), "--ole-recompress"])
    assert result.exit_code == 0, result.output
    assert first.stat().st_size < 40000
    second = source_file(tmp_path, objects, "bulk.ppt")
    result = runner.invoke(app, ["bulk", str(tmp_path), "--ole-recompress", "--jobs", "2"])
    assert result.exit_code == 0, result.output
    assert second.stat().st_size < 40000


def test_nested_zip_and_destination_backup(tmp_path, objects, native_writer):
    pytest.importorskip("psutil")
    source = source_file(tmp_path, objects)
    before = source.read_bytes()
    destination = tmp_path / "output.ppt"
    result = FileRepacker().repack(
        str(source),
        outfile=str(destination),
        options=RepackOptions(ole_recompress=True, backup=True),
    )
    assert result.results and destination.stat().st_size < len(before)
    assert source.read_bytes() == before
    archive = tmp_path / "documents.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("nested.ppt", before)
        package.writestr("unknown.bin", b"opaque")
    FileRepacker().repack(str(archive), options=RepackOptions(ole_recompress=True))
    with zipfile.ZipFile(archive) as package:
        assert len(package.read("nested.ppt")) < len(before)
        assert package.read("unknown.bin") == b"opaque"


def test_native_capability_and_replacement_bounds(tmp_path, native_writer):
    capabilities = subprocess.check_output([native_writer, "--capabilities"])
    assert b"ppt-stream-replacement-v1" in capabilities
    current, document, output = (tmp_path / name for name in ("current", "document", "output"))
    current.write_bytes(b"X" * 4097)
    document.write_bytes(b"X")
    output.touch()
    result = subprocess.run(
        [
            native_writer,
            "--replace-ppt-streams",
            str(document),
            str(current),
            str(CORPUS / "ole2-embedding-2003.ppt"),
            str(output),
        ],
        capture_output=True,
    )
    assert result.returncode != 0 and output.stat().st_size == 0


def test_native_replacement_selects_only_root_streams(tmp_path, objects, native_writer):
    streams = poorly_encoded(objects)
    streams[("nested", "PowerPoint Document")] = b"nested document"
    streams[("nested", "Current User")] = b"nested current user"
    source = tmp_path / "source.ppt"
    source.write_bytes(compound_bytes(streams))
    document, current, _ = reencode(inspect_records(read_compound(str(source)), budget()), budget())
    document_path, current_path, candidate = (
        tmp_path / name for name in ("document", "current", "candidate.ppt")
    )
    document_path.write_bytes(document)
    current_path.write_bytes(current)
    candidate.touch()
    subprocess.run(
        [
            native_writer,
            "--replace-ppt-streams",
            str(document_path),
            str(current_path),
            str(source),
            str(candidate),
        ],
        check=True,
        capture_output=True,
    )
    result = read_compound(str(candidate))
    assert result.streams[DOCUMENT] == document and result.streams[CURRENT] == current
    assert result.streams[("nested", "PowerPoint Document")] == b"nested document"
    assert result.streams[("nested", "Current User")] == b"nested current user"


def test_unqualified_optional_encoder_uses_portable_zlib(original, monkeypatch):
    import filerepack.ole_ppt_records as module
    import zlib

    monkeypatch.setattr(module, "version", lambda name: "0.0.0")
    layout = inspect_records(original, budget())
    document, current, encoders = reencode(layout, budget())
    expected = ppt_embedded_streams([zlib.compress(obj.raw, 9) for obj in layout.objects])
    assert encoders == ["zlib9", "zlib9"]
    assert (document, current) == (expected[DOCUMENT], expected[CURRENT])


def test_larger_encoding_retains_original_wrappers(original, monkeypatch):
    import filerepack.ole_ppt_records as module

    compress = module.zlib.compress
    monkeypatch.setattr(module, "version", lambda name: "0.0.0")
    monkeypatch.setattr(module.zlib, "compress", lambda data, level: compress(data, 0))
    document, current, encoders = reencode(inspect_records(original, budget()), budget())
    assert encoders == ["original", "original"]
    assert document == original.streams[DOCUMENT] and current == original.streams[CURRENT]


def test_mode_contract_retains_root_metadata(original, objects):
    before = inspect_records(original, budget())
    changed = CompoundFile(compound_bytes(poorly_encoded(objects), root=(b"\0" * 16, 8, 0, 0)))
    assert not equal_layouts(before, inspect_records(changed, budget()))


def test_option_is_a_boolean():
    with pytest.raises(ValueError, match="ole_recompress"):
        RepackOptions(ole_recompress="yes")


@pytest.mark.parametrize(
    "options",
    [
        {"format_timeout": 0.02},
        {"format_max_memory_bytes": 1024},
        {"format_max_scratch_bytes": 100},
        {"format_max_decoded_bytes": 40000},
    ],
)
def test_worker_limit_keeps_source(tmp_path, objects, native_writer, options):
    pytest.importorskip("psutil")
    path = source_file(tmp_path, objects)
    before = path.read_bytes()
    result = pack_ole(str(path), ole_recompress=True, **options)
    assert result is not None and not result.replaced and result.reason
    assert path.read_bytes() == before
    if result.status is not None:
        assert result.status == 'skipped' and result.reason_code == 'resource_limit'
    else:
        assert result.details['strategy'] == 'unchanged'


def test_interrupt_cleans_private_files(tmp_path, objects, native_writer, monkeypatch):
    import filerepack.ole_recompress as module

    path = source_file(tmp_path, objects)
    before = path.read_bytes()
    directories = []
    factory = module.tempfile.TemporaryDirectory

    def track(*args, **kwargs):
        result = factory(*args, **kwargs)
        directories.append(result.name)
        return result

    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", track)
    monkeypatch.setattr(
        module, "run_ppt_operation", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        pack_ole(str(path), ole_recompress=True)
    assert path.read_bytes() == before and all(not Path(p).exists() for p in directories)


def test_cancel_event_reaches_ppt_worker(tmp_path, objects, native_writer):
    import threading

    pytest.importorskip("psutil")
    path = source_file(tmp_path, objects)
    before = path.read_bytes()
    event = threading.Event()
    event.set()
    result = pack_ole(str(path), ole_recompress=True, _cancel_event=event)
    assert result is not None and not result.replaced and "cancelled" in result.reason
    assert path.read_bytes() == before


def test_dryrun_destination_backup_and_metadata(tmp_path, objects, native_writer):
    import os
    import stat

    pytest.importorskip("psutil")
    source = source_file(tmp_path, objects)
    source.chmod(0o640)
    os.utime(source, ns=(1600000000000000000, 1600000000000000123))
    before = source.read_bytes()
    metadata = source.stat()
    destination = tmp_path / "outputs" / "rewritten.ppt"
    backups = tmp_path / "backups"
    options = RepackOptions(ole_recompress=True, dryrun=True, backup=True, backup_dir=str(backups))
    FileRepacker().repack(str(source), outfile=str(destination), options=options)
    assert source.read_bytes() == before
    assert not destination.parent.exists() and not backups.exists()
    result = pack_ole(str(source), ole_recompress=True)
    assert result is not None and result.replaced
    assert source.stat().st_mtime_ns == metadata.st_mtime_ns
    assert stat.S_IMODE(source.stat().st_mode) == stat.S_IMODE(metadata.st_mode)


def test_nested_protection_blocks_record_recompression(objects):
    import zlib

    nested = read_compound(str(CORPUS / "simple.doc"))
    streams = {**nested.streams, ("EncryptionInfo",): b"protected"}
    raw = compound_bytes(streams)
    encoded = [zlib.compress(raw, 9), objects[1].encoded]
    candidate = CompoundFile(
        compound_bytes(ppt_embedded_streams(encoded, [len(raw), len(objects[1].raw)]))
    )
    with pytest.raises(ValueError, match="encrypt|Encrypt|protection"):
        inspect_records(candidate, budget())


def test_nested_cfb_layout_is_also_immutable(tmp_path, original, objects, native_writer):
    import zlib

    source, candidate = tmp_path / "nested.doc", tmp_path / "compact.doc"
    source.write_bytes(objects[0].raw)
    candidate.touch()
    subprocess.run([native_writer, str(source), str(candidate)], check=True, capture_output=True)
    raw = candidate.read_bytes()
    assert raw != objects[0].raw
    assert ole_fingerprint(str(source)) == ole_fingerprint(str(candidate))
    rewritten = CompoundFile(
        compound_bytes(
            ppt_embedded_streams(
                [zlib.compress(raw, 9), objects[1].encoded], [len(raw), len(objects[1].raw)]
            )
        )
    )
    before, after = inspect_records(original, budget()), inspect_records(rewritten, budget())
    assert not equal_layouts(before, after)


def test_no_sector_gain_prefers_strict_compaction(tmp_path, native_writer, monkeypatch):
    import filerepack.ole_recompress as module
    import zlib

    source = tmp_path / "source.ppt"
    shutil.copyfile(CORPUS / "ole2-embedding-2003.ppt", source)
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()

    def zlib_only(layout, bounds):
        document = ppt_embedded_streams([zlib.compress(obj.raw, 9) for obj in layout.objects])
        return document[DOCUMENT], document[CURRENT], ["zlib9", "zlib9"]

    monkeypatch.setattr(module, "reencode", zlib_only)
    info = operate(
        "ppt-ole", "rewrite", str(source), str(candidate), {"ole_writer": native_writer}, budget()
    )
    assert info["verify"] == "ole" and info["details"]["additional_savings_bytes"] == 0
    assert ole_fingerprint(str(source)) == ole_fingerprint(str(candidate))
