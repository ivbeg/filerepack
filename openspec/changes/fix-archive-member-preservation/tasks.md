## 1. Implementation

- [x] 1.1 Add failing root-dotfile, hidden-directory, empty-directory, Unicode, and option-like-name fixtures.
- [x] 1.2 Replace bare-star member selection with complete tool-specific enumeration.
- [x] 1.3 Build source/intended/candidate manifests and preserve supported entry types and metadata.
- [x] 1.4 Reject unsupported duplicate or case-colliding identities explicitly.
- [x] 1.5 Verify missing/extra members, writer failure, dry-run, and cleanup; update archive documentation.

## 2. Verification and documentation

- [x] 2.1 Run real available ZIP/7z/tar and Info-ZIP round-trips; missing tools must skip explicitly.
- [x] 2.2 Assert rejected candidates leave original bytes unchanged.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate fix-archive-member-preservation --strict`.

## 3. Integration and rollout

- [x] 3.1 Reconcile the canonical baseline and confirm deployment before archiving; local implementation is not deployment evidence.

Local verification: test/test_archive_preservation.py includes real ZIP/Info-ZIP/7z/tar payload and metadata checks, ambiguous identities, authorized and unauthorized changes, rejected writers, dry-run, failure cleanup and wrapper cases. Full-suite, Ruff, mypy, docs and wheel checks are recorded in openspec/ROADMAP.md.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
