# Public file-format discovery survey

This developer-only survey inventories public metadata and probes a small subset
of files to select potential filerepack formats. It does not add runtime handlers
or change the support matrix. The pilot was authorized on 2026-10-04.

The Russian findings are in `report-2026-10-04.md`; frozen public evidence is in
`pilot-2026-10-04/`. API caches, original downloads and store metadata remain in
the existing ignored `dev/format_survey/runs/` directory.

## Reproduce locally

Run from the repository root with Python 3.9 or later. The scripts use the standard
library; Black was used only for formatting during development.

```sh
python3 dev/format_survey/multisource/collect.py \
  --run dev/format_survey/runs/multisource-2026-10-04 \
  --output dev/format_survey/multisource/pilot-2026-10-04
python3 dev/format_survey/multisource/probe.py \
  --inventory dev/format_survey/multisource/pilot-2026-10-04/inventory.jsonl.gz \
  --run dev/format_survey/runs/multisource-2026-10-04 \
  --output dev/format_survey/multisource/pilot-2026-10-04
python3 dev/format_survey/multisource/stores.py \
  --run dev/format_survey/runs/multisource-2026-10-04 \
  --output dev/format_survey/multisource/pilot-2026-10-04
python3 dev/format_survey/multisource/audit.py \
  --output dev/format_survey/multisource/pilot-2026-10-04 \
  --run dev/format_survey/runs/multisource-2026-10-04
```

Collection requires public network access on the first run. A repeated run reuses
the frozen configuration, registry and cached responses, including failed HTTP
requests. Use a new run and output directory to refresh sources or retry source
limits. Compression timings are fresh measurements on each probe run.
`--sources` selects a subset and writes an inventory of that subset; use a
separate output directory for it.

The GitHub augmentation imports the existing pilot's inventory without new
GitHub requests. Its input path and SHA-256 are recorded in `github-import.json`.
If that ignored input is unavailable, the collector reports the missing source.
Run the parent GitHub collector first, or omit GitHub for a new survey. The
published combined inventory can still be audited without that original cache.

## Selection and bounds

- Zenodo: 100 most recent dataset hits and 100 most recently updated hits with
  publication dates in September 2026. Concepts are deduplicated across both
  selections. Public pages are limited to 25 records.
- Figshare: first 150 most recent public articles; retain distinct file IDs even
  when their basenames collide. This includes journal supplements.
- Harvard Dataverse: 150 most recent search hits. Skip entries explicitly labelled
  harvested, since Harvard's file API does not inventory their external hosts.
  Use original upload names/sizes; ingested `.tab` files are not added again.
  Ingested-file checksums are not assigned to original uploads.
- Hugging Face: 25 most downloaded and 25 most recently modified repositories for
  each of datasets and models. Pin commit SHA before walking trees, follow up to
  six pages of 1,000 entries, skip gated/private repositories, and expose
  truncation. LFS payload size and SHA-256 are used instead of pointer size/hash.
- Software Heritage: three purposive GitHub origins, latest archived HEAD,
  breadth-first walk with a budget of 120 directories per origin. Stop new
  requests to this source after HTTP 429. Count regular files only.
- Internet Archive: intended selection of 25 recent items for each of data,
  software and texts, preserving original/derivative roles separately. This
  pilot obtained no inventory because TLS handshakes timed out.
- Common Crawl and Commons: save official aggregate CSV/HTML responses and
  extract recent crawls and numeric media tables. These are separate censuses,
  not additional file rows in the pilot.

An HTTP response is bounded to 64 MiB with a 20-second socket timeout and at most
two attempts. Five independent sources may run concurrently. A socket timeout
does not constitute a hard total request deadline.

File probes rotate projects deterministically within each requested format,
ordering files by a seeded URL hash. Download at most 8 MiB per file and 64 MiB
overall; decode R streams up to 32 MiB and XZ with a 128 MiB decoder memory limit.
These are small-file discovery probes, not a byte-representative benchmark.
No R, Python pickle or model objects are executed. ZIP members are listed from
the central directory without extraction or decompression; at most 5,000 members
per sampled archive. Signature checks do not establish format conformance.

Named `.zarr` stores are grouped by ancestor directory. Up to ten consolidated
metadata anchors of 1 MiB each may be fetched and checked; array chunks are not
decoded. Unnamed stores and stores embedded in archives can be missed.

## Evidence and interpretation

`inventory.jsonl.gz` contains source, project, author/account group, selection,
version, path, extension, inner/outer compression suffixes, nominal bytes,
checksum type/value, availability and download URL. API-reported licence and
record metadata are retained in `projects.json`. Licence metadata alone is not
a per-file redistribution determination; downloaded corpus bytes are not shipped.

`formats-by-source.csv` counts occurrences and bytes by source. `candidates.csv`
checks a predetermined list of potential formats, including zero observations.
`unregistered-extensions.csv` discovers all other extensions automatically,
including source code, numeric chunk names and ambiguous binary suffixes. Being
absent from the registry does not by itself make an extension a useful candidate.

Checksum equivalence uses algorithm, digest and size together. Plain SHA-1 and
Git blob SHA-1 are different namespaces; different hash algorithms are not merged.
MD5 equivalence is metadata evidence, not proof of globally unique content.
Rows lacking checksums remain in occurrence and byte totals. Matching objects,
versions and mirrors can still inflate project counts.

`owners` is a proxy: creator groups for Zenodo/Figshare/Dataverse and namespaces
for repositories. It is not a verified number of independent people or institutions.
GitHub and Software Heritage share one source family; Hugging Face datasets and
models share another. Extension matches to filerepack's registry are routing
evidence only: `.ts` may mean TypeScript rather than a video transport stream.

`probes.json` records input hashes, identification, R serialization prefixes,
versions, gzip/XZ stream comparisons, encoded sizes, limits and environment.
Changed R streams are compared byte-for-byte after decoding; R reader validation
remains unavailable in this pilot. Failed/oversized cases have no measured saving.
Stream savings are research results and are not accepted filerepack output savings.
`nested-inventory.json` lists decoded member sizes separately from container sizes.
`directory-stores.json` records Zarr metadata and observed store objects; these
objects already appear in the main inventory and must not be added to its totals.

`receipts.json` records request URLs, retrieval times, status and successful raw
response hashes. Cached API JSON is normalized locally, so its serialization is
not the original response byte sequence. `independent-audit.json` recomputes
counts and bytes from delivered inventory, checks source/file identities and
registry flags, and verifies that Commons table sums equal its published totals.
`SHA256SUMS` fingerprints the delivered scripts and evidence.

The sample is purposive and partly truncated. It cannot estimate platform-wide
format prevalence, global unique bytes, compression savings or worldwide adoption.
