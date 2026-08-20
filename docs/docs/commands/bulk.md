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

`bulk` needs `--progress` to show a bar. Install `filerepack[progress]` for
`rich`; otherwise progress prints every N files.

## bulk-only flags

| Flag | Meaning |
|------|---------|
| `--skip-zip` / `--no-skip-zip` | Skip top-level `.zip` (default: skip) |
| `--include-ext` / `--exclude-ext` | Comma-separated extension filters. `--include-ext tar.gz` matches compound names; `--include-ext gz` and `--include-ext jpg` also match aliases (`.tgz`, `.jpeg`, `.thm`, …) |
| `--exclude-dir` | Extra directory names to skip |
| `--jobs N\|auto` | Process pool workers |
| `--continue-on-error` | Do not stop the scan on a failure |

Default skipped directories: `.git`, `.hg`, `.svn`, `.tox`, `.venv`, `venv`,
`node_modules`, `__pycache__`, `.mypy_cache`, `.pytest_cache`.

## Examples

```bash
filerepack bulk ./documents --min-size 1MB --min-savings 5 --jobs auto
filerepack bulk ./photos --include-ext jpg,png,webp,avif,jxl --progress
filerepack bulk ./archives --include-ext tar.gz --progress
filerepack bulk ./dicom --include-ext dcm --progress
filerepack bulk ./video --include-ext mp4,mkv,webm,mov --wmv-lossless
```

Exit code `2` means some files failed while `--continue-on-error` was set.

See [Bulk directories](/use-cases/bulk-directories).
