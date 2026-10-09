"""Generated animation hosts, immutable-byte and unsafe-storage-alias controls."""

import json
import struct

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.format_support import Budget, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_extensions import _blob
from filerepack.ole_ppt_records import _persist, inspect_records
from filerepack.ole_ppt_storage import storage_diagnostics
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


def animation(*, flags=0x4400, sound=0, delay=0, order=2, effect=3, duplicate=False):
    body = struct.pack("<IIIihH6B2s", 0x07000000, flags, sound, delay, order, 1,
                       1, effect, 0, 0, 0, 0, b"\xc2\x81")
    atom = record(15, 4116, record(1, 4081, body))
    return record(15, 61457, atom * (2 if duplicate else 1))


def timing(*, shape=77, set_behavior=False, string=None, condition=True):
    visual = record(15, 61756, record(0, 11003, struct.pack("<5I", 0, 1, shape,
                                                        0xFFFFFFFF, 0xFFFFFFFF)))
    behavior = record(0, 61747, struct.pack("<4I", 4 if set_behavior else 0, 0, 0, 0))
    if set_behavior:
        behavior += record(31, 61758, record(0, 61762,
                           b"\3" + "style.visibility\0".encode("utf-16le")))
    behavior = record(15, 61738, behavior + visual)
    text = string or ("visible" if set_behavior else "checkerboard(across)")
    effect = record(0, 61754 if set_behavior else 61750,
                    struct.pack("<2I", 1, 1) if set_behavior else struct.pack("<2I", 3, 0))
    effect += record(16, 61762, b"\3" + (text + "\0").encode("utf-16le")) + behavior
    root = record(0, 61735, b"\0" * 32)
    root += record(15, 61757, b"".join(record(i << 4, 61762, b"\1" + struct.pack("<I", 1))
                                    for i in (9, 10, 11, 20)))
    if condition:
        root += record(31, 61733, record(0, 61736, b"\0" * 16))
    root += record(15, 61745 if set_behavior else 61741, effect)
    return record(31, 61764, root)


def host(**kwargs):
    return presentation(
        slide_shape_extra=record(2, 61450, struct.pack("<II", 77, 0)) + animation(),
        slide_extra=record(15, 5000, tag("___PPT10", timing(**kwargs))),
    )


def changed(source, data):
    return CompoundFile(compound_bytes({**source.streams, DOCUMENT: bytes(data)}))


@pytest.mark.parametrize("set_behavior", [False, True])
def test_animation_and_timing_png_rewrite_preserves_every_immutable_byte(set_behavior):
    source = host(set_behavior=set_behavior)
    before = inspect_art(source, budget())
    replacements, details = before.reencode(budget())
    after = inspect_art(CompoundFile(compound_bytes({**source.streams, **replacements})), budget())
    assert equal_art(before, after) and details["recompressed_rasters"] == 2
    for p, r in read_records(source.streams[DOCUMENT]).items():
        if r.kind in (4116, 4081, 5000, 4113, 1008):
            end = p + 8 + r.size
            assert source.streams[DOCUMENT][p:end] == replacements[DOCUMENT][p:end]
    with pytest.raises(ValueError, match="unqualified record type/version"):
        inspect_records(source, budget())


@pytest.mark.parametrize("kwargs", [
    {"flags": 0x10}, {"flags": 2}, {"flags": 0x10000}, {"sound": 1},
    {"flags": 4, "delay": -1}, {"order": -3}, {"effect": 4}, {"duplicate": True},
])
def test_unknown_sound_flags_effect_or_duplicate_animation_rejected(kwargs):
    source = presentation(slide_shape_extra=animation(**kwargs))
    with pytest.raises(ValueError, match="animation"):
        inspect_art(source, budget())


@pytest.mark.parametrize("fault", ["atom-version", "atom-instance", "atom-length",
                                   "container-version", "container-instance", "owner"])
def test_bad_animation_header_and_owner_rejected(fault):
    source = host()
    data = bytearray(source.streams[DOCUMENT])
    records = read_records(data)
    kind = 4081 if fault.startswith("atom") else 4116
    p = next(p for p, r in records.items() if r.kind == kind)
    if fault.endswith("version"):
        struct.pack_into("<H", data, p, records[p].flags ^ 1)
    elif fault.endswith("instance"):
        struct.pack_into("<H", data, p, records[p].flags | 16)
    elif fault.endswith("length"):
        struct.pack_into("<I", data, p + 4, 27)
    else:
        struct.pack_into("<H", data, records[p].parent + 2, 61453)
    with pytest.raises(ValueError):
        inspect_art(changed(source, data), budget())


def test_animation_must_belong_to_live_page_shape():
    source = presentation(drawing_group_extra=record(15, 61444, animation()))
    with pytest.raises(ValueError, match="animation container"):
        inspect_art(source, budget())


@pytest.mark.parametrize("kwargs", [{"shape": 999}, {"string": "unsafe-effect"}])
def test_timing_must_resolve_live_shape_and_audited_string(kwargs):
    with pytest.raises(ValueError, match="PPT10"):
        inspect_art(host(**kwargs), budget())


@pytest.mark.parametrize("fault", ["zero", "duplicate", "outside-shape"])
def test_visual_target_needs_unique_shape_owned_id(fault):
    source = host()
    data = bytearray(source.streams[DOCUMENT])
    records = read_records(data)
    pos = next(p for p, r in records.items() if r.kind == 61450)
    if fault == "zero":
        struct.pack_into("<I", data, pos + 8, 0)
    elif fault == "outside-shape":
        struct.pack_into("<H", data, records[pos].parent + 2, 61443)
    else:
        source = presentation(
            slide_shape_extra=record(2, 61450, struct.pack("<II", 77, 0)) * 2 + animation(),
            slide_extra=record(15, 5000, tag("___PPT10", timing())),
        )
        data = bytearray(source.streams[DOCUMENT])
    with pytest.raises(ValueError):
        inspect_art(changed(source, data), budget())


@pytest.mark.parametrize("kind,delta", [(61741, 0), (61745, 0), (61738, 0), (61747, 8),
                                       (61750, 8), (61754, 8), (61758, 0), (61762, 0),
                                       (11003, 8), (61733, 0), (61756, 0)])
def test_new_timing_headers_flags_and_fields_fail_closed(kind, delta):
    data = bytearray(timing(set_behavior=kind in (61745, 61754, 61758)))
    pos = next(p for p, r in read_records(data).items() if r.kind == kind)
    data[pos + delta] ^= 1
    with pytest.raises(ValueError):
        _blob(bytes(data), "___PPT10", 1006, budget(), {77})


@pytest.mark.parametrize("offset", [8, 12, 24, 34])
def test_qualified_animation_mutations_still_fail_independent_equality(offset):
    source = host()
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    data = bytearray(replacements[DOCUMENT])
    pos = next(p for p, r in read_records(data).items() if r.kind == 4081)
    data[pos + offset] ^= 1
    try:
        after = inspect_art(CompoundFile(compound_bytes({**source.streams, **replacements,
                                                       DOCUMENT: bytes(data)})), budget())
    except ValueError:
        return
    assert not equal_art(before, after)


def test_aliased_storage_offsets_still_rejected_and_exact_duplicates_only_reported():
    source = presentation()
    data = source.streams[DOCUMENT]
    records = read_records(data)
    directory = next(p for p, r in records.items() if r.kind == 6002)
    wrapper = next(data[p:p + 8 + r.size] for p, r in records.items() if r.kind == 4113)
    diagnostic = storage_diagnostics(data[:directory] + wrapper + data[directory:], budget())
    assert diagnostic["ppt_storage_count"] == 2
    assert diagnostic["ppt_duplicate_wrapper_bytes"] == len(wrapper)
    assert "distinct persist IDs" in diagnostic["storage_sharing_skip"]
    assert not storage_diagnostics(data, budget())
    index = record(0, 6002, struct.pack("<III", 0x200001, 0, 0))
    alias = data[:directory] + index
    rr = read_records(alias)
    with pytest.raises(ValueError, match="ambiguous/invalid persist target"):
        _persist(alias, rr, directory, 2)


@pytest.mark.parametrize("extension", ["ppt", "pot", "pps"])
def test_native_animated_host_dryrun_output_and_verifier(tmp_path, native_writer, extension):
    source = tmp_path / ("source." + extension)
    source.write_bytes(host().data)
    raw = source.read_bytes()
    dryrun = CliRunner().invoke(app, ["repack", str(source), "--dryrun",
                                    "--ole-recompress", "--json"])
    assert dryrun.exit_code == 0, dryrun.output
    details = json.loads(dryrun.stdout)["files"][0]["details"]
    assert details["strategy"] == "ole-officeart-recompression"
    output = tmp_path / ("candidate." + extension)
    result = FileRepacker().repack(str(source), outfile=str(output),
                                 options=RepackOptions(ole_recompress=True))
    assert result.results and output.stat().st_size < source.stat().st_size
    assert verify_preservation(str(source), str(output), "officeart")
    assert source.read_bytes() == raw


def test_parent_image_policy_and_malformed_animation_retain_compaction(tmp_path, native_writer):
    from filerepack.ole_recompress import operate

    for enabled in (False, True):
        source = tmp_path / (str(enabled) + ".ppt")
        original = host() if not enabled else presentation(slide_shape_extra=animation(sound=9))
        source.write_bytes(original.data)
        candidate = tmp_path / (str(enabled) + "-candidate.ppt")
        candidate.touch()
        info = operate("ppt-ole", "rewrite", str(source), str(candidate),
                       {"ole_writer": native_writer, "pack_images": enabled}, budget())
        assert info["verify"] == "ole"
        assert CompoundFile(candidate.read_bytes()).manifest == original.manifest


def test_animation_without_additional_sector_savings_keeps_strict_compaction(
    tmp_path, native_writer,
):
    from filerepack.ole_recompress import operate

    original = host()
    replacements, _ = inspect_art(original, budget()).reencode(budget())
    source = tmp_path / "optimized.ppt"
    source.write_bytes(compound_bytes({**original.streams, **replacements}))
    raw = source.read_bytes()
    candidate = tmp_path / "candidate.ppt"
    candidate.touch()
    info = operate("ppt-ole", "rewrite", str(source), str(candidate),
                   {"ole_writer": native_writer}, budget())
    assert info["verify"] == "ole"
    assert CompoundFile(candidate.read_bytes()).manifest == CompoundFile(raw).manifest
    assert source.read_bytes() == raw
