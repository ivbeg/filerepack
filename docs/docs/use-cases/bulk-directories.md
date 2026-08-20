---
title: "Bulk directories"
description: "Walk a tree with jobs, filters, progress, and continue-on-error"
---
# Bulk directories

`filerepack bulk` scans a directory and runs the same packers as `repack`.

```bash
filerepack bulk ./documents --jobs auto --progress
filerepack bulk ./photos --include-ext jpg,png,webp --progress
filerepack bulk ./archives --include-ext tar.gz --progress
```

`bulk` needs `--progress` (unlike `repack`, which is on for a TTY). Install
`filerepack[progress]` for a `rich` bar.

## Filters

| Flag | Meaning |
|------|---------|
| `--include-ext` / `--exclude-ext` | Comma-separated extension filters |
| `--min-size` / `--max-size` | Size filters (`1MB`, `100KB`, …) |
| `--min-savings PCT` | Keep result only if savings ≥ PCT |
| `--exclude-dir` | Extra directory names to skip |
| `--skip-zip` / `--no-skip-zip` | Skip top-level `.zip` (default: skip) |

`--include-ext tar.gz` matches compound names. `--include-ext gz` and
`--include-ext jpg` also match aliases (`.tgz`, `.jpeg`, `.thm`, …).

Default skipped directories: `.git`, `.hg`, `.svn`, `.tox`, `.venv`, `venv`,
`node_modules`, `__pycache__`, `.mypy_cache`, `.pytest_cache`.

## Parallelism and errors

```bash
filerepack bulk ./documents --min-size 1MB --min-savings 5 --jobs auto --continue-on-error
```

`--jobs auto` uses a process pool. `--continue-on-error` does not stop the scan
on a failure (exit code `2` if some files failed).

Size arguments accept `1000`, `1KB`, `1.5MB`, `2GB`.

See [`bulk`](/commands/bulk) and [shared options](/commands/shared-options).
