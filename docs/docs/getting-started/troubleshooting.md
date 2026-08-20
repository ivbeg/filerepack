---
title: "Troubleshooting"
description: "Exit codes, missing tools, and files that do not shrink"
---
# Troubleshooting

This guide covers exit codes, missing binaries, and common “nothing changed”
cases. Live help: `filerepack <command> --help`. Tool inventory: `filerepack doctor`.

## Exit codes

- `0` — success
- `1` — usage error, missing path, or a failure without `--continue-on-error`
- `2` — some files failed while `--continue-on-error` was set
- `filerepack doctor` exits `1` if `7zz`/`7z` is missing

`filerepack doctor` prints install commands for the current OS after the tool
table when anything is missing.

## Missing tools

A missing optional tool leaves that format unchanged. Only `7zz` or `7z` is
required for archive and OOXML work.

```bash
filerepack doctor
```

Override a tool path with `FILEREPACK_7ZZ` (and similar) or:

```toml
# ~/.config/filerepack/config.toml
[tools]
szip = "/opt/homebrew/bin/7zz"
qpdf = "/usr/local/bin/qpdf"
```

`mp3packer` and `optivorbis` are not in Homebrew, apt, or Chocolatey. See
[External tools](/tools/).

## The file did not shrink

- Lossless JPEG/PNG/PDF often save little if the file is already optimized. Try `--ultra` for PNG/Parquet/MP3, or opt into `--lossy` when quality loss is acceptable.
- Results that are not smaller are discarded unless `--allow-grow`.
- `--min-savings` can reject small wins.
- Encrypted or signed PDFs skip pikepdf image-stream walking.
- DICOM skips signed, non-image, and already-compressed instances. `--lossy` does not apply.
- Optional extras (`filerepack[pdf]`, `filerepack[media]`, `filerepack[data]`, …) must be installed for those packers.

## RAR became 7z

RAR is rewritten as `.7z` when the `rar` binary is missing. Install `rar` if you
need a RAR container back.

## OOXML files break in Word/Excel

OOXML-like files prefer Info-ZIP `zip` when it is on PATH so extra 7-Zip fields
do not break Word/Excel. Install `zip` and re-run `filerepack doctor`.

## Bulk stopped on one bad file

Pass `--continue-on-error`. Exit code `2` means some files failed. Default
skipped directories include `.git`, `.venv`, `node_modules`, and similar.

## Related docs

- [Installation](/getting-started/installation)
- [External tools](/tools/)
- [Safety](/getting-started/safety)
- [CLI reference](/commands/)
