---
title: "Basic usage"
description: "Lossless defaults, nested walking, extras, and common flags"
---
# Basic usage

Use `repack` for one file, `bulk` for a directory, `inspect` to check eligibility,
and `doctor` to check tools. Complete Zarr stores and DCP inventories have separate
commands.

```bash
filerepack doctor
filerepack inspect <path> [OPTIONS]
filerepack repack <file> [OPTIONS]
filerepack bulk <directory> [OPTIONS]
filerepack repack-store <store> --output-dir <parent> [OPTIONS]
filerepack inspect-dcp <checkpoint-directory> [OPTIONS]
```

Use `filerepack <command> --help` for the live flag list. Flags that appear on
both `repack` and `bulk` are documented under [Shared CLI options](/commands/shared-options).

## Lossless by default

JPEG, PNG, and PDF use **lossless** tools unless you pass `--lossy`,
`--jpeg-quality`, `--png-quality`, or `--pdf-profile`.

| Flag | Effect |
|------|--------|
| `--lossy` | Ghostscript PDF (`/ebook` unless `--pdf-profile`), jpegoptim `-m`, pngquant, lossy AVIF/HEIC |
| `--jpeg-quality 1-100` | Lossy JPEG; also re-encodes images inside PDFs |
| `--png-quality high\|medium\|low` | Lossy PNG via pngquant |
| `--pdf-profile` | Ghostscript Distiller preset (implies lossy PDF) |
| `--ultra` | Stronger lossless: Parquet zstd 22, `zopflipng` for PNG, `mp3packer -z` |
| `--keep-meta` | Retain incidental metadata where supported; lossless JPEG/PNG already retain required orientation and color information |
| `--allow-grow` | Keep output even if it is larger |

DICOM is always lossless JPEG-LS. `--lossy` does not apply.
Video defaults to stream-copy remuxing. Select `--video-mode lossless` to
re-encode losslessly, or `--video-mode lossy --lossy` to permit lossy encoding.

## Nested walking

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten. Nested XML/JSON inside ZIP/OOXML/ODF/EPUB is
minified (text nodes kept). `--no-archives` skips nested archive rewriting.
`--no-images` skips image, video, and audio packers (including cover art), not
XML/JSON or PDF.

See [Formats](/formats/) for the walk order and extension lists.

## In place vs a copy

Rewrites are staged, verified and atomically published onto the original.
Use `--dryrun` to measure candidates in scratch space without publishing files.
Scientific, NIB and CAR dry-runs inspect without encoding and report unchanged
sizes. `--output-dir` writes results
elsewhere and preserves the source, publishing an unchanged copy when no
improvement is accepted for ordinary supported inputs. Scientific, NIB, CAR and
WARC handlers create a distinct output only for an accepted candidate; refused
processing does not create a fallback copy. Existing different destinations require `--overwrite`.
`--backup` copies the source first; `--backup-dir` selects that backup directory
and must be used with `--backup`. Required backup failure stops processing.

## Progress and machine-readable output

`filerepack repack` shows a progress bar on a TTY (`--no-progress` to hide it).
`bulk` needs `--progress`. Install `filerepack[progress]` for a `rich` bar;
otherwise progress prints every N files (`--progress-interval`).

`--json` and `--csv` emit machine-readable summaries (mutually exclusive).
`--stats` adds timing and counts.

For persistent evidence use `--report run.jsonl`. Bulk jobs can save a completion
checkpoint with `--manifest run.manifest` and reuse verified work with
`--manifest run.manifest --resume`. See [reports and resume](/commands/reports-and-resume).

## Related docs

- [Safety](/getting-started/safety)
- [Best practices](/getting-started/best-practices)
- [CLI reference](/commands/)
