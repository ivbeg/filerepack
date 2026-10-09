"""Real OLE no-op/skip reasons survive the API, CLI and bulk worker boundary."""

import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest
from test.helpers import separated_cli_runner

from filerepack import FileRepacker, RepackOptions, ole
from filerepack.__main__ import app
from filerepack.jobs import process_file_job
from filerepack.ole_art_layout import inspect_art
from filerepack.format_support import Budget, FormatLimits
from filerepack.ole_ppt import read_records
from filerepack.ole_verify import read_compound
from filerepack.ole_word_art import DATA, WORD
from test.ole_art_fixtures import container
from test.ole_fixtures import CORPUS
from test.test_ole import bloated, native_writer as _native_writer

native_writer = _native_writer


def source_file(tmp_path, name="simple.doc"):
    source = tmp_path / name
    shutil.copyfile(CORPUS / name, source)
    return source


@pytest.mark.parametrize("mode", ["normal", "dryrun", "minimum"])
def test_measured_rejection_reason_retains_source(tmp_path, native_writer, mode):
    source = source_file(tmp_path)
    if mode == "minimum":
        source.write_bytes(bloated())
    before = source.read_bytes()
    options = {"dryrun": mode == "dryrun", "min_savings": 99.99 if mode == "minimum" else None}
    result = ole.pack_ole(str(source), **options)
    assert result is not None and not result.replaced and source.read_bytes() == before
    if mode == "minimum":
        assert "below the required 99.99%" in result.reason
    else:
        assert "No size reduction" in result.reason and "verified candidate" in result.reason
        assert "live document streams, text and images are retained" in result.reason


@pytest.mark.parametrize("missing", ["reader", "writer"])
def test_dependency_reason_reaches_library_and_job(tmp_path, monkeypatch, missing):
    source = source_file(tmp_path)
    before = source.read_bytes()
    if missing == "reader":
        monkeypatch.setitem(sys.modules, "olefile", None)
        expected = "filerepack[ole]"
    else:
        monkeypatch.setattr(ole, "resolve_tool", lambda key: None)
        expected = "filerepack-ole writer is unavailable"
    summary = FileRepacker().repack(str(source), options=RepackOptions(dryrun=True))
    assert len(summary.results) == 1 and expected in summary.results[0].reason
    result = process_file_job({"filepath": str(source), "dryrun": True})
    assert expected in result["reason"] and result["details"]["strategy"] == "unchanged"
    assert source.read_bytes() == before


def test_protection_reason_reaches_json(tmp_path):
    source = source_file(tmp_path, "PasswordProtected.doc")
    result = separated_cli_runner().invoke(app, ["repack", str(source), "--dryrun", "--json"])
    assert result.exit_code == 0, result.output
    record = json.loads(result.stdout)["files"][0]
    assert "Encrypted/obfuscated Word" in record["reason"]
    assert record["details"]["strategy"] == "unchanged"


@pytest.mark.parametrize("flags", [[], ["--debug"], ["--log-file"]])
def test_verbose_prints_actual_strategy_and_doc_scope(tmp_path, native_writer, flags):
    source = source_file(tmp_path)
    log = tmp_path / "operation.log"
    extra = flags + ([str(log)] if flags == ["--log-file"] else [])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "filerepack",
            "repack",
            str(source),
            "--dryrun",
            "--verbose",
            "--no-progress",
            "--ole-recompress",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "would remain unchanged" in result.stdout
    assert "[SUCCESS] [DRYRUN] File" in result.stdout
    assert "Info: No size reduction" in result.stdout
    assert "Strategy: ole-compaction" in result.stdout
    assert "OfficeArt: no inline picture Data stream" in result.stdout
    if flags == ["--log-file"]:
        assert "Info: No size reduction" in log.read_text()


@pytest.mark.parametrize("name", ["fdo66692-2.doc", "tdf131707_flyWrap.doc"])
def test_verbose_explains_doc_raster_savings_below_one_sector(
    tmp_path, native_writer, monkeypatch, name
):
    extended = Path(__file__).parent / "fixtures" / "ole_extended"
    source = tmp_path / name
    original = (extended / name).read_bytes()
    source.write_bytes(original)
    # Refiltering now saves a complete sector on these fixtures. Keep this
    # no-benefit diagnostic control on the verified exact-filtered fallback.
    monkeypatch.setenv("FILEREPACK_OXIPNG", str(tmp_path / "missing-optional-oxipng"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "filerepack",
            "repack",
            str(source),
            "--dryrun",
            "--verbose",
            "--no-progress",
            "--ole-recompress",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert (
        "OfficeArt stream savings do not improve the selected physical file size" in result.stdout
    )
    assert "OfficeArt rasters: 1 PNG/JPEG payloads, 1 recompressed" in result.stdout
    assert "Strategy: ole-compaction" in result.stdout
    assert source.read_bytes() == original


def test_missing_writer_reason_visible_in_verbose(tmp_path, monkeypatch):
    source = source_file(tmp_path)
    monkeypatch.setattr(ole, "resolve_tool", lambda key: None)
    # Keep the test runner's logging handlers intact; exercise an actual CLI
    # process for log configuration in the other tests.
    result = separated_cli_runner().invoke(app, ["repack", str(source), "--dryrun", "--verbose"])
    assert result.exit_code == 1 and "Error: filerepack-ole writer is unavailable" in result.stdout
    assert "[ERROR]" in result.stderr
    assert "[SUCCESS]" not in result.output


def test_macro_workbook_no_savings_is_explicit_success(tmp_path, native_writer):
    source = source_file(tmp_path, "SquareMacro.xls")
    original = source.read_bytes()
    result = separated_cli_runner().invoke(
        app, ["repack", str(source), "--dryrun", "--ole-recompress", "--verbose"],
    )
    assert result.exit_code == 0, result.output
    assert "[SUCCESS] [DRYRUN] File" in result.stdout
    assert "Info: No size reduction" in result.stdout
    assert "Record recompression skipped: OfficeArt: host macros are not qualified" in result.stdout
    assert "[ERROR]" not in result.output
    assert source.read_bytes() == original


@pytest.mark.parametrize("jobs", ["1", "2"])
def test_bulk_worker_reason_is_visible(tmp_path, native_writer, jobs):
    source = source_file(tmp_path)
    before = source.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "filerepack",
            "bulk",
            str(tmp_path),
            "--dryrun",
            "--verbose",
            "--include-ext",
            "doc",
            "--jobs",
            jobs,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Info: No size reduction" in result.stdout
    assert "[SUCCESS] [DRYRUN] Bulk processing completed." in result.stdout
    assert "Strategy: ole-compaction" in result.stdout
    assert source.read_bytes() == before


def test_json_remains_parseable_and_quiet_suppresses_details(tmp_path, native_writer):
    source = source_file(tmp_path)
    base = [sys.executable, "-m", "filerepack", "repack", str(source), "--dryrun", "--no-progress"]
    result = subprocess.run(
        base + ["--json", "--verbose"], capture_output=True, text=True, check=True
    )
    record = json.loads(result.stdout)["files"][0]
    assert "No size reduction" in record["reason"]
    assert record["details"]["strategy"] == "ole-compaction"
    result = subprocess.run(
        base + ["--quiet", "--verbose"], capture_output=True, text=True, check=True
    )
    assert not result.stdout


def test_missing_executable_retains_reason_in_json(tmp_path):
    source = source_file(tmp_path)
    environment = {**os.environ, "FILEREPACK_OLE_COMPACTOR": str(tmp_path / "missing-writer")}
    result = subprocess.run(
        [sys.executable, "-m", "filerepack", "repack", str(source), "--dryrun", "--json"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "writer is unavailable" in json.loads(result.stdout)["files"][0]["reason"]


@pytest.mark.parametrize("family", ["word", "fopt", "record-type", "record-version"])
@pytest.mark.parametrize("command", ["repack", "bulk"])
def test_unknown_property_code_survives_isolated_worker_and_cli(
    tmp_path, native_writer, family, command
):
    compound = read_compound(str(CORPUS / "vector_image.doc"))
    layout = inspect_art(compound, Budget(FormatLimits())).adapter
    streams = dict(compound.streams)
    if family == "word":
        stream, code = WORD, 0xFFFF
        field = next(iter(layout.refs)) - 2
        assert struct.unpack_from("<H", streams[stream], field)[0] == 0x6A03
        expected = "unsupported Word property: 0xffff"
    else:
        stream, code = DATA, 0x3FFF
        start, prefix, records = layout.blocks[0]
        shape = records[0]
        assert shape.kind == 0xF004
        record_at = start + len(prefix) + next(
            at for at, record in read_records(shape.original()).items() if record.kind == 0xF00B
        )
        field = record_at + 8
        expected = "unsupported FOPT property: 0x3fff"
        if family == "record-type":
            field, code = record_at + 2, 0xF123
            expected = "unsupported OfficeArt type/version: 0xf123, version 3"
        elif family == "record-version":
            field = record_at
            code = (struct.unpack_from("<H", streams[stream], field)[0] & ~15) | 4
            expected = "unsupported OfficeArt type/version: 0xf00b, version 4"
    data = bytearray(streams[stream])
    struct.pack_into("<H", data, field, code)
    streams[stream] = bytes(data)
    source = tmp_path / "unknown.doc"
    original = container(compound, streams)
    source.write_bytes(original)
    extra = ["--no-progress"] if command == "repack" else ["--jobs", "2"]
    base = [
        sys.executable, "-m", "filerepack", command,
        str(source if command == "repack" else tmp_path),
        "--ole-recompress", "--dryrun", *extra,
    ]
    result = subprocess.run(base + ["--json"], capture_output=True, text=True, check=True)
    details = json.loads(result.stdout)["files"][0]["details"]
    assert expected in details["officeart_skip"]
    assert "Word inline pictures:" in details["officeart_skip"]
    assert "Word floating pictures:" in details["officeart_skip"]
    assert details["officeart_skip"] == details["recompression_skip"]
    verbose = subprocess.run(base + ["--verbose"], capture_output=True, text=True, check=True)
    assert verbose.stdout.count(expected) == 1
    assert "Record recompression skipped:" in verbose.stdout
    assert "OfficeArt fallback:" not in verbose.stdout
    assert source.read_bytes() == original


def test_word_diagnostics_distinguish_unsupported_and_duplicate_references():
    from filerepack.ole_word_art import CHAR, TABLE, properties

    with pytest.raises(ValueError, match="unsupported Word property: 0xd6ff"):
        properties(struct.pack("<H", 0xD6FF), 0, TABLE)
    picture_location = struct.pack("<HI", 0x6A03, 0)
    with pytest.raises(ValueError, match="duplicate Word reference property: 0x6a03"):
        properties(picture_location * 2, 0, CHAR)
    # Repeated non-reference formatting is legitimate; the final operand wins.
    formatting = struct.pack("<HHHH", 0x4A43, 20, 0x4A43, 24)
    assert properties(formatting, 0, CHAR)[0x4A43][1] == b"\x18\0"


@pytest.mark.parametrize(
    "codes,expected",
    [
        ([0xC186], "unsupported FOPT property: 0x186"),
        ([0xBF, 0xBF], "duplicate/out-of-order FOPT property: 0xbf"),
        ([0x104, 0xBF], "duplicate/out-of-order FOPT property: 0xbf"),
    ],
)
def test_fopt_diagnostics_distinguish_unsupported_and_invalid_order(codes, expected):
    from filerepack.ole_officeart import Parser, header

    body = b"".join(struct.pack("<HI", code, 0) for code in codes)
    record = header((len(codes) << 4) | 3, 0xF00B, body)
    with pytest.raises(ValueError, match=expected):
        Parser(Budget(FormatLimits())).sequence(record)
