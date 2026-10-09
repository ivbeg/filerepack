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

`--output-dir` preserves the source and publishes unchanged copies for ordinary
supported inputs when no improvement is accepted. Existing different destinations require explicit
`--overwrite`; required backups are protected independently. JSON summaries
include `output_file`, the actual destination after any accepted conversion.
Scientific, NIB, CAR and WARC handlers create distinct outputs only for accepted
candidates; unsupported, failed or intentionally skipped work does not create a
fallback copy. SQLite outputs use a consistent snapshot, including committed WAL
pages, even when compaction provides no size reduction.

Shared flags: [Shared CLI options](/commands/shared-options).
Most dry-runs measure candidates in scratch space. Scientific, NIB and CAR
dry-runs inspect without encoding and report unchanged sizes.

## Completion status

Human output explicitly labels successful results with `[SUCCESS]`, including
an unchanged file when no smaller candidate is found. A dry-run includes
`[DRYRUN]` and describes predicted changes; it does not publish them.
Intentional filtering uses `[SKIPPED]`, failures and unavailable support use
`[ERROR]`, and user interruptions use `[CANCELLED]`.

For example, a verified XLS candidate with no size reduction reports:

```text
[SUCCESS] [DRYRUN] File workbook.xls would remain unchanged ... (0.00%)
  Info: No size reduction: verified candidate ...
  Record recompression skipped: OfficeArt: host macros are not qualified
```

The skipped optional step does not turn the successful container check into an
error. Failures include their reason at normal verbosity and remain visible on
stderr with `--quiet`; quiet mode suppresses success messages. JSON/CSV keep
their existing structured status fields and contain no human status labels.
Exit codes remain 0 for successful or intentionally skipped work, 1 for errors
or unavailable support, and 130 for interruption.

## Examples

```bash
filerepack repack contract.docx
filerepack repack contract.docx --progress
filerepack repack contract.docx --dryrun --stats
filerepack repack photos.tar.gz
filerepack repack notes.json
filerepack repack notes.json --output-dir ./out
filerepack repack notes.json --output-dir ./out --overwrite
filerepack repack photo.jpg --keep-meta
filerepack repack album.mp3
filerepack repack data.sqlite --sqlite-offline  # close database users first
filerepack repack data.sqlite --output-dir ./snapshots
filerepack repack data.parquet --ultra
filerepack repack scan.pdf --pdf-linearize
filerepack repack scan.pdf --lossy
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
filerepack repack archive.rar          # becomes .7z if `rar` is missing
```

## Related docs

- [`bulk`](/commands/bulk) for directories
- [Formats](/formats/)
- [Safety](/getting-started/safety)
