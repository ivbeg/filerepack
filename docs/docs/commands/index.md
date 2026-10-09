---
title: "CLI Reference"
description: "Index of filerepack CLI commands"
slug: /commands
---

# CLI Reference

All commands are available as `filerepack <command>`. Use
`filerepack <command> --help` for the live flag list. Flags that appear on both
`repack` and `bulk` are documented under
[Shared CLI options](/commands/shared-options).

```bash
filerepack doctor
filerepack inspect <path> [OPTIONS]
filerepack repack <file> [OPTIONS]
filerepack bulk <directory> [OPTIONS]
filerepack repack-store <store> --output-dir <parent> [OPTIONS]
filerepack inspect-dcp <checkpoint-directory> [OPTIONS]
```

## Commands

| Command | Page |
|---------|------|
| Shared flags | [`/commands/shared-options`](/commands/shared-options) |
| `repack` | [`/commands/repack`](/commands/repack) |
| `bulk` | [`/commands/bulk`](/commands/bulk) |
| `inspect` | [`/commands/inspect`](/commands/inspect) |
| `repack-store` | [`/commands/repack-store`](/commands/repack-store) |
| `inspect-dcp` | [`/commands/inspect-dcp`](/commands/inspect-dcp) |
| `doctor` | [`/commands/doctor`](/commands/doctor) |
| Reports and resume | [`/commands/reports-and-resume`](/commands/reports-and-resume) |

## Exit codes

For `repack` and `bulk`:

- `0` — successful completion, including unchanged files and intentional skips
- `1` — application validation error, missing path, unsupported work, fatal failure or fail-fast error
- `2` — argument-parser usage error, or item failures in `bulk --continue-on-error`
- `130` — user interruption

`inspect` exits `0` after a completed inspection even when items are blocked.
`doctor` exits `1` if `7zz`/`7z` is missing; optional-tool absence alone does not
make it fail. See the individual command pages for store and DCP outcomes.

## See also

- [Formats](/formats/)
- [External tools](/tools/)
- [Python library](/library/)
