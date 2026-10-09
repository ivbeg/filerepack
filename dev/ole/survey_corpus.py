"""Reproduce a read-only eligibility census of pinned OLE originals.

The survey inspects originals; it never rewrites or opens them in an application.
Each content inspector receives a fresh default budget, so stage eligibility is
distinct from cumulative resource use in a real public API operation.
"""

import argparse
import hashlib
import json
import platform
import struct
import urllib.request
from collections import Counter
from pathlib import Path

from filerepack.format_support import Budget, FormatLimits
from filerepack.ole import _profile
from filerepack.ole_art_layout import inspect_art
from filerepack.ole_dedup import inspect_dedup
from filerepack.ole_verify import CompoundFile
from filerepack.ole_word_art import pieces as word_pieces, u16 as word_u16

INVENTORY = Path(__file__).with_name("corpus-inventory.json")


def exact(data, entry):
    blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    return (
        len(data) == entry["bytes"]
        and hashlib.sha256(data).hexdigest() == entry["sha256"]
        and hashlib.sha1(blob).hexdigest() == entry["git_blob_sha1"]
    )


def source_bytes(entry, cache, download):
    name, category = entry["name"], entry["category"]
    if Path(name).name != name or category not in ("document", "spreadsheet", "slideshow"):
        raise ValueError("unsafe inventory path")
    path = cache / category / name
    data = path.read_bytes() if path.is_file() else b""
    if exact(data, entry):
        return data
    if not download:
        raise ValueError("missing cache file or pinned length/hash mismatch")
    with urllib.request.urlopen(entry["source"], timeout=30) as response:
        data = response.read(entry["bytes"] + 1)
    if not exact(data, entry):
        raise ValueError("downloaded length/Git blob/SHA-256 mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def inspect(entry, data):
    result = {"name": entry["name"], "category": entry["category"], "sha256": entry["sha256"]}
    try:
        compound = CompoundFile(data)
        result["container"] = True
    except (ValueError, struct.error) as exc:
        result["container_skip"] = str(exc)
        return result
    host = Path(entry["name"]).suffix[1:]
    if host.lower() == "doc" and ("WordDocument",) in compound.streams:
        try:
            word = compound.streams[("WordDocument",)]
            table_path = ("1Table" if word_u16(word, 10) & 0x200 else "0Table",)
            modifiers = {}
            ranges = word_pieces(word, compound.streams[table_path], modifiers)
            picture_locations = sum(0x6A03 in properties for properties in modifiers.values())
            result["piece_prm"] = {
                "pieces": len(ranges),
                "picture_location_pieces": picture_locations,
            }
        except (KeyError, ValueError, struct.error) as exc:
            result["piece_prm_skip"] = str(exc)
    try:
        result["host"] = list(_profile(compound, host))
    except (ValueError, struct.error) as exc:
        result["host_skip"] = str(exc)
        return result
    try:
        art = inspect_art(compound, Budget(FormatLimits()))
        adapter = art.adapter
        result["officeart"] = {
            "adapter": type(adapter).__name__,
            "metafiles": len(art.metafiles),
            "rasters": len(art.rasters),
            "table_owned_references": sum(at < 0 for at in getattr(adapter, "refs", {})),
            "data_blocks": len(getattr(adapter, "blocks", ())),
            "data_gaps": len(getattr(adapter, "gaps", ())),
        }
    except (ValueError, struct.error) as exc:
        result["officeart_skip"] = str(exc)
    if host in ("xls", "ppt"):
        try:
            layout = inspect_dedup(compound, Budget(FormatLimits()))
            result["dedup"] = {
                "entries": len(layout.images),
                "unique_identities": len(set(layout.identity)),
                "consumers": len(layout.consumers),
                "removable_entries": len(layout.images) - len(set(layout.canonical)),
            }
        except (ValueError, struct.error) as exc:
            result["dedup_skip"] = str(exc)
    return result


def summarize(results):
    counts = {}
    for category in ("document", "spreadsheet", "slideshow"):
        rows = [r for r in results if r["category"] == category]
        counts[category] = {
            "selected": len(rows),
            "source_verified": sum("source_skip" not in r for r in rows),
            "container": sum(bool(r.get("container")) for r in rows),
            "host": sum("host" in r for r in rows),
            "officeart": sum("officeart" in r for r in rows),
            "dedup": sum("dedup" in r for r in rows),
            "dedup_with_removable_entries": sum(
                r.get("dedup", {}).get("removable_entries", 0) > 0 for r in rows
            ),
            "table_owned_word_references": sum(
                r.get("officeart", {}).get("table_owned_references", 0) > 0 for r in rows
            ),
            "piece_prm_scanned": sum("piece_prm" in r for r in rows),
            "piece_prm_picture_files": sum(
                r.get("piece_prm", {}).get("picture_location_pieces", 0) > 0 for r in rows
            ),
            "piece_prm_picture_pieces": sum(
                r.get("piece_prm", {}).get("picture_location_pieces", 0) for r in rows
            ),
        }
    reasons = {
        stage: dict(Counter(r[stage + "_skip"] for r in results if stage + "_skip" in r))
        for stage in ("source", "container", "host", "officeart", "dedup")
    }
    return {"counts": counts, "rejection_reasons": reasons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--download", action="store_true", help="fetch missing pinned originals")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    results = []
    for index, entry in enumerate(inventory["files"]):
        try:
            data = source_bytes(entry, args.cache, args.download)
        except (OSError, ValueError) as exc:
            result = {
                "name": entry["name"],
                "category": entry["category"],
                "source_skip": str(exc),
            }
        else:
            result = inspect(entry, data)
        results.append(result)
        if index % 50 == 49:
            print("inspected", index + 1, "of", len(inventory["files"]), flush=True)
    report = {
        "schema_version": 1,
        "source": inventory["source"],
        # Datasets without a Git revision pin their archive bytes in inventory.
        "commit": inventory.get("commit"),
        "license": inventory["license"],
        "selection": inventory["selection"],
        "inventory_sha256": hashlib.sha256(args.inventory.read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "scope": "read-only eligibility; no savings or application acceptance inferred",
        **summarize(results),
        "files": results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"], indent=2))
    if any("source_skip" in r for r in results):
        raise SystemExit("incomplete census: one or more pinned originals are unavailable")


if __name__ == "__main__":
    main()
