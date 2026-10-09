## 1. Implementation

- [x] 1.1 Add invalid-option overwrite, conversion-collision, and direct standalone outfile regressions.
- [x] 1.2 Validate options before writes and unify CLI/library validation.
- [x] 1.3 Implement distinct-output staging and unchanged-copy semantics.
- [x] 1.4 Normalize identities and reserve source/output/conversion/backup paths; refuse collisions by default.
- [x] 1.5 Abort destructive work on requested-backup failure and test competing reservations.
- [x] 1.6 Test dry-run and same-path aliases; update CLI/library docs.

## 2. Verification and documentation

- [x] 2.1 Verify hashes on invalid options, collisions, and backup failure.
- [x] 2.2 Exercise JSON/stream/archive outfile directly and through the CLI.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate fix-output-destination-safety --strict`.

## 3. Integration and rollout

- [x] 3.1 Reconcile the implemented canonical baseline through `update-quality-and-specification-gates` before integrating/archiving the delta; record deployment status separately.

Local verification on 2026-10-03: **561 passed, 1 skipped**, including **116 new output-safety cases**. Ruff, mypy, all 25 strict OpenSpec validations, documentation and wheel builds passed. A fresh process imported the wheel and verified distinct-output source preservation and collision refusal. These checks ran on macOS/Python 3.9; broader platform and installed-extras coverage remains separate roadmap work. Controlled video/RAR encoder fixtures verify destination handling, not real codec fidelity.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
