# Change: Investigate and add preserving SPSS system-file recompression

## Why

The survey found 14 SAV files with 119,691,823 declared bytes across ten projects
and five creator groups. Two downloaded files had SPSS system-file headers; their
original-upload checksums were unavailable and only downloaded SHA-256/size were
recorded. No compression-mode classification, dictionary comparison or writer
gain was established. SAV is a reasonable next experiment; ZSAV was not observed
in the pilot and is included as a separately gated native-format profile.

## What Changes

- Add content-based system-file and compression-mode inspection before writer work.
- Preserve dictionary bytes and exact decoded case elements instead of dataframe round trips.
- Test SAV uncompressed/bytecode modes and existing ZSAV zlib-block recompression
  as independent profiles, enabling only beneficial compatible ones.
- Preserve `$FL2`/`$FL3` kind by default; do not convert SAV into ZSAV or PSPP POR.
- Gate unknown dictionary extensions, float representations and reader versions explicitly.

## Impact

- Affected specs: `spss-system-file-recompression`.
- Affected code: dedicated passive system-file parser/packer, dispatch/registry,
  independent read-only verification and trusted PSPP/SPSS integration fixtures.
- Uses shared transaction, output-validation, budget and release-evidence contracts.
- No required core pandas/pyreadstat dependency or automatic dataframe conversion.
- Status: approved for implementation by the user on 2026-10-04, with a blocking feasibility gate; extension frequency is not writer readiness.

## Evidence

- [Survey and source checksum caveats](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [GNU PSPP system file specification](https://www.gnu.org/software/pspp/pspp-dev/html_node/System-File-Format.html).
- [GNU PSPP compression data records](https://www.gnu.org/software/pspp/pspp-dev/html_node/Data-Record.html).
- [GNU PSPP SAVE compatibility](https://www.gnu.org/software/pspp/manual/html_node/SAVE.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
