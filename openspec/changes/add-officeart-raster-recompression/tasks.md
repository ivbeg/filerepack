## 1. Codec qualification

- [x] 1.1 Define exact PNG/JPEG/UID/metadata comparison manifests and acquire pinned licensed host fixtures.
- [x] 1.2 Implement bounded PNG chunk/CRC/envelope parsing and exact-IDAT recompression.
- [x] 1.3 Verify sample/chunk preservation across palette, alpha, interlaced and high-depth PNG cases without color conversion.
- [x] 1.4 Qualify pinned optional jpegtran and a bounded independent coefficient-reader interface, including dependency/license/platform records.
- [x] 1.5 Implement JPEG coefficient/table/component/marker comparison and the explicit supported/unsupported image matrix.

## 2. Host and operation integration

- [x] 2.1 Extend parsed BLIP handling for qualified one/two-UID layouts and preserve all identity/display fields.
- [x] 2.2 Reuse audited DOC/XLS/PPT relocation and root-stream replacement without opaque signature scanning.
- [x] 2.3 Register raster intended-change verification and independently verify any composed metafile/raster candidate.
- [x] 2.4 Integrate optional-tool discovery, root budgets, cancellation and per-image skip/count diagnostics.
- [x] 2.5 Test archives, aliases, missing dependencies, dry-run, backup/output policies and physical savings thresholds.

## 3. Preservation and delivery

- [x] 3.1 Reject coefficient/sample/metadata/UID/pointer/unrelated-byte faults and malformed or over-budget encodings.
- [x] 3.2 Run pinned application comparisons and report original/compaction/selected sizes, time, memory and unsupported variants.
- [x] 3.3 Run relevant source/artifact/native/platform/static/docs checks and strict OpenSpec validation.
- [x] 3.4 Enable only the independently qualified PNG/JPEG subsets and document remaining renderer/platform limitations.

## Implementation evidence (2026-10-05)

Bounded runtime profiles and local preservation/application measurements:
[portfolio report](../../../dev/ole/PORTFOLIO.md),
[public API JSON](../../../dev/ole/qualification-portfolio.json).
Controls are labelled separately from originals. Office/Hancom and remote native
platform execution are unavailable and are not reported as passed.
Original-corpus expansion items remain unchecked; final source/artifact/static/docs
gates are checked only after their completed runs. No deployment/archive is claimed.
