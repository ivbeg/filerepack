> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Establish compatibility evidence

- [x] 1.1 Reproduce the eight successful probes with trusted `readRDS`/`load` checks;
  include the two bounded-out inputs in coverage and savings denominators.
- [x] 1.2 Add v2/v3 RDS and workspace fixtures, gzip/bzip2/XZ/uncompressed sources,
  attributes, references, encodings, integer/logical/raw/list values and float bits.
- [x] 1.3 Record R versions, wrapper reader floors, corpus provenance and benchmark limits.

## 2. Implement preserving envelopes

- [x] 2.1 Implement bounded content detection and passive supported-grammar validation.
- [x] 2.2 Implement streaming candidate encoders, envelope metadata retention, and exact
  decoded comparison; reject unsupported records, bad checksums and trailing data.
- [x] 2.3 Route candidates through shared acceptance and destination-local publication.
- [x] 2.4 Register verified aliases and validate CLI/library `r_compression` consistently.

## 3. Verify and document

- [x] 3.1 Exercise malformed lengths/references, decompression limits, cancellation,
  missing tools, changed source, output collisions and rejected larger candidates.
- [ ] 3.2 Verify trusted fixtures in native R across the declared reader matrix and
  demonstrate smaller real files without object reserialization.
- [x] 3.3 Document supported grammar, metadata restrictions, default/explicit codec
  policy, measured gain, resource cost, and unsupported variants.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
