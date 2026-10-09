"""Measure user-supplied DOCs without redistributing or overwriting their sources."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

from filerepack import FileRepacker, RepackOptions
from filerepack.verification import preservation_equal
from dev.ole.qualify import render


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--writer", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--soffice", default="soffice")
    parser.add_argument("--pdftoppm", default="pdftoppm")
    args = parser.parse_args()
    writer = str(args.writer.resolve())
    os.environ["FILEREPACK_OLE_COMPACTOR"] = writer
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "qualification_date": "2026-10-08", "platform": platform.platform(),
        "python": platform.python_version(),
        "writer": subprocess.check_output([writer, "--version"], text=True).strip(),
        "renderer": subprocess.check_output([args.soffice, "--version"], text=True).strip(),
        "scope": "User-provided originals; binaries are not redistributed. "
                 "Local LibreOffice rendering; Microsoft Office and remote platforms unmeasured.",
        "cases": [],
    }
    for source in args.sources:
        source = source.resolve()
        output = args.output_dir.resolve() / source.name
        if output.exists() or source == output:
            raise ValueError("Output must be a new path: " + str(output))
        source_hash = digest(source)
        with tempfile.TemporaryDirectory(prefix="word-property-qualification-") as scratch:
            scratch = Path(scratch)
            baseline = scratch / "compaction.doc"
            baseline.touch()
            subprocess.run([writer, str(source), str(baseline)], check=True, capture_output=True)
            started = time.monotonic()
            result = FileRepacker().repack(
                str(source), outfile=str(output), options=RepackOptions(ole_recompress=True)
            ).results[0]
            if not output.exists():
                raise ValueError(result.reason)
            assert result.details["strategy"] == "ole-officeart-recompression", result.details
            assert preservation_equal(str(source), str(output), "officeart")
            assert output.stat().st_size < baseline.stat().st_size
            elapsed = round(time.monotonic() - started, 3)
            print(source.name, source.stat().st_size, "->", output.stat().st_size,
                  "independent preservation passed; rendering pages", flush=True)
            before, after = scratch / "before", scratch / "after"
            before.mkdir()
            after.mkdir()
            pages = render(source, before, args.soffice, args.pdftoppm)
            print(source.name, "original rendered:", len(pages), "pages", flush=True)
            candidate_pages = render(output, after, args.soffice, args.pdftoppm)
            assert pages == candidate_pages, "Rendered page pixels differ: " + source.name
            assert digest(source) == source_hash
            report["cases"].append({
                "source_name": source.name, "source_sha256": source_hash,
                "source_bytes": source.stat().st_size, "source_unchanged": True,
                "candidate_sha256": digest(output), "candidate_bytes": output.stat().st_size,
                "strict_compaction_bytes": baseline.stat().st_size,
                "additional_savings_bytes": baseline.stat().st_size - output.stat().st_size,
                "independent_preservation_equal": True, "candidate_seconds": elapsed,
                "render": {"equal": True, "pages": len(pages), "dpi": 96,
                           "macro_security_level": 3, "page_hashes": pages},
                "details": result.details,
            })
            print(source.name, "equal page pixels:", len(pages), "pages", flush=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print("Qualification report:", args.report, flush=True)


if __name__ == "__main__":
    main()
