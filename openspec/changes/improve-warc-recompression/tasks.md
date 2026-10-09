## 1. Qualification

- [x] 1.1 Compare zlib, libdeflate, Zopfli and Zstandard on bounded upstream,
  local and Common Crawl records; verify each compressed candidate decodes exactly.
- [x] 1.2 Construct a controlled mixed-member archive and measure the current
  whole-file decision against per-record source/zlib selection.
- [x] 1.3 Extend the pinned corpus with large, binary, metadata, request, revisit
  and poorly-compressible records; choose a production Zopfli cutoff from results.

## 2. Implementation

- [x] 2.1 Preserve or replay eligible source gzip members only when each complete
  member is one complete, trailer-verified WARC record.
- [x] 2.2 Select the smallest verified source/zlib-9 member independently for
  every record, preserving one record per output member and original tie winners.
- [x] 2.3 Pass the existing ultra option into the WARC writer and add bounded,
  optional Zopfli-15 trials with best-candidate retention and fallback reporting.
- [x] 2.4 Apply shared decoded-byte, memory, scratch, time, cancellation,
  candidate-validation and publication policies to all trials.
- [x] 2.5 Add diagnostics and regression coverage for candidate selection,
  malformed member boundaries, optional dependency paths and budget exhaustion.
- [x] 2.6 Update CLI/library documentation and record fixed-corpus time, memory,
  scratch, savings and optional-backend qualification.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
