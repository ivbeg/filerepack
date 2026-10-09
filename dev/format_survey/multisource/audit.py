#!/usr/bin/env python3
"""Independently check aggregate accounting and extract the two public censuses."""
import argparse
import collections
import csv
import gzip
import html.parser
import hashlib
import json
import pathlib
import re


class MediaTable(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.section, self.table, self.cell = "", False, None
        self.cells, self.values, self.rows = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table = "mw-mediastats-table" in attrs.get("class", "")
            self.section = attrs.get("class", "").split()[1] if self.table else ""
        if self.table and tag == "tr":
            self.cells, self.values = [], []
        if self.table and tag == "td":
            self.cell = []
            self.values.append(attrs.get("data-sort-value"))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.table and tag == "td":
            self.cells.append("".join(self.cell))
            self.cell = None
        if self.table and tag == "tr" and len(self.cells) == 4:
            self.rows.append(
                {
                    "section": self.section,
                    "mime": self.cells[0],
                    "extensions": self.cells[1],
                    "files": int(self.values[2]),
                    "bytes": int(self.values[3]),
                }
            )
        if tag == "table":
            self.table = False


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--run", type=pathlib.Path)
    args = parser.parse_args()
    output = args.output
    with gzip.open(output / "inventory.jsonl.gz", "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    assert all(r["size"] is None or isinstance(r["size"], int) and r["size"] >= 0 for r in rows)
    # Figshare can expose distinct file IDs with the same basename in one article.
    ids = [(r["source"], r["project"], r["version"], r.get("file_id", r["name"])) for r in rows]
    assert len(ids) == len(set(ids)), "duplicated source/project/version/file-identity rows"
    source_stats = collections.defaultdict(lambda: [0, 0])
    format_stats = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        for stat in (source_stats[r["source"]], format_stats[r["source"], r["format"]]):
            stat[0] += 1
            stat[1] += r["size"] or 0
    for name, stats, fields in (
        ("sources.csv", source_stats, ("source",)),
        ("formats-by-source.csv", format_stats, ("source", "format")),
    ):
        for r in csv.DictReader((output / name).open(encoding="utf-8")):
            key = tuple(r[f] for f in fields) if len(fields) > 1 else r[fields[0]]
            assert [int(r["files"]), int(r["bytes"])] == stats[key], (name, key)
    registry = set(json.loads((output / "registry.json").read_text())["extensions"])
    for r in rows:
        assert r["registered_outer_extension"] == (r["outer_extension"] in registry)
        assert r["registered_format_extension"] == (r["candidate_format"] in registry)
    candidates = list(csv.DictReader((output / "candidates.csv").open(encoding="utf-8")))
    for c in candidates:
        group = [
            r
            for r in rows
            if r["candidate_format"] == c["format"]
            and r.get("role") not in ("derivative", "metadata")
        ]
        assert int(c["files"]) == len(group)
        assert int(c["bytes"]) == sum(r["size"] or 0 for r in group)
        known = {
            (r["checksum"], r["size"]) for r in group if r["checksum"] and r["size"] is not None
        }
        assert int(c["unique_known_checksum_size"]) == len(known)
    project_ids = {
        (p["source"], p["project"]) for p in json.loads((output / "projects.json").read_text())
    }
    assert all((r["source"], r["project"]) in project_ids for r in rows)
    probe_checks = {}
    if args.run:
        probes = json.loads((output / "probes.json").read_text())
        by_url = {r["url"]: r for r in rows}
        verified = 0
        for result in probes["results"]:
            assert result["url"] in by_url
            assert result["metadata_size"] == by_url[result["url"]]["size"]
            if result.get("sha256"):
                key = hashlib.sha256(result["url"].encode()).hexdigest()
                data = (args.run / "inputs" / (key + ".bin")).read_bytes()
                assert hashlib.sha256(data).hexdigest() == result["sha256"]
                assert len(data) == result["downloaded_bytes"]
                verified += 1
        assert (
            sum(r.get("downloaded_bytes", 0) for r in probes["results"])
            == probes["consumed_sample_bytes"]
        )
        assert probes["consumed_sample_bytes"] <= probes["limits"]["total_sample_bytes"]
        for store in json.loads((output / "directory-stores.json").read_text())["stores"]:
            members = [
                r
                for r in rows
                if r["source"] == store["source"]
                and r["project"] == store["project"]
                and r["name"].startswith(store["root"] + "/")
            ]
            assert len(members) == store["observed_files"]
            assert sum(r["size"] or 0 for r in members) == store["observed_bytes"]
            if store.get("metadata_sha256"):
                key = hashlib.sha256(store["metadata_url"].encode()).hexdigest()
                data = (args.run / "store-metadata" / (key + ".json")).read_bytes()
                assert hashlib.sha256(data).hexdigest() == store["metadata_sha256"]
        probe_checks = {
            "input_sha256_verified": verified,
            "sample_budget": "passed",
            "store_accounting": "passed",
        }
    census_checks = {}
    for kind in ("header", "detected"):
        path = output / f"commoncrawl-{kind}.csv"
        if not path.exists():
            continue
        records = list(csv.DictReader(path.open(encoding="utf-8")))
        crawls = sorted({r["crawl"] for r in records})[-3:]
        selected = [r for r in records if r["crawl"] in crawls]
        write_csv(output / f"commoncrawl-{kind}-latest.csv", selected)
        census_checks["commoncrawl-" + kind] = {
            crawl: {
                "rows": sum(r["crawl"] == crawl for r in selected),
                "pages": sum(int(r["pages"]) for r in selected if r["crawl"] == crawl),
            }
            for crawl in crawls
        }
    path = output / "commons-media-statistics.html"
    if path.exists():
        page = path.read_text(encoding="utf-8")
        tables = MediaTable()
        tables.feed(page)
        total = re.search(r"Total file size for all ([\d,]+) files: ([\d,]+) bytes", page)
        assert total, "missing Commons census denominator"
        total_files, total_bytes = (int(x.replace(",", "")) for x in total.groups())
        assert sum(r["files"] for r in tables.rows) == total_files
        assert sum(r["bytes"] for r in tables.rows) == total_bytes
        write_csv(output / "commons-media.csv", tables.rows)
        census_checks["commons"] = {
            "files": total_files,
            "bytes": total_bytes,
            "rows": len(tables.rows),
        }
    result = {
        "accounting_checks": "passed",
        "files": len(rows),
        "bytes": sum(r["size"] or 0 for r in rows),
        "censuses": census_checks,
        "local_probe_checks": probe_checks,
    }
    (output / "independent-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
