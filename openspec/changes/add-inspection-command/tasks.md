## 1. Implementation

- [x] 1.1 Define a versioned inspection result/envelope and typed library API with estimate provenance and unknown protection state.
- [x] 1.2 Implement bounded format/protection/capability probes using shared policy and tool resolution.
- [x] 1.3 Add read-only destination planning and conflict checks using the central resolver.
- [x] 1.4 Add file/directory `inspect` CLI rendering and documented exit codes with bounded discovery.
- [x] 1.5 Document the distinction between an inspection plan and a measured dry-run candidate.

## 2. Verification and documentation

- [x] 2.1 Use spies and filesystem snapshots to prove inspection starts no encoder and creates no source/output/backup/scratch files.
- [x] 2.2 Cover known signed/encrypted packages, missing tools/extras, unsupported aliases, ambiguous headers, and pre-existing destination conflicts.
- [x] 2.3 Validate JSON parsing with diagnostics and interrupted directory discovery; verify bounded reader/probe behavior.
- [x] 2.4 Compare inspected routing/options against later repack planning without requiring estimated savings to equal measured results.
- [x] 2.5 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.6 Validate this change with `openspec validate add-inspection-command --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
