---
title: "Quick Start"
description: "Task-oriented first success paths for filerepack"
---
# Quick Start

Short task-oriented paths to first success. Not sure where to start? Pick your
role and goal in the [cookbook](/getting-started/cookbook). Installation details:
[Installation](/getting-started/installation). CLI flag list: [CLI reference](/commands/).

## Shrink a Word document in 30 seconds

```bash
pip install filerepack
filerepack doctor
filerepack repack document.docx
filerepack repack document.docx --dryrun
```

`repack` shows a progress bar on a TTY (`--no-progress` to hide it). Install
`filerepack[progress]` for a `rich` bar.

## Bulk-optimize a folder of photos

```bash
filerepack bulk ./photos --include-ext jpg,png,webp --progress
```

JPEG and PNG default to **lossless** tools. Opt into lossy codecs with
`--lossy`, `--jpeg-quality`, or `--png-quality`. Output that is not smaller
than the original is discarded unless `--allow-grow`.

## Shrink a scanned PDF

```bash
pip install 'filerepack[pdf]'
filerepack repack scan.pdf                 # lossless (qpdf; pikepdf walks image streams)
filerepack repack scan.pdf --lossy         # Ghostscript /ebook (150 dpi)
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
```

`--lossy` PDF uses Ghostscript `/ebook` so scanned pages actually shrink.
`--pdf-profile prepress` restores print-quality Ghostscript.

## Walk nested files in an archive

```bash
filerepack repack photos.tar.gz
filerepack repack archive.rar              # becomes .7z if `rar` is missing
```

`.tar.gz` and friends are unpacked so nested files can be optimized, then the
tarball is rewritten.

## Next steps

- [Usage scenarios by role](/getting-started/cookbook)
- [Format support matrix](/formats/)
- [When to use filerepack](/getting-started/when-to-use)
- [Safety](/getting-started/safety)
- [Troubleshooting](/getting-started/troubleshooting)
