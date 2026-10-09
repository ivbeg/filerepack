#!/usr/bin/env python3
"""Bounded public metadata survey. No runtime imports or format writers."""
import argparse
import ast
import collections
import concurrent.futures
import csv
import datetime
import gzip
import hashlib
import json
import pathlib
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
AGENT = "filerepack-format-survey/1.0 (bounded public metadata research)"
ALIASES = {"jpeg": "jpg", "jpe": "jpg", "tiff": "tif", "rda": "rdata"}
COMPRESSION = {"gz", "xz", "bz2", "zst", "lz4"}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extension(name):
    base = pathlib.PurePosixPath(name).name.lower()
    if "." not in base or base.startswith(".") and base.count(".") == 1:
        return "[none]", "[none]", "[none]"
    parts = base.rsplit(".", 2)
    outer = parts[-1]
    inner = parts[-2] if outer in COMPRESSION and len(parts) == 3 else outer
    fmt = inner + "." + outer if inner != outer else outer
    return ALIASES.get(fmt, fmt), ALIASES.get(inner, inner), outer


def integer(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class Survey:
    def __init__(self, config, run, output):
        self.config, self.run, self.output = config, run, output
        self.lock = threading.Lock()
        self.receipts, self.errors, self.projects, self.rows = [], [], [], []
        self.cache = run / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.supported = self.registry()

    def registry(self):
        raw = (ROOT / "filerepack/consts.py").read_bytes()
        tree = ast.parse(raw)
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = ast.literal_eval(node.value)
        snapshot = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "extensions": sorted(set(values["ARCHIVE_EXTS"] + values["STANDALONE_EXTS"])),
        }
        frozen = self.run / "registry.json"
        if frozen.exists():
            return set(json.loads(frozen.read_text())["extensions"])
        write_json(frozen, snapshot)
        return set(snapshot["extensions"])

    def fetch(self, url, raw=False):
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache / (key + ".json")
        if path.exists():
            cached = json.loads(path.read_text())
            with self.lock:
                self.receipts.append(cached["receipt"])
            if cached.get("failure"):
                raise RuntimeError(cached["failure"])
            return cached["body"], cached["headers"]
        last = None
        for attempt in range(2):
            try:
                request = urllib.request.Request(
                    url,
                    headers={"User-Agent": AGENT, "Accept": "*/*" if raw else "application/json"},
                )
                with urllib.request.urlopen(
                    request, timeout=self.config["timeout_seconds"]
                ) as response:
                    data = response.read(64 * 1024 * 1024 + 1)
                    if len(data) > 64 * 1024 * 1024:
                        raise ValueError("metadata response exceeds 64 MiB")
                    body = data.decode("utf-8") if raw else json.loads(data)
                    headers = {
                        k.lower(): v
                        for k, v in response.headers.items()
                        if k.lower() in ("link", "etag", "last-modified", "content-type")
                    }
                    receipt = {
                        "url": url,
                        "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "response_sha256": hashlib.sha256(data).hexdigest(),
                        "response_bytes": len(data),
                        "status": response.status,
                    }
                write_json(path, {"body": body, "headers": headers, "receipt": receipt})
                with self.lock:
                    self.receipts.append(receipt)
                return body, headers
            except (urllib.error.URLError, ValueError, TimeoutError, OSError) as exc:
                last = exc
                if isinstance(exc, urllib.error.HTTPError) and exc.code in (
                    400,
                    401,
                    403,
                    404,
                    429,
                ):
                    break
                if attempt == 0:
                    time.sleep(1)
        failure = f"{url}: {type(last).__name__}: {last}"
        receipt = {
            "url": url,
            "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": getattr(last, "code", None),
            "failure": failure,
        }
        write_json(path, {"failure": failure, "receipt": receipt})
        with self.lock:
            self.receipts.append(receipt)
        raise RuntimeError(failure)

    def error(self, source, project, exc):
        with self.lock:
            self.errors.append({"source": source, "project": project, "error": str(exc)})
        print(f"ERROR {source} {project}: {str(exc)[:160]}", flush=True)

    def project(self, source, project, **kwargs):
        return {"source": source, "project": str(project), "complete": True, **kwargs}

    def row(self, project, name, size, checksum=None, **kwargs):
        fmt, inner, outer = extension(name)
        source = project["source"]
        family = (
            "software-repositories"
            if source in ("github", "softwareheritage")
            else ("huggingface" if source.startswith("huggingface-") else source)
        )
        return {
            "source": source,
            "family": family,
            "project": project["project"],
            "owner": project.get("owner", "[unknown]"),
            "selection": project["selection"],
            "version": project.get("version"),
            "name": name,
            "format": fmt,
            "candidate_format": inner,
            "outer_extension": outer,
            "registered_outer_extension": outer in self.supported,
            "registered_format_extension": inner in self.supported,
            "size": integer(size),
            "checksum": checksum,
            **kwargs,
        }

    def commit(self, projects, rows):
        with self.lock:
            self.projects.extend(projects)
            self.rows.extend(rows)

    def zenodo(self):
        projects, rows, seen = [], [], set()
        for selection in self.config["zenodo"]:
            # Public unauthenticated API now caps each response at 25 records.
            records = []
            failed = False
            for page in range(1, (selection["size"] + 24) // 25 + 1):
                url = "https://zenodo.org/api/records?" + urllib.parse.urlencode(
                    {"q": selection["query"], "size": 25, "page": page, "sort": "mostrecent"}
                )
                try:
                    data, _ = self.fetch(url)
                    records.extend(data["hits"]["hits"])
                except Exception as exc:
                    self.error("zenodo", selection["label"] + f"-page-{page}", exc)
                    failed = True
                    break
            for record in records[: selection["size"]]:
                concept = str(record.get("conceptrecid") or record["id"])
                if concept in seen:
                    continue
                seen.add(concept)
                meta = record["metadata"]
                creators = meta.get("creators", [])
                owner = (
                    " | ".join(sorted(c.get("orcid") or c.get("name", "") for c in creators))
                    or "[unknown]"
                )
                project = self.project(
                    "zenodo",
                    concept,
                    selection=selection["label"],
                    version=str(record["id"]),
                    owner=owner,
                    title=meta.get("title"),
                    license=meta.get("license"),
                    access=meta.get("access_right"),
                    record_url=record.get("links", {}).get("self_html"),
                    publication_date=meta.get("publication_date"),
                )
                projects.append(project)
                for file in record.get("files", []):
                    rows.append(
                        self.row(
                            project,
                            file["key"],
                            file.get("size"),
                            file.get("checksum"),
                            url=file.get("links", {}).get("self"),
                            available=meta.get("access_right") == "open",
                            role="original",
                            mime=None,
                        )
                    )
            print(f"zenodo {selection['label']}: {len(records)} hits, failed={failed}", flush=True)
        self.commit(projects, rows)

    def figshare(self):
        projects, rows = [], []
        count = self.config["figshare"]["recent"]
        selected = []
        for page in range(1, (count + 99) // 100 + 1):
            url = "https://api.figshare.com/v2/articles?" + urllib.parse.urlencode(
                {
                    "page_size": 100,
                    "page": page,
                    "order": "published_date",
                    "order_direction": "desc",
                }
            )
            try:
                data, _ = self.fetch(url)
                selected.extend(data)
            except Exception as exc:
                self.error("figshare", f"selection-page-{page}", exc)
        # Fixed page size keeps the second page's offset at 100.
        selected = list({d["id"]: d for d in selected}.values())[:count]
        for item in selected:
            try:
                record, _ = self.fetch(item["url"])
                project = self.project(
                    "figshare",
                    record["id"],
                    selection="recent-publications",
                    owner=" | ".join(str(a["id"]) for a in record.get("authors", []))
                    or "[unknown]",
                    group_id=record.get("group_id"),
                    version=record.get("version"),
                    title=record.get("title"),
                    license=record.get("license"),
                    record_url=record.get("url_public_html"),
                    publication_date=record.get("published_date"),
                )
                projects.append(project)
                for file in record.get("files", []):
                    rows.append(
                        self.row(
                            project,
                            file["name"],
                            file.get("size"),
                            "md5:" + file["computed_md5"] if file.get("computed_md5") else None,
                            url=file.get("download_url"),
                            available=not file.get("is_link_only"),
                            file_id=file["id"],
                            role="original",
                            mime=file.get("mimetype"),
                        )
                    )
            except Exception as exc:
                self.error("figshare", item["id"], exc)
        print(f"figshare: {len(projects)} articles, {len(rows)} files", flush=True)
        self.commit(projects, rows)

    def dataverse(self):
        projects, rows, selected = [], [], []
        count = self.config["dataverse"]["recent"]
        for start in range(0, count, 100):
            url = "https://dataverse.harvard.edu/api/search?" + urllib.parse.urlencode(
                {
                    "q": "*",
                    "type": "dataset",
                    "per_page": min(100, count - start),
                    "start": start,
                    "sort": "date",
                    "order": "desc",
                }
            )
            try:
                data, _ = self.fetch(url)
                selected.extend(data["data"]["items"])
            except Exception as exc:
                self.error("dataverse", f"selection-start-{start}", exc)
        for item in selected:
            pid = item["global_id"]
            planned = self.project(
                "dataverse",
                pid,
                selection="recent-publications",
                owner=" | ".join(sorted(set(item.get("authors", [])))) or "[unknown]",
                collection=item.get("identifier_of_dataverse"),
                title=item.get("name"),
                record_url=item.get("url"),
                complete=False,
            )
            if (
                "harvested"
                in (
                    item.get("publisher", "") + " " + item.get("identifier_of_dataverse", "")
                ).lower()
            ):
                planned["skipped"] = "harvested metadata; files hosted outside Harvard"
                projects.append(planned)
                continue
            try:
                url = "https://dataverse.harvard.edu/api/datasets/:persistentId/?" + (
                    urllib.parse.urlencode({"persistentId": pid})
                )
                data, _ = self.fetch(url)
                record = data["data"]
                version = record["latestVersion"]
                project = self.project(
                    "dataverse",
                    pid,
                    selection="recent-publications",
                    owner=planned["owner"],
                    collection=planned.get("collection"),
                    version=f"{version['versionNumber']}.{version['versionMinorNumber']}",
                    version_state=version["versionState"],
                    title=item.get("name"),
                    license=version.get("license"),
                    record_url=record.get("persistentUrl"),
                )
                projects.append(project)
                for file in version.get("files", []):
                    f = file["dataFile"]
                    original = f.get("originalFileName")
                    name = original or f["filename"]
                    name = "/".join(p for p in (file.get("directoryLabel", ""), name) if p)
                    # Ingest checksum belongs to the tabular derivative, not the original upload.
                    checksum = f.get("checksum", {})
                    ck = (
                        checksum.get("type", "").lower() + ":" + checksum["value"]
                        if checksum.get("value") and not original
                        else None
                    )
                    rows.append(
                        self.row(
                            project,
                            name,
                            f.get("originalFileSize") if original else f.get("filesize"),
                            ck,
                            url=(
                                "https://dataverse.harvard.edu/api/access/datafile/"
                                f"{f['id']}?format=original"
                            ),
                            file_id=f["id"],
                            available=not file.get("restricted", False),
                            mime=f.get("originalFileFormat") if original else f.get("contentType"),
                            stored_name=f["filename"],
                            stored_size=f.get("filesize"),
                            original_upload=bool(original),
                            role="original",
                        )
                    )
            except Exception as exc:
                projects.append(planned)
                self.error("dataverse", pid, exc)
        print(f"dataverse: {len(projects)} datasets, {len(rows)} files", flush=True)
        self.commit(projects, rows)

    def huggingface(self):
        projects, rows = [], []
        limit = self.config["huggingface"]["per_selection"]
        for kind in ("datasets", "models"):
            seen = set()
            for sort in ("downloads", "lastModified"):
                url = f"https://huggingface.co/api/{kind}?" + urllib.parse.urlencode(
                    {"limit": limit, "sort": sort, "direction": -1}
                )
                try:
                    items, _ = self.fetch(url)
                except Exception as exc:
                    self.error("huggingface-" + kind, sort, exc)
                    continue
                for item in items:
                    name = item["id"]
                    if name in seen:
                        continue
                    seen.add(name)
                    source = "huggingface-" + kind
                    project = self.project(
                        source,
                        name,
                        selection=sort,
                        owner=name.split("/")[0],
                        version=item.get("sha"),
                        downloads=item.get("downloads"),
                        license=[t for t in item.get("tags", []) if t.startswith("license:")],
                        record_url="https://huggingface.co/"
                        + ("datasets/" if kind == "datasets" else "")
                        + name,
                        gated=item.get("gated"),
                        directories=0,
                    )
                    if item.get("private") or item.get("gated"):
                        project.update(complete=False, skipped="gated/private")
                        projects.append(project)
                        continue
                    try:
                        if not project["version"]:
                            detail, _ = self.fetch(f"https://huggingface.co/api/{kind}/{name}")
                            project["version"] = detail["sha"]
                        sha = project["version"]
                        url = (
                            f"https://huggingface.co/api/{kind}/{name}/tree/{sha}"
                            "?recursive=true&limit=1000"
                        )
                        for page in range(self.config["huggingface"]["max_tree_pages"]):
                            files, headers = self.fetch(url)
                            for file in files:
                                if file["type"] != "file":
                                    project["directories"] += 1
                                    continue
                                lfs = file.get("lfs") or {}
                                ck = (
                                    "sha256:" + lfs["oid"]
                                    if lfs.get("oid")
                                    else ("git-sha1:" + file["oid"] if file.get("oid") else None)
                                )
                                rows.append(
                                    self.row(
                                        project,
                                        file["path"],
                                        lfs.get("size", file.get("size")),
                                        ck,
                                        url=project["record_url"]
                                        + f"/resolve/{sha}/"
                                        + urllib.parse.quote(file["path"], safe="/"),
                                        available=True,
                                        role="repository",
                                        lfs=bool(lfs),
                                        xet=bool(file.get("xetHash")),
                                    )
                                )
                            link = headers.get("link", "")
                            match = re.search(r'<([^>]+)>; rel="next"', link)
                            if not match:
                                break
                            url = match.group(1)
                            if urllib.parse.urlparse(url).hostname != "huggingface.co":
                                raise ValueError("unexpected pagination host")
                        else:
                            project.update(
                                complete=False, truncated="tree page budget", next_url=url
                            )
                    except Exception as exc:
                        project["complete"] = False
                        self.error(source, name, exc)
                    projects.append(project)
                print(f"huggingface {kind} {sort}: {len(projects)} total projects", flush=True)
        self.commit(projects, rows)

    def softwareheritage(self):
        projects, rows = [], []
        base = "https://archive.softwareheritage.org/api/1/"
        rate_limited = False
        for origin in self.config["softwareheritage"]["origins"]:
            project = self.project(
                "softwareheritage",
                origin,
                selection="purposive-format-fixtures",
                owner=origin.rsplit("/", 2)[-2],
                record_url=origin,
                directory_requests=0,
            )
            if rate_limited:
                project.update(complete=False, skipped="source rate limit reached")
                projects.append(project)
                continue
            try:
                visit, _ = self.fetch(
                    base + "origin/" + origin + "/visit/latest/?require_snapshot=true"
                )
                snapshot, _ = self.fetch(visit["snapshot_url"] + "?branches_count=1000")
                branches = snapshot["branches"]
                head = branches.get("HEAD")
                visited = set()
                while head and head["target_type"] == "alias":
                    if head["target"] in visited:
                        raise ValueError("snapshot alias cycle")
                    visited.add(head["target"])
                    head = branches.get(head["target"])
                if not head or head["target_type"] != "revision":
                    raise ValueError("no revision HEAD in first 1000 snapshot branches")
                revision, _ = self.fetch(base + "revision/" + head["target"] + "/")
                project.update(
                    version=head["target"],
                    snapshot=visit["snapshot"],
                    visit_date=visit["date"],
                    root_directory=revision["directory"],
                )
                queue = collections.deque([(revision["directory"], "")])
                while (
                    queue
                    and project["directory_requests"]
                    < self.config["softwareheritage"]["max_directories"]
                ):
                    directory, prefix = queue.popleft()
                    entries, _ = self.fetch(base + "directory/" + directory + "/")
                    project["directory_requests"] += 1
                    for entry in entries:
                        name = prefix + entry["name"]
                        if entry["type"] == "dir":
                            queue.append((entry["target"], name + "/"))
                        elif entry["type"] == "file" and entry.get("perms") in (33188, 33261):
                            checksums = entry.get("checksums") or {}
                            ck = (
                                "sha256:" + checksums["sha256"]
                                if checksums.get("sha256")
                                else ("git-sha1:" + entry["target"])
                            )
                            rows.append(
                                self.row(
                                    project,
                                    name,
                                    entry.get("length"),
                                    ck,
                                    url=base + "content/sha1_git:" + entry["target"] + "/raw/",
                                    available=entry.get("status") == "visible",
                                    role="repository",
                                )
                            )
                if queue:
                    project.update(
                        complete=False,
                        truncated="directory budget",
                        remaining_directories=len(queue),
                    )
            except Exception as exc:
                project["complete"] = False
                self.error("softwareheritage", origin, exc)
                rate_limited = "429" in str(exc)
            projects.append(project)
            print(
                f"softwareheritage {origin}: {project['directory_requests']} directories",
                flush=True,
            )
        self.commit(projects, rows)

    def internetarchive(self):
        projects, rows = [], []
        for kind in self.config["internetarchive"]["types"]:
            url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
                {
                    "q": f"mediatype:{kind} AND NOT access-restricted-item:true",
                    "fl[]": "identifier",
                    "rows": self.config["internetarchive"]["per_type"],
                    "sort[]": "publicdate desc",
                    "output": "json",
                }
            )
            try:
                data, _ = self.fetch(url)
            except Exception as exc:
                self.error("internetarchive", kind, exc)
                # Same host timed out twice; don't repeat identical connectivity failure.
                if "timed out" in str(exc):
                    break
                continue
            for item in data["response"]["docs"]:
                name = item["identifier"]
                try:
                    data, _ = self.fetch("https://archive.org/metadata/" + urllib.parse.quote(name))
                    project = self.project(
                        "internetarchive",
                        name,
                        selection="recent-" + kind,
                        owner="[unknown]",
                        record_url="https://archive.org/details/" + name,
                    )
                    projects.append(project)
                    for file in data.get("files", []):
                        rows.append(
                            self.row(
                                project,
                                file["name"],
                                file.get("size"),
                                "md5:" + file["md5"] if file.get("md5") else None,
                                mime=file.get("format"),
                                role=file.get("source", "unknown"),
                                available=not file.get("private"),
                                url=f"https://archive.org/download/{name}/"
                                + urllib.parse.quote(file["name"]),
                            )
                        )
                except Exception as exc:
                    self.error("internetarchive", name, exc)
        self.commit(projects, rows)

    def github(self):
        path = ROOT / self.config["github_inventory"]
        if not path.exists():
            self.error(
                "github", "existing-pilot", "inventory file unavailable; run GitHub pilot first"
            )
            return
        projects, rows, seen = [], [], set()
        for line in path.open(encoding="utf-8"):
            row = json.loads(line)
            repo = row["repository"]
            project = self.project(
                "github",
                repo,
                selection="existing-purposive-pilot",
                version=row["commit_sha"],
                owner=repo.split("/")[0],
                record_url="https://github.com/" + repo,
            )
            if repo not in seen:
                projects.append(project)
                seen.add(repo)
            rows.append(
                self.row(
                    project,
                    row["path"],
                    row["size"],
                    "git-sha1:" + row["blob_sha"],
                    available=True,
                    role=row["role"],
                    url="https://raw.githubusercontent.com/"
                    + repo
                    + "/"
                    + row["commit_sha"]
                    + "/"
                    + (urllib.parse.quote(row["path"], safe="/")),
                )
            )
        self.commit(projects, rows)
        write_json(
            self.output / "github-import.json",
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "files": len(rows),
            },
        )

    def reference_censuses(self):
        ccbase = "https://commoncrawl.github.io/cc-crawl-statistics/plots/"
        commonsbase = "https://commons.wikimedia.org/wiki/"
        urls = {
            "commoncrawl-header.csv": ccbase + "mimetypes.csv",
            "commoncrawl-detected.csv": ccbase + "mimetypes_detected.csv",
            "commons-media-statistics.html": commonsbase + "Special:MediaStatistics",
        }
        for name, url in urls.items():
            try:
                data, _ = self.fetch(url, raw=True)
                (self.output / name).write_text(data, encoding="utf-8")
            except Exception as exc:
                self.error("reference-censuses", name, exc)

    def summarize(self):
        self.rows.sort(key=lambda r: (r["source"], r["project"], r["name"]))
        self.projects.sort(key=lambda r: (r["source"], r["project"]))
        self.output.mkdir(parents=True, exist_ok=True)
        with (self.output / "inventory.jsonl.gz").open("wb") as target:
            with gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as file:
                for row in self.rows:
                    file.write(
                        (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
                            "utf-8"
                        )
                    )
        write_json(self.output / "projects.json", self.projects)
        write_json(
            self.output / "errors.json",
            sorted(self.errors, key=lambda e: (e["source"], str(e["project"]))),
        )
        write_json(
            self.output / "receipts.json",
            sorted({r["url"]: r for r in self.receipts}.values(), key=lambda r: r["url"]),
        )
        for name in ("registry.json", "config.json"):
            (self.output / name).write_bytes((self.run / name).read_bytes())
        formats = []
        by_format = collections.defaultdict(list)
        for row in self.rows:
            by_format[(row["source"], row["format"])].append(row)
        for (source, fmt), rows in sorted(by_format.items()):
            formats.append({"source": source, "format": fmt, **metrics(rows)})
        write_csv(self.output / "formats-by-source.csv", formats)
        discovered = collections.defaultdict(list)
        for row in self.rows:
            if not row["registered_format_extension"]:
                discovered[row["candidate_format"]].append(row)
        write_csv(
            self.output / "unregistered-extensions.csv",
            sorted(
                [
                    {
                        "extension": ext,
                        "sources": ";".join(sorted({r["source"] for r in rows})),
                        "outer_stream_supported_files": sum(
                            r["registered_outer_extension"] for r in rows
                        ),
                        **metrics(rows),
                    }
                    for ext, rows in discovered.items()
                ],
                key=lambda r: -r["bytes"],
            ),
        )
        sources = []
        for source in sorted(
            {r["source"] for r in self.projects} | {e["source"] for e in self.errors}
        ):
            rows = [r for r in self.rows if r["source"] == source]
            projects = [p for p in self.projects if p["source"] == source]
            sources.append(
                {
                    "source": source,
                    "projects_selected": len(projects),
                    "projects_complete": sum(p["complete"] for p in projects),
                    "errors": sum(e["source"] == source for e in self.errors),
                    **metrics(rows),
                }
            )
        write_csv(self.output / "sources.csv", sources)
        candidates = []
        for fmt in self.config["candidate_formats"]:
            fmt = ALIASES.get(fmt, fmt)
            if any(c["format"] == fmt for c in candidates):
                continue
            rows = [
                r
                for r in self.rows
                if r["candidate_format"] == fmt and r.get("role") not in ("derivative", "metadata")
            ]
            candidates.append(
                {
                    "format": fmt,
                    "registered_extension": fmt in self.supported,
                    "families": ";".join(sorted({r["family"] for r in rows})),
                    "sources": ";".join(sorted({r["source"] for r in rows})),
                    "outer_stream_supported_files": sum(
                        r["registered_outer_extension"] for r in rows
                    ),
                    **metrics(rows),
                }
            )
        write_csv(self.output / "candidates.csv", sorted(candidates, key=lambda c: -c["bytes"]))
        write_json(
            self.output / "audit.json",
            {
                "total": metrics(self.rows),
                "row_count": len(self.rows),
                "source_file_count_sum": sum(s["files"] for s in sources),
                "source_bytes_sum": sum(s["bytes"] for s in sources),
                "format_file_count_sum": sum(f["files"] for f in formats),
                "format_bytes_sum": sum(f["bytes"] for f in formats),
                "claims": (
                    "Extension inventory and API-declared bytes/checksums; "
                    "not content validation or a platform probability sample."
                ),
            },
        )
        print(
            json.dumps(
                {
                    "output": str(self.output),
                    "files": len(self.rows),
                    "projects": len(self.projects),
                    "errors": len(self.errors),
                }
            ),
            flush=True,
        )


def metrics(rows):
    known = [r for r in rows if r["checksum"] and r["size"] is not None]
    # Include size and algorithm: Git object IDs are not raw file SHA-1 hashes.
    unique = {(r["checksum"], r["size"]) for r in known}
    return {
        "files": len(rows),
        "bytes": sum(r["size"] or 0 for r in rows),
        "missing_sizes": sum(r["size"] is None for r in rows),
        "projects": len({(r["source"], r["project"]) for r in rows}),
        "owners": len({(r["family"], r["owner"]) for r in rows if r["owner"] != "[unknown]"}),
        "checksum_files": len(known),
        "unique_known_checksum_size": len(unique),
        "unique_known_bytes": sum(size for _, size in unique),
        "available_files": sum(bool(r.get("available")) for r in rows),
    }


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=pathlib.Path, default=HERE / "config.json")
    parser.add_argument("--run", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument(
        "--sources",
        nargs="+",
        default=[
            "zenodo",
            "figshare",
            "dataverse",
            "huggingface",
            "softwareheritage",
            "internetarchive",
            "github",
            "reference_censuses",
        ],
    )
    args = parser.parse_args()
    args.run.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    frozen = args.run / "config.json"
    if not frozen.exists():
        frozen.write_bytes(args.config.read_bytes())
    config = json.loads(frozen.read_text())
    survey = Survey(config, args.run, args.output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=config["workers"]) as pool:
        tasks = {pool.submit(getattr(survey, source)): source for source in args.sources}
        for task in concurrent.futures.as_completed(tasks):
            try:
                task.result()
            except Exception as exc:
                survey.error(tasks[task], "source-task", exc)
    survey.summarize()


if __name__ == "__main__":
    main()
