# Change: Investigate lossless GGUF recompression

## Why

The survey found 24 `.gguf` files totaling 144,289,715,840 declared bytes
across four projects. No sample small enough for the bounded probe was
available, so the GGUF version, tensor layout, read compatibility, and any
same-format savings remain unmeasured. GGUF's scale merits a feasibility
study, but quantization or a generic outer archive would change the task.

## What Changes

- Add bounded, passive inspection of content-confirmed GGUF files and tensor
  offsets/alignment.
- Test same-format lossless candidates with complete real models and the
  intended native reader matrix, including mmap behavior where applicable.
- Enable only individually qualified profiles with exact tensor-byte
  preservation and real savings; otherwise leave GGUF inspection-only.
- Exclude quantization, requantization, tensor conversion, and external wrapping.

## Impact

- Affected specs: `gguf-recompression`.
- Affected code if feasible: GGUF parser/writer, format registry, verifier,
  CLI reporting, resource accounting, and tests.
- Sharded model sets require group-level evidence and SHALL NOT be treated as
  unrelated standalone files by a writer.

## Evidence

- [Survey and sample availability](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [GGUF format specification](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
