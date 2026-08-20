---
title: "Shared CLI options"
description: "Flags shared by filerepack repack and bulk"
---
# Shared CLI options

These flags apply to `repack` and `bulk` unless noted. JPEG/PNG/PDF are lossless
unless `--lossy`, `--pdf-profile`, or a quality flag is set. Results that are
not smaller are discarded unless `--allow-grow`.

| Flag | Meaning |
|------|---------|
| `--dryrun` | Measure savings; do not modify files |
| `--quiet` / `--verbose` / `--debug` | Verbosity |
| `--no-images` | Skip image, video, and audio packers (including cover art). XML/JSON/PDF still run |
| `--no-archives` | Skip nested archive rewriting |
| `--deep` / `--no-deep` | Walk inside archives (default: on); nested XML/JSON is minified |
| `--min-savings PCT` | Keep result only if savings ≥ PCT |
| `--min-size` / `--max-size` | Size filters (`1MB`, `100KB`, …) |
| `--backup` / `--backup-dir` | Copy source before rewriting |
| `--output-dir` | Write results here instead of in place |
| `--compression-level 1-9` | Archive compression (default 9) |
| `--jpeg-quality 1-100` | Implies lossy JPEG; also re-encodes images inside PDFs |
| `--png-quality high\|medium\|low` | Implies lossy PNG (pngquant) |
| `--pdf-profile` | Ghostscript Distiller preset: `screen`, `ebook`, `printer`, `prepress`, `default` (implies lossy PDF) |
| `--lossy` | Ghostscript PDF (`/ebook` unless `--pdf-profile` is set), jpegoptim `-m`, pngquant, lossy AVIF/HEIC |
| `--wmv-lossless` | Video CRF 0 (or VP9 lossless for WebM) |
| `--convert-container` / `--no-convert-container` | WMV/AVI/ASF → MP4 (default: convert) |
| `--allow-grow` | Keep output even if larger |
| `--keep-meta` | Keep JPEG/PNG metadata (default strips EXIF/ICC) |
| `--max-extract-size` | Skip archive extract if uncompressed size exceeds this (`0` disables; default 8GB, also 100× the archive) |
| `--ultra` | Stronger lossless passes: Parquet zstd 22, `zopflipng` for PNG, `mp3packer -z` |
| `--json` / `--csv` | Machine-readable output (mutually exclusive) |
| `--log-file PATH` | Also write CLI messages to a file |
| `--stats` | Extra timing / counts |
| `--progress` | Progress bar (`rich` if installed). `repack` is on for a TTY (`--no-progress` to hide); `bulk` needs `--progress` |
| `--progress-interval N` | Interval when `rich` is not installed (default 10) |

Lossy PDF defaults to Ghostscript `/ebook` (150 dpi) because `/prepress` barely
shrinks scanned pages. Use `--pdf-profile prepress` for the old print-quality
Ghostscript path. Lossless PDF walks embedded image streams when
`filerepack[pdf]` is installed; encrypted or signed PDFs skip that step. DICOM
is always lossless JPEG-LS (`gdcmconv` or `dcmcjpls`); `--lossy` does not apply.

Size arguments accept `1000`, `1KB`, `1.5MB`, `2GB`.

See [`repack`](/commands/repack), [`bulk`](/commands/bulk), and [Formats](/formats/).
