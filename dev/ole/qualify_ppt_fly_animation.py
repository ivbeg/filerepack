"""Independent immutable animation, POI save/reopen and slide/notes qualification.

Run after producing a distinct-output candidate with the public repack command.
Requires the pinned POI 5.4.1 control, LibreOffice and pdftoppm; these are not
runtime dependencies. Supplied source/candidate files are read-only inputs.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from dev.ole.qualify_ppt_notes import render
from filerepack.format_support import format_scope
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_verify import read_compound
from filerepack.tools import resolve_tool


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--poi-classpath", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    source, candidate = args.source.resolve(), args.candidate.resolve()
    assert len({source, candidate, args.report.resolve()}) == 3
    raw = source.read_bytes()
    stat = source.stat()
    candidate_raw = candidate.read_bytes()
    before, after = read_compound(str(source)), read_compound(str(candidate))
    writer = resolve_tool("ole_compactor")
    with format_scope({"ole_writer": writer}) as budget:
        assert equal_art(inspect_art(before, budget), inspect_art(after, budget))
    document, pictures = ("PowerPoint Document",), ("Pictures",)
    old, new = before.streams[document], after.streams[document]
    records = read_records(old)
    immutable = {1008, 1052, 1053, 1054, 1058, 4113, 4116, 4081, 5000}
    spans = [(p, r) for p, r in records.items() if r.kind in immutable]
    assert len(old) == len(new)
    assert all(old[p:p + 8 + r.size] == new[p:p + 8 + r.size] for p, r in spans)
    assert all(before.streams[p] == after.streams[p] for p in before.streams
               if p not in (document, pictures))
    result = {
        "date": "2026-10-09", "scope": "Local macOS Python 3.13/native/POI/LibreOffice",
        "source_sha256": digest(raw), "candidate_sha256": digest(candidate_raw),
        "source_bytes": len(raw), "candidate_bytes": len(candidate_raw),
        "whole_file_saved_bytes": len(raw) - len(candidate_raw),
        "savings_percent": 100 * (len(raw) - len(candidate_raw)) / len(raw),
        "complete_officeart_contract_equal": True, "unaffected_streams_exact": True,
        "immutable_animation_notes_tags_storage_layout_spans": len(spans),
        "animation_atoms": sum(r.kind == 4081 for r in records.values()),
        "source_mode": oct(stat.st_mode & 0o777),
        "source_mtime_ns": stat.st_mtime_ns,
        "candidate_mode": oct(candidate.stat().st_mode & 0o777),
        "mtime_preserved": candidate.stat().st_mtime_ns == stat.st_mtime_ns,
        "native_sha256": digest(Path(writer).read_bytes()), "poi_version": "5.4.1",
        "renderer": subprocess.check_output([shutil.which("soffice"), "--version"],
                                             text=True).strip(),
    }
    with tempfile.TemporaryDirectory(prefix="filerepack-fly-qa-") as directory:
        root = Path(directory)
        reader = subprocess.run(
            ["java", "-Djava.awt.headless=true", "-cp", args.poi_classpath,
             "PptAnimationCompatibility", str(source), str(candidate),
             str(root / "source-saved.ppt"), str(root / "candidate-saved.ppt")],
            capture_output=True, text=True, timeout=120,
        )
        assert reader.returncode == 0, reader.stdout + reader.stderr
        assert "source_candidate_equal=true" in reader.stdout
        result["poi_reader_save_reopen"] = reader.stdout.splitlines()
        for mode in ("slides", "notes"):
            print("Comparing", mode, flush=True)
            first = render(source, root / ("source-" + mode), notes=mode == "notes")
            second = render(candidate, root / ("candidate-" + mode), notes=mode == "notes")
            assert first == second, "Source/candidate rendering differs: " + mode
            result[mode + "_render"] = {
                "equal_page_rgb": True, "page_count": len(first), "pages": first,
            }
    assert source.read_bytes() == raw and source.stat().st_mtime_ns == stat.st_mtime_ns
    assert candidate.read_bytes() == candidate_raw
    result["source_unchanged"] = result["candidate_unchanged_by_qa"] = True
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print("Content, independent reader/save/reopen and rendering checks passed", flush=True)


if __name__ == "__main__":
    main()
