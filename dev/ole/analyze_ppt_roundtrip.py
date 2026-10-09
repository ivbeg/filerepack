"""Read-only PPT extension inventory and isolated Pictures encoding feasibility.

No host eligibility gate is relaxed and no PPT candidate is written. Image-only
savings are not evidence of whole-file eligibility, preservation or savings.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct

from filerepack.format_support import Budget, FormatLimits
from filerepack.ole_art_layout import inspect_art
from filerepack.ole_officeart import Parser, encode_rasters
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_extensions import _EXTRA
from filerepack.ole_ppt_host import PptHost, _lists, _notes, _objects
from filerepack.ole_ppt_records import _VERSIONS, _persist
from filerepack.ole_verify import read_compound


def forms(records):
    counts = Counter(
        (r.kind, r.flags & 15, r.flags >> 4,
         records[r.parent].kind if r.parent is not None else None, r.size)
        for r in records.values()
    )
    return [
        dict(kind=k, version=v, instance=i, owner=o, size=s, count=n)
        for (k, v, i, o, s), n in sorted(counts.items())
    ]


def analyze(path):
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    compound = read_compound(str(path))
    data = compound.streams[("PowerPoint Document",)]
    records = read_records(data)
    children = defaultdict(list)
    for pos, record in records.items():
        children[record.parent].append(pos)
    try:
        inspect_art(compound, Budget(FormatLimits()))
        rejection = None
    except ValueError as exc:
        rejection = str(exc)
    tags = []
    for pos, record in records.items():
        if record.kind != 5002:
            continue
        name_pos, blob_pos = children[pos]
        owner = records[records[record.parent].parent].kind
        tags.append({
            "name": data[name_pos + 8:name_pos + 8 + records[name_pos].size].decode("utf-16le"),
            "owner": owner,
            "forms": forms(read_records(data[blob_pos + 8:blob_pos + 8 + records[blob_pos].size])),
        })
    # Inspect graph helpers in isolation, without claiming full host acceptance.
    edits = [p for p, r in records.items() if r.kind == 4085]
    directories = [p for p, r in records.items() if r.kind == 6002]
    assert len(edits) == len(directories) == 1
    edit, directory = edits[0], directories[0]
    previous, index, doc_id, seed = struct.unpack_from("<4I", data, edit + 16)
    assert previous == 0 and index == directory and doc_id == 1
    persist, fields = _persist(data, records, directory, seed)
    host = PptHost(
        data, compound.streams[("Current User",)], records, children, persist,
        fields, directory, edit, {0}, [p for p in children[None] if records[p].kind == 4113],
    )
    lists = _lists(host)
    _notes(host, lists)
    _objects(host)
    graph = {
        "slides": len(lists[0]), "masters": len(lists[1]), "notes_pages": len(lists[2]),
        "notes_containers": sum(r.kind == 1008 for r in records.values()),
        "embedded_storages": len(host.storages),
        "notes_and_embedded_graph_checks": "passed in isolation",
    }
    budget = Budget(FormatLimits())
    parser = Parser(budget, bounded_png=True)
    parser.retain_jpeg = any(r.kind == 1008 for r in records.values())
    pictures = parser.sequence(compound.streams[("Pictures",)])
    payloads, encoders = encode_rasters(parser.rasters, budget, skips=parser.raster_skips)
    trials = []
    for record, encoder in zip(parser.rasters, encoders):
        image = record.raster
        assert image is not None
        encoded = payloads.get(id(record), image.encoded)
        trials.append({
            "picture_index": next(i for i, p in enumerate(pictures) if p is record),
            "original_bytes": len(image.encoded), "candidate_bytes": len(encoded),
            "saved_bytes": len(image.encoded) - len(encoded), "encoder": encoder,
        })
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
    observed = forms(records)
    blockers = []
    for form in observed:
        kind = form["kind"]
        rule = _EXTRA.get(kind)
        if rule is None:
            if _VERSIONS.get(kind) != form["version"]:
                blockers.append(form)
        else:
            v, instances, owners, size = rule
            if (v != form["version"] or form["instance"] not in instances
                    or form["owner"] not in owners or (size is not None and form["size"] != size)):
                blockers.append(form)
    return {
        "file": str(path), "sha256": before, "file_bytes": len(compound.data),
        "source_unchanged": before == after,
        "streams": {"/".join(p): len(v) for p, v in compound.streams.items()},
        "runtime_picture_rejection": rejection, "record_form_blockers": blockers,
        "programmable_tags": tags, "graph": graph,
        "picture_kinds": dict(Counter(p.kind for p in pictures)),
        "pictures_bytes": len(compound.streams[("Pictures",)]),
        "selected_rasters": len(parser.rasters), "decoded_accounting_bytes": budget.decoded,
        "sample_selection_bytes": parser.decoded, "skips": parser.raster_skips,
        "verified_image_only_savings_bytes": sum(t["saved_bytes"] for t in trials),
        "trials": trials, "whole_file_candidate_written": False,
        "limitation": (
            "Isolated image feasibility; full host eligibility and final file savings unqualified."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("output must differ from input")
    result = analyze(args.input)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "sha256", "source_unchanged", "graph", "selected_rasters",
        "verified_image_only_savings_bytes", "whole_file_candidate_written",
    )}, indent=2))


if __name__ == "__main__":
    main()
