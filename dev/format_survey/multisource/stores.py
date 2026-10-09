#!/usr/bin/env python3
"""Identify directory stores separately from file extensions and inspect metadata."""
import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--run", type=pathlib.Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.output / "inventory.jsonl.gz", "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    projects = {
        (p["source"], p["project"]): p
        for p in json.loads((args.output / "projects.json").read_text())
    }
    groups = collections.defaultdict(list)
    for row in rows:
        parts = row["name"].split("/")
        roots = [i for i, p in enumerate(parts) if p.lower().endswith(".zarr")]
        if roots:
            root = "/".join(parts[: roots[0] + 1])
            groups[(row["source"], row["project"], row["version"], root)].append(row)
    result = []
    cache = args.run / "store-metadata"
    cache.mkdir(parents=True, exist_ok=True)
    for (source, project, version, root), members in sorted(groups.items()):
        markers = [
            r
            for r in members
            if pathlib.PurePosixPath(r["name"]).name
            in (".zarray", ".zgroup", ".zmetadata", "zarr.json")
        ]
        record = {
            "source": source,
            "project": project,
            "version": version,
            "root": root,
            "observed_files": len(members),
            "observed_bytes": sum(r["size"] or 0 for r in members),
            "project_tree_complete": projects[source, project]["complete"],
            "marker_files": len(markers),
            "identification": "path and metadata marker hypothesis",
        }
        anchor = next((r for r in markers if r["name"] == root + "/.zmetadata"), None)
        if anchor is None:
            anchor = next((r for r in markers if r["name"] == root + "/zarr.json"), None)
        if anchor and len(result) < 10:
            try:
                path = cache / (hashlib.sha256(anchor["url"].encode()).hexdigest() + ".json")
                if path.exists():
                    data = path.read_bytes()
                else:
                    request = urllib.request.Request(
                        anchor["url"],
                        headers={
                            "User-Agent": "filerepack-format-survey/1.0 (bounded store metadata)"
                        },
                    )
                    with urllib.request.urlopen(request, timeout=20) as response:
                        data = response.read(1024 * 1024 + 1)
                    if len(data) > 1024 * 1024:
                        raise ValueError("store metadata exceeds 1 MiB")
                    path.write_bytes(data)
                if len(data) != anchor["size"]:
                    raise ValueError("store metadata size mismatch")
                verified = False
                if anchor["checksum"]:
                    algorithm, expected = anchor["checksum"].split(":", 1)
                    actual = (
                        hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
                        if algorithm == "git-sha1"
                        else hashlib.new(algorithm, data).hexdigest()
                    )
                    if actual != expected:
                        raise ValueError("store metadata checksum mismatch")
                    verified = True
                metadata = json.loads(data)
                array_metadata = {
                    k: v
                    for k, v in metadata.get("metadata", {}).items()
                    if k.endswith("/.zarray") or k == ".zarray"
                }
                record.update(
                    identification="parsed consolidated Zarr metadata",
                    metadata_url=anchor["url"],
                    metadata_bytes=len(data),
                    metadata_sha256=hashlib.sha256(data).hexdigest(),
                    metadata_checksum_verified=verified,
                    arrays=[
                        {
                            "path": key.removesuffix("/.zarray"),
                            **{
                                k: value.get(k)
                                for k in (
                                    "zarr_format",
                                    "shape",
                                    "chunks",
                                    "dtype",
                                    "compressor",
                                    "filters",
                                    "order",
                                    "fill_value",
                                    "dimension_separator",
                                )
                            },
                        }
                        for key, value in sorted(array_metadata.items())
                    ],
                    store_metadata_format=metadata.get(
                        "zarr_consolidated_format", metadata.get("zarr_format")
                    ),
                )
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
        result.append(record)
    target = args.output / "directory-stores.json"
    target.write_text(
        json.dumps(
            {
                "scope": (
                    "Named .zarr roots only; observed objects are already in the file "
                    "inventory. Metadata probes are limited to ten anchors of 1 MiB "
                    "each; no array/chunk decoding."
                ),
                "stores": result,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "stores": len(result),
                "path": str(target),
                "identified": sum(
                    r["identification"] == "parsed consolidated Zarr metadata" for r in result
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
