## 1. Implementation

- [ ] 1.1 Build a preservation corpus covering every advertised writer or label support unavailable/experimental.
- [x] 1.2 Replace early-return integration passes with explicit skip or failure according to provisioning.
- [x] 1.3 Add extras and macOS/Windows process/filesystem lanes; retain Python 3.9–3.13 and define future-version policy.
- [x] 1.4 Add fault/property tests and staged coverage ratchets focused on shared transaction/validator code.
- [x] 1.5 Record fixed-corpus timing, memory, scratch, acceptance, and final-vs-inner savings benchmarks.
- [x] 1.6 Audit existing completed/archived specs, populate verified canonical requirements, record gaps, and rebase overlapping deltas.
- [ ] 1.7 Update openspec/project.md and contributor/docs guidance; confirm deployment before archiving old changes.

## 2. Verification and documentation

- [x] 2.1 Run strict OpenSpec validation and reject duplicate/conflicting requirement ownership.
- [x] 2.2 Provision real optional integrations and verify artifact/platform failures cannot be masked by checkout imports or early returns.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate update-quality-and-specification-gates --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
