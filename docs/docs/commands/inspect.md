---
title: "inspect"
description: "Read-only eligibility, prerequisite and destination inspection"
sidebar_position: 4
---

# Inspect

```bash
filerepack inspect <path> [OPTIONS]
```

`filerepack inspect PATH --json` plans processing without running an encoder,
extracting payloads, or creating output, backup or processing files. A single
file produces one JSON object. A directory produces one JSON object per line,
followed by a summary containing `scan_complete`.

```bash
filerepack inspect document.docx --json --output-dir ./outputs
filerepack inspect ./input --json --profile preserve
```

Without `--json`, the command prints a human-readable item list and blockers.

| Flag | Meaning |
| --- | --- |
| `--json` | One JSON object for a file; JSONL items plus summary for a directory |
| `--output-dir PATH` | Inspect proposed destinations without creating them |
| `--overwrite` | Evaluate existing destinations with overwrite permission |
| `--backup` / `--backup-dir` | Inspect required backup paths and conflicts |
| `--profile fast\|balanced\|maximum\|preserve` | Inspect effective profile settings |
| `--sqlite-offline` | Evaluate the explicit in-place SQLite offline policy |

Inspection has its own option set and does not accept all `repack`/`bulk` flags.
Directory inspection scans recognized filenames, includes top-level ZIP files and
excludes the proposed output tree. Use `inspect-dcp` for a flat DCP inventory and
`repack-store --dryrun` for complete Zarr store inspection.

The version 1 record includes format capabilities, missing prerequisites,
protection (`protected`, `unprotected`, or `unknown`), destination conflicts,
proposed paths, effective settings and estimates with their provenance.
Protection remains `unknown` when bounded inspection cannot establish safety.
Absence of familiar ZIP signature names does not prove that a package is safe.
Compressed streams are identified by extension during inspection; execution may
detect a WARC or tar payload and change its route after a bounded content probe.

`candidate_savings` is unknown: inspection never measures compressed candidates.
Use `repack --dryrun` to measure them for ordinary formats; scientific, NIB and
CAR dry-runs also inspect without encoding. Execution repeats validation and
path checks, so an earlier inspection cannot authorize publication.

Exit codes: 0 for completed inspection, including blocked items; 1 for an invalid
invocation or failed inspection; 130 for interruption. Argument-parser usage
errors exit 2. ZIP listings are limited
to a 1 MiB central directory and 10,000 entries; ZIP64 listings are outside this
inspection profile. File and directory symlinks are excluded.
