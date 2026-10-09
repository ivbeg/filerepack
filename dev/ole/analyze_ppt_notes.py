"""Read-only corpus study of PPT notes and independent Pictures feasibility.

This does not relax any runtime qualification gate or write a PPT candidate.
Run as: python -m dev.ole.analyze_ppt_notes INPUT... --output REPORT.json
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import struct
import zlib

import olefile

from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole_officeart import BLIPS, Parser
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_records import _VERSIONS, inspect_records
from filerepack.ole_raster import PngData, optimize_png
from filerepack.ole_verify import CompoundFile, read_compound


def digest(data):
    return hashlib.sha256(data).hexdigest()


def analyze(path):  # noqa: C901 -- development-only inventory, not a runtime qualification gate
    before = digest(path.read_bytes())
    compound = read_compound(str(path))
    data = compound.streams[("PowerPoint Document",)]
    records = read_records(data)
    children = defaultdict(list)
    for pos, record in records.items():
        children[record.parent].append(pos)
    top = sorted(children[None])
    issues, deviations = [], []

    def check(condition, reason):
        if not condition:
            issues.append(reason)

    directories = [p for p in top if records[p].kind == 6002]
    assert len(directories) == 1, "Study requires one persist directory"
    directory = directories[0]
    cursor, end = directory + 8, directory + 8 + records[directory].size
    persist = {}
    while cursor < end:
        descriptor = struct.unpack_from("<I", data, cursor)[0]
        first, count = descriptor & 0xFFFFF, descriptor >> 20
        cursor += 4
        assert count and cursor + 4 * count <= end
        for identifier in range(first, first + count):
            assert identifier not in persist
            persist[identifier] = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
    check(len(set(persist.values())) == len(persist), "Aliased persist targets")
    check(set(persist.values()) == set(top) - {directory, top[-1]}, "Unaccounted top objects")

    lists = defaultdict(list)
    for pos, record in records.items():
        if record.kind == 1011:
            parent = records[record.parent]
            assert parent.kind == 4080 and record.size == 20
            identifier, flags, reserved1, logical_id, reserved2 = struct.unpack_from(
                "<5I", data, pos + 8
            )
            lists[parent.flags >> 4].append((logical_id, persist[identifier]))
    slides, notes = dict(lists[0]), dict(lists[2])
    check(len(slides) == len(lists[0]), "Duplicate slide IDs")
    check(len(notes) == len(lists[2]), "Duplicate notes IDs")
    document_atom = next(p for p in children[0] if records[p].kind == 1001)
    notes_master_id = struct.unpack_from("<I", data, document_atom + 8 + 24)[0]
    notes_master = persist.get(notes_master_id)
    notes_atoms = {}
    for pos in top:
        record = records[pos]
        if record.kind != 1008:
            continue
        check(record.flags == 15, "NotesContainer header")
        direct = children[pos]
        check([records[p].kind for p in direct[:3]] == [1009, 1036, 2032], "Notes children")
        check(sum(records[p].kind == 1009 for p in direct) == 1, "NotesAtom count")
        atom = direct[0]
        check(records[atom].flags == 1 and records[atom].size == 8, "NotesAtom header")
        slide_id, flags, unused = struct.unpack_from("<IHH", data, atom + 8)
        notes_atoms[pos] = (slide_id, flags, unused)
        if pos == notes_master:
            if slide_id != 0 or flags != 0:
                deviations.append(
                    {
                        "record": "NotesAtom",
                        "offset": atom,
                        "field": "notes-master slideIdRef/slideFlags",
                        "expected": [0, 0],
                        "actual": [slide_id, flags],
                        "observed_legacy_variant": (slide_id, flags) == (0x80000000, 2),
                    }
                )
        else:
            check(slide_id in slides and flags & ~7 == 0, "Notes slideId/flags")
    note_links = []
    for slide_id, pos in slides.items():
        check(records[pos].kind == 1006, "Slide target kind")
        atom = next(p for p in children[pos] if records[p].kind == 1007)
        notes_id = struct.unpack_from("<I", data, atom + 8 + 16)[0]
        target = notes.get(notes_id)
        check(target in notes_atoms, "Missing notesId target")
        check(target in notes_atoms and notes_atoms[target][0] == slide_id, "Notes reverse link")
        note_links.append({"slide_id": slide_id, "notes_id": notes_id, "notes_offset": target})
    check(set(notes_atoms) == set(notes.values()) | {notes_master}, "Unreferenced NotesContainer")
    check(notes_master in notes_atoms and notes_master not in notes.values(), "Notes master role")

    tags = []
    for pos, record in records.items():
        if record.kind != 5002:
            continue
        direct = children[pos]
        assert len(direct) == 2
        name_pos, blob_pos = direct
        name = data[name_pos + 8 : name_pos + 8 + records[name_pos].size].decode("utf-16le")
        blob = data[blob_pos + 8 : blob_pos + 8 + records[blob_pos].size]
        inside = read_records(blob)
        tags.append(
            {
                "offset": pos,
                "name": name,
                "bytes": len(blob),
                "contained_kinds": dict(Counter(r.kind for r in inside.values())),
                "blob_sha256": digest(blob),
            }
        )

    owner_counts, pib_counts = Counter(), Counter()
    for pos, record in records.items():
        if record.kind == 3009:
            owner = pos
            while records[owner].parent is not None:
                owner = records[owner].parent
            owner_counts[records[owner].kind] += 1
        if record.kind == 0xF00B:
            assert (record.flags >> 4) * 6 <= record.size
            for index in range(record.flags >> 4):
                code, value = struct.unpack_from("<HI", data, pos + 8 + index * 6)
                if code == 0x4104:
                    pib_counts[value] += 1

    objects = []
    for pos in top:
        record = records[pos]
        if record.kind != 4113:
            continue
        expected = struct.unpack_from("<I", data, pos + 8)[0]
        assert expected <= 16 * 1024 * 1024
        encoded = data[pos + 12 : pos + 8 + record.size]
        decoder = zlib.decompressobj()
        raw = decoder.decompress(encoded, expected + 1)
        assert len(raw) == expected and decoder.eof
        assert not decoder.unused_data and not decoder.unconsumed_tail
        try:
            CompoundFile(raw)
            strict = "accepted"
        except ValueError as exc:
            strict = str(exc)
        with olefile.OleFileIO(io.BytesIO(raw), raise_defects=olefile.DEFECT_INCORRECT) as nested:
            contents = {"/".join(p): nested.get_size(p) for p in nested.listdir()}
            compobj = nested.openstream(["\x01CompObj"]).read()
            photoshop = b"Adobe Photoshop Image" in compobj
        objects.append(
            {
                "offset": pos,
                "encoded_bytes": len(encoded),
                "decoded_bytes": len(raw),
                "encoded_sha256": digest(encoded),
                "decoded_sha256": digest(raw),
                "zlib9_bytes": len(zlib.compress(raw, 9)),
                "strict_cfb": strict,
                "photoshop_compobj": photoshop,
                "streams": contents,
            }
        )

    # Individual reads avoid retaining all expanded pictures during research.
    # The production aggregate limit is reported below, never raised here.
    parser = Parser(Budget(FormatLimits()), raster=False)
    pictures = parser.sequence(compound.streams[("Pictures",)])
    picture_offsets, offset = {}, 0
    for index, picture in enumerate(pictures):
        picture_offsets[offset] = index
        offset += 8 + len(picture.body)
    stores = [p for p, r in records.items() if r.kind == 0xF001]
    entries = []
    for pos, record in records.items():
        if record.kind != 0xF007:
            continue
        body = data[pos + 8 : pos + 8 + record.size]
        size, count, target = struct.unpack_from("<III", body, 20)
        index = picture_offsets.get(target) if count else None
        valid = None
        if index is not None:
            picture = pictures[index]
            uid_size = 16 * (1 + (picture.flags >> 4 == BLIPS[picture.kind][1]))
            valid = (
                size == len(picture.body) + 8
                and body[2:18] == picture.body[uid_size - 16 : uid_size]
            )
        entries.append(
            {
                "offset": pos,
                "size": size,
                "c_ref": count,
                "picture_index": index,
                "size_uid_match": valid,
                "flags": record.flags,
                "body_size": record.size,
            }
        )
    png, skips, decoded_total, qualified = [], [], 0, 0
    for index, picture in enumerate(pictures):
        single = Parser(Budget(FormatLimits()))
        try:
            parsed = single.one(picture.flags, picture.kind, picture.body, 0)
        except FormatLimit as exc:
            skips.append(str(exc))
            continue
        image = parsed.raster
        skips.extend(single.raster_skips)
        decoded_total += single.decoded
        qualified += len(single.rasters)
        if image is None or not isinstance(image.parsed, PngData):
            continue
        candidate, encoder = optimize_png(image.encoded, image.parsed, single.budget)
        png.append(
            {
                "picture_index": index,
                "encoded_bytes": len(image.encoded),
                "decoded_bytes": len(image.parsed.raw),
                "candidate_bytes": len(candidate),
                "saved_bytes": len(image.encoded) - len(candidate),
                "encoder": encoder,
                "exact_filtered_samples_and_chunks_verified": True,
            }
        )
    unsupported = defaultdict(Counter)
    for record in records.values():
        if _VERSIONS.get(record.kind) != record.flags & 15:
            unsupported[record.kind][(record.flags & 15, record.flags >> 4)] += 1
    try:
        inspect_records(compound, Budget(FormatLimits()))
        runtime = "accepted"
    except ValueError as exc:
        runtime = str(exc)
    after = digest(path.read_bytes())
    assert before == after
    selected = []
    selected_decoded = 0
    for trial in png:
        if selected_decoded + trial["decoded_bytes"] <= 64 * 1024 * 1024:
            selected.append(trial)
            selected_decoded += trial["decoded_bytes"]
    logical = {"/".join(p): digest(v) for p, v in compound.streams.items()}
    return {
        "file": str(path),
        "sha256": before,
        "file_bytes": path.stat().st_size,
        "source_unchanged": before == after,
        "logical_stream_sha256": logical,
        "document_bytes": len(data),
        "pictures_bytes": offset,
        "records": len(records),
        "record_counts": dict(sorted(Counter(r.kind for r in records.values()).items())),
        "runtime_rejection": runtime,
        "unsupported_type_count": len(unsupported),
        "unsupported_types": {
            str(k): [{"version": v, "instance": i, "count": n} for (v, i), n in sorted(c.items())]
            for k, c in sorted(unsupported.items())
        },
        "notes_graph": {
            "slides": len(slides),
            "notes_slides": len(notes),
            "notes_containers": len(notes_atoms),
            "notes_master_offset": notes_master,
            "notes_master_persist_id": notes_master_id,
            "issues": issues,
            "standard_deviations": deviations,
            "unused_notes_atom_values": sorted({v[2] for v in notes_atoms.values()}),
            "links": note_links,
        },
        "embedded_subtypes": dict(
            Counter(
                struct.unpack_from("<I", data, p + 20)[0]
                for p, r in records.items()
                if r.kind == 4035
            )
        ),
        "embedded_objects": objects,
        "embedded_reference_owner_kinds": dict(owner_counts),
        "binary_tags": tags,
        "bstore_count": len(stores),
        "fbse_entries": entries,
        "simple_pib_reference_counts": dict(sorted(pib_counts.items())),
        "c_ref_matches_simple_pib_counts": all(
            entry["c_ref"] == pib_counts[index + 1] for index, entry in enumerate(entries)
        ),
        "pictures": {
            "count": len(pictures),
            "kinds": dict(Counter(p.kind for p in pictures)),
            "individually_qualified_raster_count": qualified,
            "skips": skips,
            "parsed_decoded_bytes": decoded_total,
            "runtime_64_mib_aggregate_limit_exceeded": decoded_total > 64 * 1024 * 1024,
            "png_zlib9_verified_stream_savings": sum(p["saved_bytes"] for p in png),
            "png_only_64_mib_selection": {
                "policy": "Pictures order; retain remaining images byte-identically",
                "count": len(selected),
                "decoded_bytes": selected_decoded,
                "verified_stream_savings": sum(p["saved_bytes"] for p in selected),
                "indexes": [p["picture_index"] for p in selected],
            },
            "png_trials": png,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert args.output.resolve() not in {p.resolve() for p in args.inputs}
    report = {
        "scope": "Read-only feasibility; no runtime eligibility or whole-file savings claim",
        "date": "2026-10-08",
        "files": [analyze(p) for p in args.inputs],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for file in report["files"]:
        print(
            Path(file["file"]).name,
            json.dumps(
                {
                    "notes_graph_issues": file["notes_graph"]["issues"],
                    "pictures": file["pictures"]["count"],
                    "picture_skips": file["pictures"]["skips"],
                    "fbse_c_ref": dict(Counter(e["c_ref"] for e in file["fbse_entries"])),
                    "png_zlib9_savings": file["pictures"]["png_zlib9_verified_stream_savings"],
                }
            ),
        )


if __name__ == "__main__":
    main()
