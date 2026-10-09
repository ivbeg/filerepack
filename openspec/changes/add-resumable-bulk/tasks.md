## 1. Implementation

- [x] 1.1 Define manifest schema, deterministic execution fingerprint, and streaming source/output content identity checks.
- [x] 1.2 Implement coordinator-owned locked atomic checkpoint updates and protected path reservations/exclusions.
- [x] 1.3 Record before/after source and destination state for in-place and distinct-output publication.
- [x] 1.4 Implement `--manifest`/`--resume`, compatible-state validation, safe completion reuse, and re-planning on invalidation.
- [x] 1.5 Integrate resumed records with audit/outcome accounting without double-counting historical savings.
- [x] 1.6 Document unsupported schema/corruption handling, privacy, crash windows, and the dry-run manifest policy.

## 2. Verification and documentation

- [x] 2.1 Interrupt a batch and resume; verify completed matching inputs do not re-encode while incomplete ones are processed.
- [x] 2.2 Change bytes without changing size/time, effective options, tool version/path, policy version, and output destination; verify each invalidates reuse.
- [x] 2.3 Test in-place post-publication identity and distinct-output deletion/modification; prevent stale success or unrelated overwrite.
- [x] 2.4 Inject checkpoint replacement failure/crash and simultaneous writers; preserve a valid prior manifest and safe normal collision behavior.
- [x] 2.5 Cover malformed/unsupported manifests, aliases to inputs/outputs/reports, dry-run read-only behavior, and reconciled resumed accounting.
- [x] 2.6 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.7 Validate this change with `openspec validate add-resumable-bulk --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
