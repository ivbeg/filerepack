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
filerepack repack <file> [OPTIONS]
filerepack bulk <directory> [OPTIONS]
```

## Commands

| Command | Page |
|---------|------|
| Shared flags | [`/commands/shared-options`](/commands/shared-options) |
| `repack` | [`/commands/repack`](/commands/repack) |
| `bulk` | [`/commands/bulk`](/commands/bulk) |
| `doctor` | [`/commands/doctor`](/commands/doctor) |

## Exit codes

- `0` — success
- `1` — usage error, missing path, or a failure without `--continue-on-error`
- `2` — some files failed while `--continue-on-error` was set
- `filerepack doctor` exits `1` if `7zz`/`7z` is missing

## See also

- [Formats](/formats/)
- [External tools](/tools/)
- [Python library](/library/)
