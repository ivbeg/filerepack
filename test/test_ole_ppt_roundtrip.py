"""Generated round-trip PPT hosts and independent immutable-byte regressions."""

import io
import json
import struct
import zipfile

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.format_support import Budget, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_records import inspect_records
from filerepack.ole_verify import CompoundFile
from filerepack.verification import verify_preservation
from test.ole_fixtures import compound_bytes
from test.ole_ppt_notes_fixtures import presentation, record
from test.test_ole import native_writer as _native_writer
from test.test_ole_ppt_notes import tag

native_writer = _native_writer
DOCUMENT, PICTURES = ("PowerPoint Document",), ("Pictures",)


def budget():
    return Budget(FormatLimits())


def roundtrip(*, notes=True, properties=3, layout=7, master_extra=b"", slide_extra=b"",
              tags=None):
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", '<p:sldLayout xmlns:p="ppt"/>')
    blob = package.getvalue()
    layouts = b"".join(record(i << 4, 1054, blob) for i in range(1, 12))
    props = [(447, 2097184), (540, 63500)][3 - properties:] + [(0xC3A9, len(blob))]
    tertiary = record(properties << 4 | 3, 0xF122,
                      b"".join(struct.pack("<HI", k, v) for k, v in props) + blob)
    if tags is None:
        tags = tag("___PPT9", record(0, 4012, b"\0" * 12))
    return presentation(
        notes=notes, embedded=False,
        drawing_group_extra=record(32, 0xF11A, struct.pack("<2I", 0x2C415, 0x1C943E)),
        master_extra=record(0, 1052, struct.pack("<I", 1)) + layouts + master_extra,
        slide_extra=record(0, 1058, struct.pack("<IHH", 1, layout, 0xABCD)) + slide_extra,
        slide_shape_extra=tertiary + record(15, 0xF011, record(15, 5000, tags)),
    )


def changed(source, data):
    return CompoundFile(compound_bytes({**source.streams, DOCUMENT: bytes(data)}))


@pytest.mark.parametrize("notes", [False, True])
@pytest.mark.parametrize("properties", [1, 2, 3])
def test_roundtrip_host_shrinks_pngs_with_exact_immutable_records(notes, properties):
    source = roundtrip(notes=notes, properties=properties)
    before = inspect_art(source, budget())
    replacements, details = before.reencode(budget())
    after = inspect_art(CompoundFile(compound_bytes({**source.streams, **replacements})), budget())
    assert equal_art(before, after) and details["recompressed_rasters"] == 2
    assert len(replacements[PICTURES]) < len(source.streams[PICTURES])
    data = source.streams[DOCUMENT]
    for pos, item in read_records(data).items():
        if item.kind in (1052, 1054, 1058, 0xF11A, 0xF122, 5000, 1008):
            end = pos + 8 + item.size
            assert data[pos:end] == replacements[DOCUMENT][pos:end]
    # Broader host acceptance never extends compressed embedded-storage selection.
    with pytest.raises(ValueError, match="unqualified record type/version"):
        inspect_records(source, budget())


@pytest.mark.parametrize("layout", range(1, 12))
def test_each_audited_layout_instance_resolves(layout):
    assert inspect_art(roundtrip(layout=layout), budget()).rasters


@pytest.mark.parametrize("fault", [
    "slide-version", "slide-instance", "slide-owner", "slide-length", "master-id",
    "layout-id", "master-identity", "layout-instance", "color-count", "color-version",
    "color-length", "color-owner", "property-count", "property-version", "property-owner",
    "property-tail", "property-order", "property-blip", "shape-client-instance",
    "shape-parent-instance",
])
def test_bad_roundtrip_headers_ids_and_property_bounds_are_rejected(fault):
    source = roundtrip()
    data = bytearray(source.streams[DOCUMENT])
    records = read_records(data)
    kind = (1058 if fault.startswith("slide") or fault in ("master-id", "layout-id")
            else 1052 if fault == "master-identity"
            else 1054 if fault == "layout-instance"
            else 0xF11A if fault.startswith("color")
            else 0xF011 if fault.startswith("shape-") else 0xF122)
    pos = next(p for p, r in records.items() if r.kind == kind)
    if fault.endswith("version"):
        struct.pack_into("<H", data, pos, records[pos].flags ^ 1)
    elif fault == "shape-parent-instance":
        struct.pack_into("<H", data, records[pos].parent, 31)
    elif fault in ("slide-instance", "layout-instance", "color-count", "property-count",
                   "shape-client-instance"):
        flags = {"slide-instance": 16, "layout-instance": 192, "color-count": 48,
                 "property-count": 67, "shape-client-instance": 31}[fault]
        struct.pack_into("<H", data, pos, flags)
    elif fault.endswith("length"):
        struct.pack_into("<I", data, pos + 4, records[pos].size - 1)
    elif fault.endswith("owner"):
        owner = records[pos].parent
        assert owner is not None
        struct.pack_into("<H", data, owner + 2, 1008)
    elif fault in ("master-id", "master-identity", "layout-id"):
        struct.pack_into("<H" if fault == "layout-id" else "<I", data,
                         pos + (12 if fault == "layout-id" else 8), 99)
    elif fault == "property-tail":
        struct.pack_into("<I", data, pos + 22, 999999)
    elif fault == "property-order":
        struct.pack_into("<H", data, pos + 14, 1)
    elif fault == "property-blip":
        struct.pack_into("<HI", data, pos + 8, 0x4104, 99)
    with pytest.raises(ValueError):
        inspect_art(changed(source, data), budget())


@pytest.mark.parametrize("fault", ["reference", "layout", "master", "identity"])
def test_duplicate_roundtrip_objects_fail_closed(fault):
    source = roundtrip(
        slide_extra=record(0, 1058, struct.pack("<IHH", 1, 7, 0)) if fault == "reference" else b"",
        master_extra={
            "layout": record(112, 1054, b"PK\x03\x04immutable"),
            "master": record(0, 1052, struct.pack("<I", 2)),
            "identity": record(0, 1052, struct.pack("<I", 1)),
        }.get(fault, b""),
    )
    with pytest.raises(ValueError):
        inspect_art(source, budget())


@pytest.mark.parametrize("fault", [
    "name", "record", "version", "instance", "length", "extra-record",
    "paragraph-mask", "character-mask", "special-mask", "duplicate", "ppt10",
])
def test_shape_tags_admit_only_audited_zero_mask_style_run(fault):
    payload = bytearray(12)
    if fault.endswith("mask"):
        at = {"paragraph-mask": 0, "character-mask": 4, "special-mask": 8}[fault]
        payload[at] = 1
    if fault == "length":
        payload += b"\0"
    blob = record(1 if fault == "version" else 16 if fault == "instance" else 0,
                  9999 if fault == "record" else 4012, bytes(payload))
    if fault == "extra-record":
        blob += record(0, 4012, b"\0" * 12)
    name = "___BAD9" if fault == "name" else "___PPT10" if fault == "ppt10" else "___PPT9"
    tags = tag(name, blob)
    if fault == "duplicate":
        tags += tags
    with pytest.raises(ValueError):
        inspect_art(roundtrip(tags=tags), budget())


@pytest.mark.parametrize("kind,offset", [(1058, 14), (1054, 20), (0xF11A, 8),
                                       (0xF122, 10), (4012, 8)])
def test_independent_verifier_rejects_unpermitted_extension_mutations(kind, offset):
    source = roundtrip()
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    data = bytearray(replacements[DOCUMENT])
    if kind == 4012:
        pos = next(p for p, r in read_records(data).items()
                   if r.kind == 5003 and r.size == 20)
        offset += 8
    else:
        pos = next(p for p, r in read_records(data).items() if r.kind == kind)
    data[pos + offset] ^= 1
    mutated = CompoundFile(
        compound_bytes({**source.streams, **replacements, DOCUMENT: bytes(data)})
    )
    try:
        after = inspect_art(mutated, budget())
    except ValueError:
        return
    assert not equal_art(before.identity(), after)


@pytest.mark.parametrize("extension", ["ppt", "pot", "pps"])
def test_native_roundtrip_aliases_dryrun_output_and_independent_verification(
    tmp_path, native_writer, extension,
):
    source = tmp_path / ("source." + extension)
    source.write_bytes(roundtrip().data)
    raw = source.read_bytes()
    dryrun = CliRunner().invoke(app, ["repack", str(source), "--dryrun",
                                    "--ole-recompress", "--json"])
    assert dryrun.exit_code == 0, dryrun.output
    item = json.loads(dryrun.stdout)["files"][0]
    assert item["details"]["strategy"] == "ole-officeart-recompression"
    assert source.read_bytes() == raw
    output = tmp_path / ("candidate." + extension)
    result = FileRepacker().repack(str(source), outfile=str(output),
                                 options=RepackOptions(ole_recompress=True))
    assert result.results and output.stat().st_size < source.stat().st_size
    assert verify_preservation(str(source), str(output), "officeart")
    assert not verify_preservation(str(source), str(output), "ole")
    assert source.read_bytes() == raw


def test_verbose_reports_identical_record_and_picture_gate_once(tmp_path, native_writer):
    source = tmp_path / "unsupported.ppt"
    raw = roundtrip(tags=tag("___BAD9", record(0, 4012, b"\0" * 12))).data
    source.write_bytes(raw)
    result = CliRunner().invoke(app, ["repack", str(source), "--dryrun",
                                    "--ole-recompress", "--verbose"])
    assert result.exit_code == 0, result.output
    assert "Record recompression skipped:" in result.stdout
    assert "Record recompression skipped: PPT OLE records: " in (
        result.stdout
    )
    assert result.stdout.count("PPT OLE records: unknown/duplicate programmable extension") == 1
    assert source.read_bytes() == raw


def test_optimized_roundtrip_without_sector_gain_keeps_strict_compaction(tmp_path, native_writer):
    from filerepack.ole_recompress import operate

    original = roundtrip()
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
