"""OLE compaction safety, profile, allocator and native writer qualification."""

import hashlib
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack import ole
from filerepack.ole_verify import CompoundFile, END, FREE, ole_fingerprint, read_compound
from test.ole_fixtures import CORPUS, SAMPLES, compound_bytes


@pytest.fixture
def native_writer(monkeypatch):
    writer = os.environ.get("FILEREPACK_OLE_COMPACTOR") or shutil.which("filerepack-ole")
    if not writer:
        pytest.skip("Build/install filerepack-ole to run native qualification")
    assert Path(writer).is_file(), "Configured OLE writer must exist"
    monkeypatch.setenv("FILEREPACK_OLE_COMPACTOR", writer)
    return writer


def bloated(profile="doc", **kwargs):
    return compound_bytes(
        read_compound(str(CORPUS / SAMPLES[profile])).streams,
        free_sectors=80,
        mini_gaps=5,
        **kwargs,
    )


def test_corpus_provenance():
    for entry in json.loads((CORPUS / "provenance.json").read_text())["files"]:
        data = (CORPUS / entry["name"]).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]


@pytest.mark.parametrize(
    "extension,profile",
    [(ext, host) for ext, host in ole.OLE_EXTENSIONS.items() if host in SAMPLES],
)
def test_all_aliases_compact_real_streams(tmp_path, native_writer, extension, profile):
    source = tmp_path / ("document." + extension)
    source.write_bytes(bloated(profile))
    before = ole_fingerprint(str(source))
    estimate = ole.inspect_ole(str(source))
    assert estimate.eligible and estimate.profile == profile
    assert estimate.free_sector_bytes == 80 * 512
    result = ole.pack_ole(str(source))
    assert result is not None and result.replaced and result.savings_bytes >= 80 * 512
    assert ole_fingerprint(str(source)) == before


@pytest.mark.parametrize(
    "filename",
    [
        "simple.doc",
        "Simple.xls",
        "SampleSS.xls",
        "SampleShow.ppt",
        "PngPicture.doc",
        "word_with_embeded.doc",
        "SimpleWithFormula.xls",
        "WithChart.xls",
        "ole2-embedding-2003.ppt",
        "SimpleMacro.doc",
        "HeaderWithMacros.doc",
        "SimpleMacro.xls",
        "SquareMacro.xls",
        "WithEmbeddedObjects.xls",
        "external_name.xls",
        "SimpleMacro.ppt",
    ],
)
def test_real_originals_are_preserved(tmp_path, native_writer, filename):
    source = tmp_path / filename
    shutil.copyfile(CORPUS / filename, source)
    assert ole.inspect_ole(str(source)).eligible
    before = ole_fingerprint(str(source))
    original = source.read_bytes()
    result = ole.pack_ole(str(source))
    assert result is not None and ole_fingerprint(str(source)) == before
    if not result.replaced:
        assert source.read_bytes() == original


@pytest.mark.parametrize(
    "filename,reason",
    [
        ("PasswordProtected.doc", "Encrypted"),
        ("password.xls", "FilePass"),
        ("Password_Protected-hello.ppt", "Encrypted"),
        ("pictures_escher.doc", "allocation fields"),
    ],
)
def test_real_unsupported_documents_skip_before_writer(
    tmp_path, monkeypatch, caplog, filename, reason
):
    source = tmp_path / filename
    shutil.copyfile(CORPUS / filename, source)
    original = source.read_bytes()
    monkeypatch.setattr(ole, "resolve_tool", lambda name: pytest.fail("Writer reached"))
    assert not ole.inspect_ole(str(source)).eligible
    result = ole.pack_ole(str(source))
    assert result is not None and not result.replaced and result.reason
    assert reason in caplog.text and source.read_bytes() == original


def test_complete_metadata_thresholds_and_unknown_objects(tmp_path, native_writer):
    streams = read_compound(str(CORPUS / "simple.doc")).streams
    streams.update(
        {
            ("Папка", "empty"): b"",
            ("Папка", "63"): b"a" * 63,
            ("Папка", "64"): b"b" * 64,
            ("Папка", "65"): b"c" * 65,
            ("Папка", "4095"): b"d" * 4095,
            ("Папка", "4096"): b"e" * 4096,
            ("Папка", "4097"): b"f" * 4097,
            ("\x01opaque",): b"private payload",
        }
    )
    # Include sub-second FILETIMEs, CLSIDs, state bits, an empty storage and property sets.
    metadata = (bytes(range(16)), 0xD1003456, 132999999999999999, 133000000000000001)
    source = tmp_path / "metadata.doc"
    source.write_bytes(
        compound_bytes(
            streams,
            storages={("Папка",): metadata, ("empty storage",): metadata},
            root=(bytes(range(16)), 42, metadata[2], metadata[3]),
            free_sectors=100,
            mini_gaps=3,
        )
    )
    before = ole_fingerprint(str(source))
    result = ole.pack_ole(str(source))
    assert result is not None and result.replaced
    assert ole_fingerprint(str(source)) == before


@pytest.mark.parametrize("profile", ["doc", "xls", "ppt"])
@pytest.mark.parametrize("mode", ["compact", "records", "embedded", "dryrun"])
def test_nonzero_root_filetimes_survive_native_pipeline(tmp_path, native_writer, profile, mode):
    created, modified = 133827851172139529, 134359509521350001
    original = bloated(profile, root=(bytes(range(16)), 42, created, modified))
    source = tmp_path / ("root-times." + profile)
    source.write_bytes(original)
    assert ole.inspect_ole(str(source)).eligible
    before = ole_fingerprint(str(source))
    root = next(entry for entry in before.entries if not entry.path)
    assert (root.created, root.modified) == (created, modified)
    result = ole.pack_ole(
        str(source),
        ole_recompress=mode in ("records", "dryrun"),
        ole_embedded_recompress=mode == "embedded",
        dryrun=mode == "dryrun",
    )
    assert result is not None and result.savings_bytes > 0
    assert ole_fingerprint(str(source)) == before
    if mode == "dryrun":
        assert not result.replaced and source.read_bytes() == original
    else:
        assert result.replaced


def test_extended_difat(tmp_path, native_writer):
    streams = read_compound(str(CORPUS / "simple.doc")).streams
    streams[("large unknown",)] = b"x" * (8 * 1024 * 1024)
    source = tmp_path / "large.doc"
    source.write_bytes(compound_bytes(streams, free_sectors=80))
    assert struct.unpack_from("<I", source.read_bytes(), 72)[0] > 0
    before = ole_fingerprint(str(source))
    assert ole.pack_ole(str(source)).replaced
    assert ole_fingerprint(str(source)) == before


@pytest.mark.parametrize(
    "fault",
    [
        "fat-cycle",
        "overlap",
        "mini-cycle",
        "orphan",
        "tree-cycle",
        "order",
        "consecutive-red",
        "name",
        "truncated",
        "version",
        "allocation",
    ],
)
def test_bad_allocation_or_directory_is_refused(fault):
    original = compound_bytes(
        {("alpha",): b"a" * 4096, ("bravo",): b"b" * 4096, ("tiny",): b"s" * 200}, free_sectors=1
    )
    parsed = CompoundFile(original)
    data = bytearray(original)
    fat_sid = struct.unpack_from("<I", data, 76)[0]
    fat_offset = (fat_sid + 1) * 512
    dir_sid = struct.unpack_from("<I", data, 48)[0]
    directory = (dir_sid + 1) * 512
    index = {entry.name: n for n, entry in enumerate(parsed.directory)}
    alpha, bravo, tiny = (index[name] for name in ("alpha", "bravo", "tiny"))
    start = parsed.directory[alpha].start
    if fault == "fat-cycle":
        struct.pack_into("<I", data, fat_offset + start * 4, start)
    elif fault == "overlap":
        struct.pack_into("<I", data, directory + bravo * 128 + 116, start)
    elif fault == "mini-cycle":
        mini_offset = (struct.unpack_from("<I", data, 60)[0] + 1) * 512
        struct.pack_into(
            "<I", data, mini_offset + parsed.directory[tiny].start * 4, parsed.directory[tiny].start
        )
    elif fault == "orphan":
        struct.pack_into("<I", data, directory + 76, FREE)
    elif fault == "tree-cycle":
        struct.pack_into("<I", data, directory + alpha * 128 + 68, alpha)
    elif fault == "order":
        # Replace alpha's name with a different name on the wrong side of its parent.
        data[directory + alpha * 128 : directory + alpha * 128 + 10] = "zebra".encode("utf-16le")
    elif fault == "consecutive-red":
        # alpha has a live child; both red color bytes violate the MS-CFB tree rule.
        child = parsed.directory[alpha].left
        assert child != FREE
        data[directory + alpha * 128 + 67] = 0
        data[directory + child * 128 + 67] = 0
    elif fault == "name":
        data[directory + alpha * 128 : directory + alpha * 128 + 2] = b"/\0"
    elif fault == "truncated":
        data = data[:-1]
    elif fault == "version":
        struct.pack_into("<H", data, 26, 4)
    else:
        unused = next(sid for sid in range(parsed.sectors) if sid not in parsed.owners)
        struct.pack_into("<I", data, fat_offset + unused * 4, END)
    with pytest.raises(ValueError):
        CompoundFile(bytes(data))


@pytest.mark.parametrize(
    "name", ["\x05DigitalSignature", "EncryptionInfo", "EncryptedPackage", "\x06DataSpaces", "VBA"]
)
def test_unknown_protection_is_not_qualified(tmp_path, name):
    streams = read_compound(str(CORPUS / "simple.doc")).streams
    streams[(name,)] = b"opaque"
    source = tmp_path / "source.doc"
    source.write_bytes(compound_bytes(streams))
    assert not ole.inspect_ole(str(source)).eligible


@pytest.mark.parametrize("profile", ["doc", "xls", "ppt"])
def test_truncated_application_profile(tmp_path, profile):
    streams = read_compound(str(CORPUS / SAMPLES[profile])).streams
    key = {"doc": ("WordDocument",), "xls": ("Workbook",), "ppt": ("PowerPoint Document",)}
    streams[key[profile]] = streams[key[profile]][:24]
    source = tmp_path / ("source." + profile)
    source.write_bytes(compound_bytes(streams))
    assert not ole.inspect_ole(str(source)).eligible


@pytest.mark.parametrize(
    "fault",
    [
        "bytes",
        "metadata",
        "root-clsid",
        "root-created-time",
        "root-time",
        "missing",
        "reader",
        "short-read",
        "truncated",
        "fail",
        "interrupt",
    ],
)
def test_bad_writer_and_interruption_preserve_source_and_clean_scratch(
    tmp_path, monkeypatch, fault
):
    source = tmp_path / "source.doc"
    created, modified = 133827851172139529, 134359509521350000
    original = bloated(
        storages={("empty",): (b"\0" * 16, 0, 0, 0)},
        root=(b"\0" * 16, 0, created, modified),
    )
    source.write_bytes(original)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr("filerepack.candidates.TEMP_PATH", str(scratch))
    monkeypatch.setattr(ole, "resolve_tool", lambda name: "fake-writer")

    def encode(argv, **kwargs):
        if fault == "interrupt":
            raise KeyboardInterrupt
        if fault == "fail":
            return False
        streams = read_compound(str(source)).streams
        if fault == "bytes":
            streams[("\x05SummaryInformation",)] = b"changed"
        metadata = (b"\0" * 16, 1 if fault == "metadata" else 0, 0, 0)
        storages = {} if fault == "missing" else {("empty",): metadata}
        root = (
            b"\x01" * 16 if fault == "root-clsid" else b"\0" * 16,
            0,
            created + 1 if fault == "root-created-time" else created,
            modified + 1 if fault == "root-time" else modified,
        )
        data = compound_bytes(streams, storages=storages, root=root)
        Path(argv[2]).write_bytes(data[:-1] if fault == "truncated" else data)
        return True

    monkeypatch.setattr(ole, "check_command", encode)
    if fault == "reader":
        import olefile

        original_listdir = olefile.OleFileIO.listdir

        def disagree(reader, **kwargs):
            paths = original_listdir(reader, **kwargs)
            return paths if str(reader.fp.name) == str(source) else paths[1:]

        monkeypatch.setattr(olefile.OleFileIO, "listdir", disagree)
    elif fault == "short-read":
        import olefile

        original_openstream = olefile.OleFileIO.openstream

        def short_read(reader, parts):
            with original_openstream(reader, parts) as stream:
                payload = stream.read()
            return io.BytesIO(payload[:-1])

        monkeypatch.setattr(olefile.OleFileIO, "openstream", short_read)
    if fault == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            ole.pack_ole(str(source))
    else:
        result = ole.pack_ole(str(source))
        assert result is not None and not result.replaced and result.reason
    assert source.read_bytes() == original and not list(scratch.iterdir())


@pytest.mark.parametrize("missing", ["reader", "writer"])
def test_missing_dependencies(tmp_path, monkeypatch, caplog, missing):
    source = tmp_path / "source.doc"
    source.write_bytes(bloated())
    original = source.read_bytes()
    if missing == "reader":
        monkeypatch.setitem(sys.modules, "olefile", None)
    else:
        monkeypatch.setattr(ole, "resolve_tool", lambda name: None)
    result = ole.pack_ole(str(source))
    assert result is not None and not result.replaced and result.reason
    assert source.read_bytes() == original
    assert ("filerepack[ole]" if missing == "reader" else "writer is unavailable") in caplog.text


@pytest.mark.parametrize("dryrun,minimum", [(True, None), (False, 99.99)])
def test_candidate_policies_preserve_source(tmp_path, native_writer, dryrun, minimum):
    source = tmp_path / "source.doc"
    source.write_bytes(bloated())
    original = source.read_bytes()
    result = ole.pack_ole(str(source), dryrun=dryrun, min_savings=minimum)
    assert result is not None and not result.replaced
    assert source.read_bytes() == original


def test_filesystem_metadata_distinct_output_and_backup(tmp_path, native_writer):
    source = tmp_path / "source.doc"
    original = bloated()
    source.write_bytes(original)
    source.chmod(0o640)
    os.utime(source, ns=(1600000000000000000, 1600000000123456789))
    before = source.stat()
    output = tmp_path / "output.doc"
    result = FileRepacker().repack(str(source), outfile=str(output))
    assert result.results and source.read_bytes() == original
    assert ole_fingerprint(str(output)) == ole_fingerprint(str(source))
    assert output.stat().st_mtime_ns == before.st_mtime_ns
    assert stat.S_IMODE(output.stat().st_mode) == stat.S_IMODE(before.st_mode)
    FileRepacker().repack(str(source), options=RepackOptions(backup=True))
    assert Path(str(source) + ".bak").read_bytes() == original
    assert source.stat().st_size < len(original)


def test_nested_archive_uses_same_preservation_contract(tmp_path, native_writer):
    if not (shutil.which("7zz") or shutil.which("7z")):
        pytest.skip("Archive writer unavailable")
    original = bloated("xls")
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("nested/report.xls", original)
        archive.writestr("empty/", b"")
    source = tmp_path / "outer.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("inner.zip", inner.getvalue())
        archive.writestr("unknown.bin", b"keep this exactly")
    FileRepacker().repack(str(source))
    with zipfile.ZipFile(source) as outer:
        assert outer.read("unknown.bin") == b"keep this exactly"
        with zipfile.ZipFile(io.BytesIO(outer.read("inner.zip"))) as archive:
            actual = archive.read("nested/report.xls")
            assert len(actual) < len(original) and archive.read("empty/") == b""
    assert CompoundFile(actual).manifest == CompoundFile(original).manifest


def test_native_writer_refuses_nonempty_destination(tmp_path, native_writer):
    source = tmp_path / "source.doc"
    source.write_bytes(bloated())
    output = tmp_path / "output.doc"
    output.write_bytes(b"prior user bytes")
    result = subprocess.run([native_writer, str(source), str(output)], capture_output=True)
    assert result.returncode != 0 and output.read_bytes() == b"prior user bytes"


@pytest.mark.parametrize("flag", [0x100, 0x8000])
def test_word_protection_flags(tmp_path, flag):
    streams = read_compound(str(CORPUS / "simple.doc")).streams
    fib = bytearray(streams[("WordDocument",)])
    struct.pack_into("<H", fib, 10, struct.unpack_from("<H", fib, 10)[0] | flag)
    streams[("WordDocument",)] = bytes(fib)
    source = tmp_path / "source.doc"
    source.write_bytes(compound_bytes(streams))
    assert "Encrypted/obfuscated" in ole.inspect_ole(str(source)).reason


@pytest.mark.parametrize("limit", ["MAX_BYTES", "MAX_ENTRIES", "MAX_DEPTH"])
def test_structural_resource_limits(monkeypatch, limit):
    import filerepack.ole_verify as validator

    monkeypatch.setattr(
        validator, limit, {"MAX_BYTES": 512, "MAX_ENTRIES": 1, "MAX_DEPTH": 1}[limit]
    )
    data = compound_bytes({("storage", "stream"): b"x" * 5000})
    with pytest.raises(ValueError, match="limit"):
        CompoundFile(data)


def test_unqualified_supplementary_names_are_refused():
    with pytest.raises(ValueError, match="Unicode"):
        CompoundFile(compound_bytes({("😀",): b"bytes"}))


def legacy_root(data):
    result = bytearray(data)
    offset = (struct.unpack_from("<I", result, 48)[0] + 1) * 512
    result[offset : offset + 64] = b"R\0" + b"\0" * 62
    struct.pack_into("<H", result, offset + 64, 2)
    return bytes(result)


def test_legacy_root_has_an_exact_private_canonical_view(tmp_path):
    canonical = bloated("ppt", root=(b"\0" * 16, 0, 133827851172139529, 134359509521350000))
    original = legacy_root(canonical)
    source = tmp_path / "legacy.ppt"
    source.write_bytes(original)
    parsed = read_compound(str(source))
    assert parsed.root_name_normalized and parsed.data == canonical
    assert parsed.manifest == CompoundFile(canonical).manifest
    assert ole_fingerprint(str(source)) == CompoundFile(canonical).manifest
    assert ole.inspect_ole(str(source)).eligible
    assert source.read_bytes() == original
    # The independent reader must still read the provided source, including
    # nested in-memory containers, rather than trusting parsed.data alone.
    from filerepack.ole_verify import independent_manifest

    assert independent_manifest(io.BytesIO(original), parsed) == parsed.manifest
    altered = legacy_root(compound_bytes({("different",): b"bytes"}))
    with pytest.raises(ValueError, match="independent"):
        independent_manifest(io.BytesIO(altered), parsed)


def test_legacy_root_normalization_allocates_only_one_file_copy():
    import tracemalloc

    from filerepack.ole_root import normalize_root_name

    canonical = compound_bytes({("stream",): b"payload"}).ljust(8 * 1024 * 1024, b"\0")
    original = legacy_root(canonical)
    tracemalloc.start()
    try:
        normalized = normalize_root_name(original)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert normalized == canonical
    # Allow small interpreter overhead, but reject a second whole-file buffer.
    assert peak < len(original) + 128 * 1024


@pytest.mark.parametrize("fault", ["length", "name", "type", "link", "metadata", "other-name"])
def test_legacy_root_does_not_hide_other_directory_defects(fault):
    data = bytearray(legacy_root(compound_bytes({("stream",): b"payload"})))
    offset = (struct.unpack_from("<I", data, 48)[0] + 1) * 512
    if fault == "length":
        data[offset + 64] = 3
    elif fault == "name":
        data[offset] = ord("X")
    elif fault == "type":
        data[offset + 66] = 2
    elif fault == "link":
        struct.pack_into("<I", data, offset + 76, 0)
    elif fault == "metadata":
        # Stream FILETIMEs must still be zero; root-name compatibility cannot
        # turn malformed stream metadata into a qualified source.
        struct.pack_into("<Q", data, offset + 128 + 100, 1)
    else:
        # The same anomaly in a live stream is never normalized.
        data[offset + 128 : offset + 192] = b"R\0" + b"\0" * 62
        struct.pack_into("<H", data, offset + 192, 2)
    with pytest.raises(ValueError):
        CompoundFile(bytes(data))


@pytest.mark.parametrize("mode", ["compact", "records", "embedded", "dryrun"])
def test_legacy_root_and_unicode_names_reach_native_pipeline(tmp_path, native_writer, mode):
    streams = read_compound(str(CORPUS / "SampleShow.ppt")).streams
    streams.update({("MsoDataStore", name): b"opaque " + name.encode() for name in ("ß", "T", "ᾀ")})
    canonical = compound_bytes(streams, free_sectors=80)
    original = legacy_root(canonical)
    source = tmp_path / "legacy.ppt"
    source.write_bytes(original)
    before = ole_fingerprint(str(source))
    result = ole.pack_ole(
        str(source),
        ole_recompress=mode == "records",
        ole_embedded_recompress=mode == "embedded",
        dryrun=mode == "dryrun",
    )
    assert result is not None and result.savings_bytes > 0
    if mode == "dryrun":
        assert source.read_bytes() == original and not result.replaced
    else:
        assert result.replaced and not read_compound(str(source)).root_name_normalized
        assert ole_fingerprint(str(source)) == before


@pytest.mark.parametrize("names", [("ᾀ", "ᾈ"), ("A", "a"), ("S", "ſ")])
def test_simple_uppercase_duplicates_are_still_rejected(names):
    with pytest.raises(ValueError, match="duplicate name"):
        CompoundFile(compound_bytes({(name,): b"payload" for name in names}))


def test_read_only_inspection_and_record_bound(tmp_path, monkeypatch):
    source = tmp_path / "source.xls"
    source.write_bytes(bloated("xls"))
    monkeypatch.setattr(ole, "check_command", lambda *args, **kwargs: pytest.fail("Writer reached"))
    assert ole.inspect_ole(str(source)).eligible
    monkeypatch.setattr(ole, "MAX_RECORDS", 1)
    assert "limit" in ole.inspect_ole(str(source)).reason


@pytest.mark.parametrize("payload", [b"{\\rtf1}", b"<html>table</html>", b"\x09\x08BIFF"])
def test_office_suffix_is_insufficient(tmp_path, payload):
    source = tmp_path / "source.xls"
    source.write_bytes(payload)
    assert not ole.inspect_ole(str(source)).eligible


def test_no_images_does_not_disable_document_compaction(tmp_path, native_writer):
    source = tmp_path / "source.doc"
    source.write_bytes(bloated())
    size = source.stat().st_size
    result = FileRepacker().repack(str(source), options=RepackOptions(pack_images=False))
    assert result.results and source.stat().st_size < size
