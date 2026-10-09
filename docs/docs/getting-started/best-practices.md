---
title: "Best practices"
description: "Practical defaults for lossless repack, bulk jobs, and extras"
---
# Best practices

## Start lossless, measure first

- Run `filerepack doctor` after install so missing binaries are obvious.
- Use `--dryrun` (and `--stats`) on a sample before rewriting a tree.
- Keep JPEG/PNG/PDF lossless unless you explicitly want `--lossy` or a quality flag.
- Use `--allow-grow` only when a required layout, such as PDF linearization or record-based WARC gzip, matters more than size reduction. Some preserving profiles still require a smaller candidate.

## Nested files and Office

- Leave `--deep` on so images and XML inside `.docx` / `.xlsx` / ZIP are packed.
- Install Info-ZIP `zip` for OOXML so Word/Excel stay happy.
- Use `--no-images` when you only want XML/JSON minify and archive rewrite.

## Bulk directories

- Prefer `--jobs auto` on multi-core machines.
- Filter with `--include-ext` / `--exclude-ext` and `--min-size` so you do not touch tiny files.
- Default skipped directories already cover `.git`, virtualenvs, and `node_modules`. Add more with `--exclude-dir`.
- `bulk` skips top-level `.zip` by default (`--no-skip-zip` to include them). Nested zips inside other archives are still walked.
- Pass `--progress` (and `filerepack[progress]`) for long jobs.

## PDFs and scans

- Lossless: `pip install 'filerepack[pdf]'` then `filerepack repack file.pdf`.
- Scanned pages: `--lossy` (Ghostscript `/ebook`). Use `--pdf-profile prepress` for print-quality Ghostscript.
- `--jpeg-quality` also re-encodes images inside PDFs.

## Data and media extras

- Parquet: `filerepack[parquet]` or `[data]`; `--ultra` is zstd level 22.
- Cover art: `filerepack[media]`.
- Fonts: `filerepack[fonts]`.
- Raster verification: `filerepack[validation]`; video/audio verification needs ffmpeg and ffprobe.
- Scientific/checkpoint formats: use the [complete extra list](/getting-started/installation#optional-extras) and check the [supported profiles](/formats/scientific).

## Configuration

Put tool paths in `~/.config/filerepack/config.toml` or environment variables
(`FILEREPACK_7ZZ`, …). See [External tools](/tools/).

## Related docs

- [Basic usage](/getting-started/basic-usage)
- [Safety](/getting-started/safety)
- [Cookbook](/getting-started/cookbook)
