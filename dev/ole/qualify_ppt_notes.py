"""Qualify supplied PPTs without publication, including independent notes rendering.

Run with the project venv as a module; requires the qualified native helper,
LibreOffice and pdftoppm. All presentation intermediates are private and removed.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from PIL import Image

from filerepack.format_support import format_scope
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_recompress import run_art_operation
from filerepack.ole_verify import read_compound
from filerepack.tools import resolve_tool


def digest(data):
    return hashlib.sha256(data).hexdigest()


def render(source, directory, *, notes=False):
    directory.mkdir(parents=True)
    profile = directory / "profile"
    (profile / "user").mkdir(parents=True)
    (profile / "user" / "registrymodifications.xcu").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
        '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
        "</item></oor:items>"
    )
    parameters = {"ExportHiddenSlides": {"type": "boolean", "value": "true"}}
    if notes:
        parameters.update(
            {
                key: {"type": "boolean", "value": "true"}
                for key in ("ExportNotesPages", "ExportOnlyNotesPages")
            }
        )
    command = [
        shutil.which("soffice"),
        "-env:UserInstallation=" + profile.as_uri(),
        "--headless",
        "--convert-to",
        "pdf:impress_pdf_Export:" + json.dumps(parameters),
        "--outdir",
        str(directory),
        str(source),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    pdf = directory / (source.stem + ".pdf")
    assert result.returncode == 0 and pdf.is_file(), result.stdout + result.stderr
    subprocess.run(
        [shutil.which("pdftoppm"), "-r", "72", "-png", str(pdf), str(directory / "page")],
        check=True,
        capture_output=True,
        timeout=120,
    )
    pages = []
    for path in sorted(directory.glob("page-*.png")):
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            pages.append({"size": list(rgb.size), "sha256": digest(rgb.tobytes())})
    assert pages
    return pages


def qualify(path, writer, root, *, render_pages):
    raw = path.read_bytes()
    candidate = root / "candidate.ppt"
    candidate.touch()
    info = run_art_operation("rewrite", str(path.resolve()), str(candidate), {"ole_writer": writer})
    assert info["verify"] == "officeart"
    before, after = read_compound(str(path)), read_compound(str(candidate))
    # Current helpers accelerate independently checked rows; old helpers retain
    # Python checks. Share actual root accounting across this fresh comparison.
    with format_scope({'ole_writer': writer}) as budget:
        assert equal_art(inspect_art(before, budget), inspect_art(after, budget))
    document = ("PowerPoint Document",)
    old, new = before.streams[document], after.streams[document]
    records = read_records(old)
    spans = [p for p, r in records.items() if r.kind in (1008, 4113)]
    assert len(old) == len(new)
    assert all(old[p : p + 8 + records[p].size] == new[p : p + 8 + records[p].size] for p in spans)
    assert all(
        before.streams[p] == after.streams[p]
        for p in before.streams
        if p not in (document, ("Pictures",))
    )
    result = {
        "file": str(path),
        "source_sha256": digest(raw),
        "candidate_sha256": digest(candidate.read_bytes()),
        "source_bytes": len(raw),
        "candidate_bytes": candidate.stat().st_size,
        "whole_file_saved_bytes": len(raw) - candidate.stat().st_size,
        "unchanged_notes_and_storage_spans": len(spans),
        "equal_content_contract": True,
        "unaffected_streams_identical": True,
        "worker": info,
        "logical_stream_sha256": {"/".join(p): digest(d) for p, d in after.streams.items()},
    }
    if render_pages:
        for mode in ("slides", "notes"):
            print(path.name, "rendering", mode, flush=True)
            first = render(path.resolve(), root / ("source-" + mode), notes=mode == "notes")
            second = render(candidate, root / ("candidate-" + mode), notes=mode == "notes")
            assert first == second, "Source/candidate rendering differs: " + mode
            result[mode + "_render"] = {"equal_rgb_pages": True, "pages": first}
        # Independently compare the observed old master fields with the standard
        # zero-field control. This is a development-only rendering experiment,
        # never a runtime normalization or an accepted content transformation.
        current = root / "current"
        current.write_bytes(before.streams[("Current User",)])
        normalized = bytearray(old)
        master = next(
            p
            for p, r in records.items()
            if r.kind == 1009 and struct.unpack_from("<I", old, p + 8)[0] == 0x80000000
        )
        struct.pack_into("<IH", normalized, master + 8, 0, 0)
        payload = root / "normative-document"
        payload.write_bytes(normalized)
        control = root / "normative-master.ppt"
        control.touch()
        subprocess.run(
            [
                writer,
                "--replace-ppt-streams",
                str(payload),
                str(current),
                str(path.resolve()),
                str(control),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        norm_notes = render(control, root / "normative-notes", notes=True)
        assert norm_notes == result["notes_render"]["pages"], (
            "Old/master standard-form notes differ"
        )
        result["legacy_master_normative_render_equal"] = True
    assert digest(path.read_bytes()) == digest(raw)
    result["source_unchanged"] = True
    print(
        path.name,
        result["whole_file_saved_bytes"],
        info["usage"]["peak_worker_rss_bytes"],
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    writer = resolve_tool("ole_compactor")
    assert writer and args.output.resolve() not in {p.resolve() for p in args.inputs}
    report = {
        "date": "2026-10-08",
        "scope": "Local macOS Python 3.13/native/LibreOffice qualification",
        "renderer": subprocess.check_output(
            [shutil.which("soffice"), "--version"], text=True
        ).strip(),
        "native_sha256": digest(Path(writer).read_bytes()),
        "files": [],
    }
    for path in args.inputs:
        with tempfile.TemporaryDirectory(prefix="filerepack-ppt-notes-qa-") as scratch:
            render_pages = not args.no_render and "root-normalized" not in path.name
            result = qualify(path, writer, Path(scratch), render_pages=render_pages)
            report["files"].append(result)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if len(report["files"]) == 4:
        assert (
            report["files"][1]["logical_stream_sha256"]
            == report["files"][3]["logical_stream_sha256"]
        )
        report["normalized_duplicate_logical_equivalence"] = True
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
