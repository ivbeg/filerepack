# Change: Investigate lossless Safetensors recompression

## Why

The survey found 347 `.safetensors` files with 1,616,952,877,759 declared
bytes across 32 projects. Only two headers were inspected; no same-format
compression candidate, real-file saving, or reader round-trip was measured.
The volume justifies a feasibility study, not a claim that tensor weights can
be usefully compressed while remaining Safetensors.

## What Changes

- Add bounded, passive inspection of content-confirmed Safetensors files.
- Measure whether any same-format, lossless rewrite can reduce real files and
  remain readable by independent Safetensors readers.
- Register a writer only for profiles that pass exact tensor-data preservation,
  native-reader, resource, and real-file benefit gates. Otherwise retain an
  inspection-only result with no advertised writer.
- Exclude quantization, dtype conversion, external wrappers, and model changes.

## Impact

- Affected specs: `safetensors-recompression`.
- Affected code if feasible: passive parser, candidate writer, format registry,
  verification, CLI reporting, and tests.
- Reuses structural-output validation, resource budgets, transactions, and
  archive-member preservation.

## Evidence

- [Survey and bounded header probes](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [Safetensors format and tensor offsets](https://huggingface.co/docs/safetensors/en/index).
- [Safetensors metadata parsing](https://huggingface.co/docs/safetensors/metadata_parsing).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
