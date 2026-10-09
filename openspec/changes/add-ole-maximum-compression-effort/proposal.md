# Change: Add bounded maximum OLE compression effort through ultra

## Why

The initial metafile codec uses zlib9 and qualified Zopfli with 15 iterations for
payloads up to 1 MiB. Some already-supported payloads may benefit from more effort,
but a larger trial must not exceed root limits, discard a better earlier result
or implicitly enable new content transformations.

## What Changes

- Use existing ultra / --ultra to select a versioned stronger OLE effort mapping
  when an applicable content mode is explicitly enabled.
- Preserve the current default mapping; maximum version 1 adds a Zopfli 50-
  iteration trial up to 2 MiB within existing hard per-payload/root limits.
- Retain original, zlib9 and the existing 15-iteration candidates wherever
  applicable, then choose the smallest completely verified result.
- Publish effective mapping/version, dependency availability and measured
  time/memory/savings rather than claim a compression ratio.

## Impact

- Affected capability: officeart-recompression; additive effort requirements.
- Affected code: codec effort resolution, worker options/budgets, diagnostics,
  benchmark tooling and CLI/library/docs integration.
- Priority: P3, after coverage/raster/nested work.
- Prerequisite: initial OfficeArt. PNG uses this mapping only after its codec is
  delivered; JPEG does not gain an unrelated quality setting. Existing PPT wrapper
  and future HWP codecs need their own qualified mappings before adopting it.
- Coordinates with [named optimization profiles](../add-optimization-profiles/proposal.md)
  without duplicating selectors or depending on unimplemented profile resolution.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

Benchmark both mappings on the same pinned real corpus with fixed backend versions.
Report final savings beyond compaction/default, accepted rate, wall time, memory,
timeouts and dependency skips. Verify that ultra never enables a transformation
or loss, never drops a better candidate and cannot reset resource limits.
