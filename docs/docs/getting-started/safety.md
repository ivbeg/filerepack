---
title: "Safety"
description: "In-place rewrites, backups, size limits, and files that are never touched"
---
# Safety

filerepack is designed to leave the source file untouched until a candidate is
verified and actually smaller.

## Write path

Rewrites go to a temp file, are verified, then `os.replace`d onto the original.
A missing `7zz`/`7z` leaves the source archive untouched. Packers must not
unlink user files before a successful rewrite.

## Discard if not smaller

Output that is not smaller than the original is discarded unless `--allow-grow`.
`--min-savings PCT` keeps the result only if savings are at least that percent.

## Backups and output directory

```bash
filerepack repack contract.docx --backup
filerepack repack contract.docx --backup-dir ./backups
filerepack repack contract.docx --output-dir ./out
```

`--dryrun` measures savings and does not modify files.

## Archive extract limits

`--max-extract-size` skips archive extract if uncompressed size exceeds the
limit (`0` disables). The default is 8 GB, and also 100× the archive size, so
a tiny zip bomb is not fully expanded.

## Files that stay untouched

These are never extracted and rewritten:

- Signed installers: `deb`, `rpm`, `pkg`, `dmg`
- Disc/library archives 7-Zip cannot create: `iso`, `cpio`, `ar` / `a` / `lib`
- OpenType `.otf` fonts (ZIP ODF templates with that extension are packed)
- Encrypted or digitally signed PDFs skip pikepdf stream replacement; lossless qpdf may still run
- DICOM instances that are signed, non-image, or already compressed

## Related docs

- [Troubleshooting](/getting-started/troubleshooting)
- [Formats](/formats/)
- [CLI shared options](/commands/shared-options)
