## 1. Implementation

- [x] 1.1 Define typed root-input counters and bulk live-resource reservations with configurable documented defaults.
- [ ] 1.2 Propagate context into archives, streams, PSD, XML/PDF/covers, and validators.
- [ ] 1.3 Replace unbounded decoding with capped streaming or bounded verified adapters.
- [x] 1.4 Monitor actual extraction/encoder output and stop owned processes at limits/deadlines.
- [x] 1.5 Preflight normalized member/link containment and unsupported path collisions.
- [x] 1.6 Test nested bombs, malformed paths, stalled peeking, log growth, and parallel scratch reservations.

## 2. Verification and documentation

- [x] 2.1 Assert budget failures preserve sources and release process/scratch reservations.
- [x] 2.2 Measure memory/scratch behavior and document external monitoring bounds rather than claim unsupported hard guarantees.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate add-operation-resource-budgets --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
