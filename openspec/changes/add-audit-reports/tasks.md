## 1. Implementation

- [x] 1.1 Define schema version 1 for run metadata, item/member events, terminal outcomes, and completion/abort summaries.
- [x] 1.2 Implement coordinator-owned bounded JSONL writing and JSON spooling/atomic finalization.
- [x] 1.3 Add report destination reservations/exclusions and path disclosure modes with error scrubbing.
- [x] 1.4 Wire `--report`, `--report-format`, and `--report-paths` through single-file and bulk CLI paths.
- [x] 1.5 Propagate sink failures into invocation exit status without losing already recorded file outcomes.
- [x] 1.6 Document report schemas, partial recovery, privacy policy, and examples independent of stdout JSON/CSV.

## 2. Verification and documentation

- [x] 2.1 Parse JSON and JSONL reports for all typed statuses, nested members, dry-run predictions, and serial/parallel jobs.
- [x] 2.2 Inject interruption, process termination/truncated line, disk-full, and final replacement failure; verify partial versus complete state and non-success exit.
- [x] 2.3 Check bounded report memory across many records and clean machine-readable stdout alongside stderr diagnostics.
- [x] 2.4 Verify occupied paths, source/target aliases, report discovery exclusion, and redaction of names and path-bearing errors.
- [x] 2.5 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.6 Validate this change with `openspec validate add-audit-reports --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
