## 1. HWP stream qualification

- [x] 1.1 Complete the prerequisite HWP host/protection profile and acquire pinned licensed multi-section/BinData fixtures.
- [x] 1.2 Define per-version stream/framing/compression-flag/reference matrices from the Hancom specification.
- [x] 1.3 Implement bounded raw-DEFLATE decode/encode for already-compressed DocInfo and BodyText sections.
- [x] 1.4 Qualify DocInfo/BinData ID, link/embedding and compression-policy resolution before enabling compressed binary streams.
- [x] 1.5 Qualify optional stronger raw-DEFLATE encoding with pinned version/license/platform evidence.

## 2. Preservation and execution

- [x] 2.1 Implement independent exact-decoded/unchanged-encoded/metadata/identity comparison and register a separate verifier.
- [x] 2.2 Qualify bounded native replacements for exact selected nested/root stream paths.
- [x] 2.3 Integrate ole_recompress, cumulative root budgets, cancellation/cleanup and compaction-baseline selection.
- [x] 2.4 Reject malformed/trailing/concatenated/wrong-wrapper streams, altered bytes/flags/IDs, missing sections and metadata faults.
- [x] 2.5 Exercise aliases/archives where registered, optional tools, dry-run, output/backup/threshold policies and verbose/JSON reporting.

## 3. Delivery evidence

- [x] 3.1 Compare real complete manifests and available application output, explicitly recording Hancom/platform limitations.
- [x] 3.2 Measure original/compaction/recompressed sizes, stream counts, time and memory separately from controls.
- [x] 3.3 Run relevant source/artifact/native/platform/static/docs checks and strict OpenSpec validation before staged activation.

## Implementation evidence (2026-10-05)

Bounded runtime profiles and local preservation/application measurements:
[portfolio report](../../../dev/ole/PORTFOLIO.md),
[public API JSON](../../../dev/ole/qualification-portfolio.json).
Controls are labelled separately from originals. Office/Hancom and remote native
platform execution are unavailable and are not reported as passed.
Original-corpus expansion items remain unchecked; final source/artifact/static/docs
gates are checked only after their completed runs. No deployment/archive is claimed.
Item 1.5 is qualified through a dedicated RFC1950-to-RFC1951 adapter for pinned
Zopfli0.4.3/15 at ≤1 MiB, retaining HWP suffixes and original/raw-zlib9 candidates.
Header/dictionary/checksum/collision/termination, cutoff and cumulative-budget
faults are covered in `test/test_ole_hwp_codecs.py`; ultra does not add HWP trials.
