> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Establish full-store evidence

- [ ] 1.1 Obtain complete local stores from multiple origins; record versions, complete key
  manifests, source checksums and actual stored bytes rather than partial API totals.
- [ ] 1.2 Benchmark same-family codec levels and explicit compatible upgrades; report
  gains, unchanged stores, read cost, time and peak scratch/memory.
- [x] 1.3 Prepare group/array, C/F order, endian, float bits, structured fixed-size dtype,
  missing/edge chunks, attributes and consolidated/unconsolidated fixtures.

## 2. Implement the directory transaction contract

- [x] 2.1 Add typed store requests/outcomes and exclusive destination-local staging ownership.
- [x] 2.2 Implement source-root disjointness, key/link/collision checks and generation manifests.
- [x] 2.3 Implement and test atomic no-replace publication per supported platform/filesystem;
  refuse publication when unavailable.
- [x] 2.4 Add cumulative store/chunk/memory/scratch budgets, cancellation and cleanup.

## 3. Implement Zarr v2 recompression

- [x] 3.1 Add metadata/content detection and allowlisted dtype/filter/codec profile inspection.
- [x] 3.2 Add bounded complete-array candidate generation with exact decompressed chunk comparison.
- [x] 3.3 Preserve untouched metadata/auxiliaries and synchronize existing consolidated metadata.
- [x] 3.4 Add `repack-store`, required distinct output, and validated codec-policy options.

## 4. Verify and document

- [x] 4.1 Exercise stale metadata, one corrupt chunk, unknown codecs, pickle/object dtype,
  symlinks, path escapes, case collisions, source changes and exhausted budgets.
- [x] 4.2 Exercise cancellation, no-benefit cleanup and destination-creation races without
  exposing partial output or replacing an existing directory.
- [ ] 4.3 Check complete stores with ordinary/consolidated native readers and record the
  tested codec/platform matrix, metadata guarantees and exclusions.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
