# Change: Add preserving RDS and R workspace recompression

## Why

The 2026-10-04 survey found 16 RDS files (1,002,562,263 declared bytes) across
12 projects and three platforms, plus eight RData/RDA files across four projects.
On eight bounded R samples from five projects, gzip-9 saved 680,511 bytes and XZ-6
saved 1,201,468 bytes while preserving the decoded serialization stream exactly.
The 44.53% XZ result applies only to this successful subset; two larger decoded
streams exceeded the probe limit. Rscript was unavailable, so native reader
compatibility remains a release prerequisite, not an established result.

## What Changes

- Add content-identified `.rds`, `.rdata`, and `.rda` handling for a tested subset
  of XDR serialization versions 2 and 3 and their native compression wrappers.
- Change only the compression envelope; retain serialization and workspace bytes.
- Default to the source compression codec. Expose explicit codec selection through
  `--r-compression=preserve|gzip|bzip2|xz` and the library option `r_compression`.
- Validate complete framing and byte equality without executing serialized objects.
- Gate registration on trusted native R fixtures, real-file savings, and bounds.

## Impact

- Affected specs: `r-serialization-recompression`.
- Affected code: a dedicated R serialization module, `formats.py`, `dispatch.py`,
  CLI/library option validation, candidate verification, optional integration tests.
- Dependencies: shared acceptance/publication in `refactor-repack-transactions`,
  validation in `add-structural-output-validation`, and resource accounting in
  `add-operation-resource-budgets`. Implement the needed contracts without duplicating them.
- Existing stream handlers remain the fallback for explicitly wrapped generic files.
- Status: approved for implementation by the user on 2026-10-04; implementation and evidence are tracked in tasks.md and validation.md.

## Evidence

- [Survey and caveats](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [R readRDS documentation](https://stat.ethz.ch/R-manual/R-devel/library/base/html/readRDS.html).
- [R save documentation](https://stat.ethz.ch/R-manual/R-devel/library/base/html/save.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
