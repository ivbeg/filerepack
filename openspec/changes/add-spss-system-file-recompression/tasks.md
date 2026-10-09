> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Blocking feasibility gate

- [ ] 1.1 Inspect complete SAV sources, compression modes and dictionary records;
  acquire independent-origin real ZSAV files with recorded provenance.
- [x] 1.2 Measure same-kind candidate gains and native-reader requirements per profile;
  record a go/no-go decision including all unchanged and unsupported attempts.
- [x] 1.3 Prepare endian, raw/bytecode/zlib, IEEE float bits, system/user missing,
  labels, codepages, long strings, weights and multiple-response fixtures.

## 2. Implement passing profiles only

- [x] 2.1 Implement complete bounded passive header/dictionary/case framing validation.
- [x] 2.2 Add exact case-element SAV bytecode candidates without dictionary conversion.
- [ ] 2.3 Add independently gated existing-ZSAV block envelope recompression and offset rebuild.
- [x] 2.4 Verify dictionary bytes, decoded case bytes and framing before shared acceptance/publication.
- [x] 2.5 Register only verified content profiles and expose precise unsupported reasons.

## 3. Verify and document

- [x] 3.1 Exercise unknown records, corrupt counts/offsets/zlib blocks, float normalization,
  budgets, source changes, cancellation and destination failures.
- [ ] 3.2 Obtain trusted native-reader dictionary/case checks per advertised profile and
  document actual reader lineages, version coverage and compatibility limitations.
- [x] 3.3 Document no-conversion policy, dictionary guarantees, measured gain/cost and
  any negative feasibility result without claiming unseen ZSAV support.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
