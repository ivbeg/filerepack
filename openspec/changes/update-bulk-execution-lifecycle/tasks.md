## 1. Implementation

- [x] 1.1 Introduce incremental scanning and bound in-flight jobs.
- [x] 1.2 Exclude normalized output/backup trees and reserve all effective destinations centrally.
- [x] 1.3 Coordinate unique backups and conversion collision detection.
- [x] 1.4 Implement stop-submission, pending cancellation, running-task cancellation/drain, and interrupt handling.
- [x] 1.5 Report actual completed and cancelled outcomes and scan-completeness state.
- [x] 1.6 Test serial/parallel agreement, process spawn, large directories, fail-fast, and interrupts.

## 2. Verification and documentation

- [x] 2.1 Stress a large synthetic scan and assert the documented in-flight bound.
- [x] 2.2 Assert no unreported completed write and no target/backup conflict under competing workers.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate update-bulk-execution-lifecycle --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
