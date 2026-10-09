## 1. Feasibility and corpus

- [ ] 1.1 Obtain complete GGUF samples across supported versions, tensor types, and single/sharded layouts from multiple projects.
- [ ] 1.2 Record metadata, alignment, tensor payload composition, native-reader behavior, mmap behavior, and bounded same-format savings.
- [ ] 1.3 Document unchanged, unsupported, failed, and resource-limited cases; stop writer work if no profile passes the gate.

## 2. Inspection and validation

- [x] 2.1 Implement bounded content-based parsing of GGUF headers, metadata, tensor descriptors, and ranges.
- [x] 2.2 Validate versions, byte order, offsets, payload bounds, dimensions, and alignment without interpreting tensor payloads as executable content.
- [ ] 2.3 Build full-file fixtures and reader checks for supported single-file and sharded model profiles.

## 3. Qualified writer, if feasible

- [ ] 3.1 Implement only a profile proven to preserve tensor bytes and native-reader/mmap behavior.
- [ ] 3.2 Add full structural and reader verification before shared size acceptance.
- [ ] 3.3 Integrate resource limits, transactional publication, archive routing, and precise version reporting.
- [x] 3.4 Document unsupported versions, layouts, and the inspection-only outcome when no writer qualifies.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
