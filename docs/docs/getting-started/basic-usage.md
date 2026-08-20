---
title: "Basic usage"
description: "Lossless defaults, nested walking, extras, and common flags"
---
# Basic usage

filerepack has three commands: `repack`, `bulk`, and `doctor`.

```bash
filerepack doctor
filerepack repack <file> [OPTIONS]
filerepack bulk <directory> [OPTIONS]
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
| `--keep-meta` | Keep JPEG/PNG EXIF/ICC (default strips metadata) |
| `--allow-grow` | Keep output even if it is larger |

DICOM is always lossless JPEG-LS. `--lossy` does not apply.

## Nested walking

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten. Nested XML/JSON inside ZIP/OOXML/ODF/EPUB is
minified (text nodes kept). `--no-archives` skips nested archive rewriting.
`--no-images` skips image, video, and audio packers (including cover art), not
XML/JSON or PDF.

See [Formats](/formats/) for the walk order and extension lists.

## In place vs a copy

Rewrites go to a temp file, are verified, then `os.replace`d onto the original.
Use `--dryrun` to measure savings without writing. `--output-dir` writes results
elsewhere. `--backup` / `--backup-dir` copy the source first.

## Progress and machine-readable output

`filerepack repack` shows a progress bar on a TTY (`--no-progress` to hide it).
`bulk` needs `--progress`. Install `filerepack[progress]` for a `rich` bar;
otherwise progress prints every N files (`--progress-interval`).

`--json` and `--csv` emit machine-readable summaries (mutually exclusive).
`--stats` adds timing and counts.

## Related docs

- [Safety](/getting-started/safety)
- [Best practices](/getting-started/best-practices)
- [CLI reference](/commands/)
