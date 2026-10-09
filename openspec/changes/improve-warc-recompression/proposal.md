# Change: Improve WARC gzip recompression by record

## Why

WARC output currently re-encodes every record with zlib level 9 and decides
whether to publish one whole-file candidate. This can replace an already-smaller
source member just because another record benefits from recompression. The
existing `--ultra` option also does not reach the WARC encoder.

## What Changes

- Compare the valid source member and a zlib-9 candidate independently for each
  record, then emit the smallest verified member while preserving one record per
  member and exact decoded bytes.
- Route the existing `ultra` option to a bounded, optional Zopfli-15 trial for
  eligible records; retain the best earlier candidate when that trial is missing,
  interrupted, ineligible or larger.
- Keep the current WARC framing and archive-level minimum-savings, transaction,
  index, source-snapshot and resource-limit policies.
- Record codec qualification and benchmark the output size, time, memory and
  scratch use on pinned mixed-size WARC inputs.

## Impact

- Affected capability: `warc-recompression`.
- Affected code: WARC member reader/writer, dispatch option mapping, bounded
  format budgets, diagnostics and WARC documentation.
- Priority: P1 for per-record member selection; the optional ultra trial remains
  best-effort and must not become a required runtime dependency.
- Dependencies: [initial WARC recompression](../add-warc-recompression/proposal.md),
  [optimization profiles](../add-optimization-profiles/proposal.md), and
  [operation resource budgets](../add-operation-resource-budgets/proposal.md).
- Research and size evidence: [WARC recompression improvements](../../../dev/warc/research-2026-10-05.md).
- Status: proposed; implementation tasks are unchecked.

## Validation

- Verify all selected gzip members independently and compare their complete
  decoded record bytes, order, boundaries and SHA-256 with the source.
- Cover source members with one record, split records, multiple records,
  corrupt trailers, truncated members, equal-size candidates and mixed codec
  winners. Preserve one output member per record.
- Exercise `ultra` through direct, library, bulk and nested dispatch; test
  optional Zopfli absence, size cutoffs, interruption and larger candidates.
- Re-run the fixed measurement corpus and report the final savings beyond zlib 9,
  elapsed time, peak memory, scratch use and candidate acceptance.
- Confirm archive-wide savings thresholds, cancellation, transaction and index
  protections remain in force.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
