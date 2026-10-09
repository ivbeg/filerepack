"""Fly-from-bottom timing, text/reference gates and independent mutation controls."""

import json
import struct
from collections import defaultdict

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_extensions import _blob, check_picture_layout_refs
from filerepack.ole_verify import CompoundFile
from filerepack.verification import verify_preservation
from test.ole_fixtures import compound_bytes
from test.ole_ppt_notes_fixtures import presentation, record
from test.test_ole import native_writer as _native_writer
from test.test_ole_ppt_animation import DOCUMENT, budget
from test.test_ole_ppt_notes import tag

native_writer = _native_writer


def string(text, flags=0):
    return record(flags, 61762, b"\3" + (text + "\0").encode("utf-16le"))


def fly_track(axis, *, shape=77):
    frames = b""
    for index, time in enumerate((0, 1000)):
        value = "1+#ppt_h/2" if axis == "ppt_y" and index == 0 else "#" + axis
        frames += record(0, 61763, struct.pack("<I", time)) + string(value) + string("", 16)
    visual = record(15, 61756, record(0, 11003, struct.pack("<5I", 0, 1, shape,
                                                        0xFFFFFFFF, 0xFFFFFFFF)))
    behavior = record(15, 61738, record(0, 61747, struct.pack("<4I", 5, 0, 0, 0))
                      + record(31, 61758, string(axis)) + visual)
    track = record(15, 61739, record(0, 61748, struct.pack("<3I", 1, 0x38, 1))
                   + record(15, 61759, frames) + behavior)
    return record(31, 61764, record(0, 61735, b"\0" * 32) + track)


def fly_animation(*, build=1, effect=12, direction=3, after=0, text=0, verb=0, sound=0):
    body = struct.pack("<IIIihH6B2s", 0x07000000, 0x4400, sound, 0, 2, 1,
                       build, effect, direction, after, text, verb, b"\xc2\x81")
    return record(15, 61457, record(15, 4116, record(1, 4081, body)))


def text_run(numbered=False):
    return (struct.pack("<IHHHH", 0x03800000, 0xFFFF, 1, 3, 1) if numbered
            else struct.pack("<IHH", 0x02800000, 0xFFFF, 0)) + b"\0" * 8


def font_defaults(*, fonts=1):
    level = struct.pack("<IHH", 0x03000000, 0, 0xFFFF)
    return (record(15, 2006, record(0, 4023, b"\0" * 68) * fonts)
            + record(64, 4018, struct.pack("<H", 5) + level * 5) + record(0, 4020, level))


def fly_host(**kwargs):
    shapes = record(2, 61450, struct.pack("<II", 77, 0)) + fly_animation(**kwargs)
    shapes += record(15, 61457, record(15, 5000, tag(
        "___PPT9", record(0, 4012, text_run() + b"\0" * 12 + text_run(True)))))
    return presentation(
        document_info=record(15, 5000, tag("___PPT10", font_defaults())),
        slide_shape_extra=shapes,
        slide_extra=record(15, 5000, tag("___PPT10", fly_track("ppt_x") + fly_track("ppt_y"))),
    )


def changed(source, data, replacements=None):
    return CompoundFile(compound_bytes({**source.streams, **(replacements or {}),
                                       DOCUMENT: bytes(data)}))


def test_fly_host_reencodes_images_and_preserves_every_animation_and_tag_byte():
    source = fly_host()
    before = inspect_art(source, budget())
    replacements, details = before.reencode(budget())
    after = inspect_art(changed(source, replacements[DOCUMENT], replacements), budget())
    assert equal_art(before, after) and details["recompressed_rasters"] == 2
    for p, r in read_records(source.streams[DOCUMENT]).items():
        if r.kind in (1008, 4113, 4116, 4081, 5000):
            end = p + 8 + r.size
            assert source.streams[DOCUMENT][p:end] == replacements[DOCUMENT][p:end]


@pytest.mark.parametrize("kwargs", [
    {"build": 2}, {"effect": 4}, {"direction": 0}, {"direction": 4},
    {"after": 1}, {"text": 1}, {"verb": 1}, {"sound": 1},
])
def test_other_fly_effect_fields_and_sound_still_rejected(kwargs):
    with pytest.raises(ValueError, match="animation"):
        inspect_art(fly_host(**kwargs), budget())


@pytest.mark.parametrize("axis", ["ppt_x", "ppt_y"])
@pytest.mark.parametrize("kind,offset", [
    (61739, 0), (61748, 0), (61748, 8), (61748, 12), (61748, 16),
    (61759, 0), (61763, 0), (61763, 8), (61747, 8), (61747, 12),
    (61762, 0), (61762, 8), (61762, 9), (11003, 16),
])
def test_malformed_fly_headers_values_formulas_or_visual_references_rejected(axis, kind, offset):
    data = bytearray(fly_track(axis))
    pos = next(p for p, r in read_records(data).items() if r.kind == kind)
    data[pos + offset] ^= 1
    with pytest.raises(ValueError):
        _blob(bytes(data), "___PPT10", 1006, budget(), {77})


@pytest.mark.parametrize("fault", ["swapped", "missing", "formula", "axis", "endpoint"])
def test_fly_keyframes_are_checked_together_with_the_coordinate(fault):
    data = bytearray(fly_track("ppt_y"))
    records = read_records(data)
    frames = [p for p, r in sorted(records.items()) if r.kind == 61762 and
              records[r.parent].kind == 61759]
    if fault == "swapped":
        struct.pack_into("<H", data, frames[0], 16)
        struct.pack_into("<H", data, frames[1], 0)
    elif fault == "missing":
        struct.pack_into("<H", data, frames[1] + 2, 61763)
    elif fault == "formula":
        data[frames[1] + 9] = ord("x")
    elif fault == "axis":
        name = next(p for p, r in records.items() if r.kind == 61762 and
                    records[r.parent].kind == 61758)
        data[name + 17] = ord("x")  # ppt_y -> ppt_x while retaining vertical keyframes.
    else:
        times = [p for p, r in sorted(records.items()) if r.kind == 61763]
        struct.pack_into("<I", data, times[1] + 8, 999)
    with pytest.raises(ValueError):
        _blob(bytes(data), "___PPT10", 1006, budget(), {77})


@pytest.mark.parametrize("payload", [b"\0" * 12, text_run(), text_run(True),
                                     text_run() * 3 + b"\0" * 12 + text_run(True)])
def test_ppt9_null_picture_bullet_text_runs_are_bounded(payload):
    _blob(record(0, 4012, payload), "___PPT9", 61457, budget())


@pytest.mark.parametrize("fault", ["reference", "pf-mask", "cf-mask", "si-mask",
                                   "numbering", "truncated", "tail"])
def test_ppt9_unknown_properties_and_live_picture_bullet_refs_rejected(fault):
    payload = bytearray(text_run(True))
    if fault == "truncated":
        payload.pop()
    elif fault == "tail":
        payload.append(0)
    else:
        offset = {"reference": 4, "pf-mask": 0, "cf-mask": 12,
                  "si-mask": 16, "numbering": 8}[fault]
        payload[offset] ^= 1
    with pytest.raises(ValueError, match="PPT9"):
        _blob(record(0, 4012, bytes(payload)), "___PPT9", 61457, budget())


@pytest.mark.parametrize("fault", ["missing-font", "duplicate-font", "levels",
                                   "master-font", "default-font", "owner"])
def test_ppt10_text_defaults_require_audited_fields_and_unique_font_target(fault):
    data = bytearray(font_defaults(fonts=0 if fault == "missing-font" else
                                   2 if fault == "duplicate-font" else 1))
    if fault in ("levels", "master-font", "default-font"):
        records = read_records(data)
        kind = 4020 if fault == "default-font" else 4018
        pos = next(p for p, r in records.items() if r.kind == kind)
        data[pos + (8 if fault == "levels" else 14 if kind == 4018 else 12)] ^= 1
    with pytest.raises(ValueError):
        _blob(bytes(data), "___PPT10", 1006 if fault == "owner" else 2000, budget())


def composite_graph(*, original=1, composite=1, slide=1, instance=1, duplicate=False):
    main = record(15, 1016, record(0, 1052, struct.pack("<I", original))
                  + record(96, 1054, b"PK\3\4main layout"))
    merged = record(15, 1016, record(0, 1053, struct.pack("<I", composite))
                    + record(instance << 4, 1054, b"PK\3\4merged layout"))
    atom = bytearray(24)
    struct.pack_into("<I", atom, 12, 2)
    ref = record(0, 1053, struct.pack("<I", slide))
    page = record(15, 1006, record(2, 1007, bytes(atom)) + ref * (2 if duplicate else 1))
    data = main + merged + page
    records = read_records(data)
    children = defaultdict(list)
    for p, r in sorted(records.items()):
        children[r.parent].append(p)
    check_picture_layout_refs(data, records, children, {3: len(main) + len(merged)},
                              {1: 0, 2: len(main)})


def test_composite_master_and_slide_bind_to_one_live_original_and_layout():
    composite_graph()


@pytest.mark.parametrize("kwargs", [{"original": 0}, {"composite": 9}, {"slide": 9},
                                    {"instance": 6}, {"duplicate": True}])
def test_composite_master_missing_identity_layout_collision_or_bad_slide_rejected(kwargs):
    with pytest.raises(ValueError):
        composite_graph(**kwargs)


@pytest.mark.parametrize("kind,offset", [(4081, 8), (4081, 26), (4081, 34),
                                       (5003, 30), (4113, 8)])
def test_fly_immutable_mutations_cannot_pass_independent_equality(kind, offset):
    source = fly_host()
    before = inspect_art(source, budget())
    replacements, _ = before.reencode(budget())
    data = bytearray(replacements[DOCUMENT])
    records = read_records(data)
    pos = next(p for p, r in records.items() if r.kind == kind)
    data[pos + offset] ^= 1
    try:
        after = inspect_art(changed(source, data, replacements), budget())
    except ValueError:
        return
    assert not equal_art(before, after)


@pytest.mark.parametrize("extension", ["ppt", "pot", "pps"])
def test_native_public_fly_dryrun_output_and_independent_verifier(
    tmp_path, native_writer, extension,
):
    source = tmp_path / ("source." + extension)
    source.write_bytes(fly_host().data)
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


@pytest.mark.parametrize("options", [{"pack_images": False}, {"ole_recompress": False}])
def test_fly_parent_image_policy_and_default_retain_strict_compaction(
    tmp_path, native_writer, options,
):
    source = tmp_path / "source.ppt"
    source.write_bytes(fly_host().data)
    raw = source.read_bytes()
    output = tmp_path / "candidate.ppt"
    FileRepacker().repack(str(source), outfile=str(output),
                         options=RepackOptions(**{"ole_recompress": True, **options}))
    assert CompoundFile(output.read_bytes()).manifest == CompoundFile(raw).manifest
    assert source.read_bytes() == raw
