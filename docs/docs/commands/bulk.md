---
title: "bulk"
description: "Scan a directory and repack matching files in parallel"
---
# bulk

```bash
filerepack bulk <directory> [OPTIONS]
```

Walks a directory tree and runs the same packers as [`repack`](/commands/repack).
Shared flags: [Shared CLI options](/commands/shared-options).

`--output-dir` retains paths relative to the scanned directory and preserves
source bytes. Workers share the library's collision and required-backup rules;
use `--overwrite` explicitly for existing output/conversion targets. Invalid
common options are rejected before workers start.
The per-format output and dry-run exceptions described under
[`repack`](/commands/repack) also apply to bulk.

`bulk` needs `--progress` to show a bar. Install `filerepack[progress]` for
`rich`; otherwise progress prints every N files.

## bulk-only flags

| Flag | Meaning |
|------|---------|
| `--skip-zip` / `--no-skip-zip` | Skip top-level `.zip` (default: skip) |
| `--include-ext` / `--exclude-ext` | Comma-separated extension filters. `--include-ext tar.gz` matches compound names; `--include-ext gz` and `--include-ext jpg` also match aliases (`.tgz`, `.jpeg`, `.thm`, …) |
| `--exclude-dir` | Extra directory names to skip |
| `--jobs N\|auto` | Upper bound on workers (default: 1); auto starts from host CPU count, subject to resource grants |
| `--continue-on-error` | Do not stop the scan on a failure |
| `--bulk-max-memory-bytes` | Aggregate worker memory grants (default: 2147483648) |
| `--bulk-max-scratch-bytes` | Aggregate scratch grants (default: 8589934592) |
| `--bulk-max-cpu-threads` | Aggregate encoder thread grants (default: host CPU count) |
| `--manifest PATH` | Persist a content-verified completion checkpoint |
| `--resume` | Reuse compatible verified completion; requires `--manifest` |

Default skipped directories: `.git`, `.hg`, `.svn`, `.tox`, `.venv`, `venv`,
`node_modules`, `__pycache__`, `.mypy_cache`, `.pytest_cache`.
File/directory symlinks, output and backup trees, and owned report/checkpoint/log
files are excluded from discovery. `--exclude-dir` takes comma-separated names.

## Examples

```bash
filerepack bulk ./documents --min-size 1MB --min-savings 5 --jobs auto
filerepack bulk ./photos --include-ext jpg,png,webp,avif,jxl --progress
filerepack bulk ./archives --include-ext tar.gz --progress
filerepack bulk ./dicom --include-ext dcm --progress
filerepack bulk ./video --include-ext mp4,mkv,webm,mov --wmv-lossless
```

Exit code `2` means some files failed while `--continue-on-error` was set.
Argument-parser usage errors also exit `2`; inspect stderr to distinguish them.

Human output labels each file with `[SUCCESS]`, `[SKIPPED]`, `[ERROR]` or
`[CANCELLED]`. The final summary explicitly states `[SUCCESS] Bulk processing
completed.` or `[ERROR]`/`[CANCELLED]` when errors or interruption occurred.
An unchanged file with no size reduction is a successful result. Report,
checkpoint and scan failures also produce an error summary.

`--quiet` hides successful output while retaining errors on stderr. JSON/CSV
retain structured statuses without human labels on stdout. Exit codes remain
0 for clean completion, 1 for fatal or fail-fast errors, 2 for errors under
`--continue-on-error`, and 130 for user interruption.

See [Bulk directories](/use-cases/bulk-directories).
