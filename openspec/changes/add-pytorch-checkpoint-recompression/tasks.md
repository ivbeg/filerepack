> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Blocking feasibility gate

- [x] 1.1 Build trusted native Torch fixtures and identify complete real checkpoint origins.
- [ ] 1.2 Measure reader acceptance of ZIP methods per record class, ZIP64, alignment,
  mmap and Python/LibTorch versions; record rejected combinations explicitly.
- [ ] 1.3 Compare tensor bits, dtype/shape/strides, storage offsets/sharing and load
  results; benchmark real gains and read/memory/time costs with all attempts included.
- [x] 1.4 Record a go/no-go decision per profile; omit runtime compression registration
  if no compatible beneficial candidate is established.

## 2. Implement passing profiles only

- [x] 2.1 Add passive complete ZIP/layout classification and specific unsupported reasons.
- [x] 2.2 Preserve member bytes/order/required attributes and verified alignment through bounded candidates.
- [x] 2.3 Add exact decoded member/layout validation and shared acceptance/publication.
- [x] 2.4 Add explicit CLI/library compatibility policy with mmap-preserving defaults.
- [x] 2.5 Prevent generic standalone or nested ZIP routing from bypassing checkpoint policy.

## 3. Verify and document

- [x] 3.1 Exercise malicious pickle payloads without execution, duplicate/unknown records,
  CRC failures, offsets/ZIP64 damage, budgets, cancellation and destination failures.
- [x] 3.2 Verify native reader fixtures for every enabled profile and documented version floor.
- [x] 3.3 Document tested methods, mmap implications, excluded formats, actual gains,
  costs and any negative feasibility result without broad model-format claims.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
