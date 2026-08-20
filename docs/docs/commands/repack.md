---
title: "repack"
description: "Recompress a single file, walking nested members when it is an archive"
---
# repack

```bash
filerepack repack <file> [OPTIONS]
```

Rewrites one file in place (unless `--output-dir` or `--dryrun`). Archives and
Office documents are walked with `--deep` (default). Progress is on for a TTY;
pass `--no-progress` to hide it.

Shared flags: [Shared CLI options](/commands/shared-options).

## Examples

```bash
filerepack repack contract.docx
filerepack repack contract.docx --progress
filerepack repack contract.docx --dryrun --stats
filerepack repack photos.tar.gz
filerepack repack notes.json
filerepack repack photo.jpg --keep-meta
filerepack repack album.mp3
filerepack repack data.sqlite
filerepack repack data.parquet --ultra
filerepack repack scan.pdf --lossy
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
filerepack repack archive.rar          # becomes .7z if `rar` is missing
```

## Related docs

- [`bulk`](/commands/bulk) for directories
- [Formats](/formats/)
- [Safety](/getting-started/safety)
