"""Repeat the previous bounded sample with the new passive runtime adapters.

Run with filerepack[scientific,zarr]; writes candidates/results to --output only.
The cached inputs are immutable. Native user-object loaders are never called.
"""

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

from filerepack.format_support import run_operation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    rows = json.loads(
        (root / "dev/format_survey/multisource/pilot-2026-10-04/probes.json").read_text()
    )["results"]
    cache = root / "dev/format_survey/runs/multisource-2026-10-04/inputs"
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    mapping = {
        "rds": "r-serialization",
        "rdata": "r-serialization",
        "mat": "mat",
        "pt": "checkpoint",
        "sav": "spss",
    }
    for row in rows:
        if row["format"] not in mapping:
            continue
        source = cache / (hashlib.sha256(row["url"].encode()).hexdigest() + ".bin")
        if not source.exists():
            continue
        profiles = (
            ["preserve", "xz"]
            if mapping[row["format"]] == "r-serialization"
            else (["preserve-mmap", "load-only"] if row["format"] == "pt" else ["preserve"])
        )
        for profile in profiles:
            item = {
                key: row.get(key)
                for key in (
                    "url",
                    "project",
                    "source",
                    "name",
                    "format",
                    "sha256",
                    "metadata_checksum_verified",
                )
            }
            item.update(profile=profile, input_bytes=source.stat().st_size)
            candidate = output / (source.stem + "." + profile)
            settings = {
                "r_compression": profile if row["format"] in ("rds", "rdata") else "preserve",
                "checkpoint_compatibility": profile if row["format"] == "pt" else "preserve-mmap",
                "experimental_formats": True,
                "format_max_nodes": 2000000,
            }
            start = time.monotonic()
            try:
                result = run_operation(
                    mapping[row["format"]], "rewrite", str(source), str(candidate), settings
                )
                item.update(
                    result=result,
                    candidate_bytes=candidate.stat().st_size,
                    accepted=candidate.stat().st_size < source.stat().st_size,
                )
            except (OSError, ValueError) as exc:
                item.update(error=str(exc), accepted=False, candidate_bytes=item["input_bytes"])
            item["seconds"] = round(time.monotonic() - start, 4)
            results.append(item)
            print(item["format"], profile, item["accepted"], item.get("error", ""), flush=True)
    (output / "results.json").write_text(
        json.dumps({"environment": platform.platform(), "results": results}, indent=2)
    )


if __name__ == "__main__":
    main()
