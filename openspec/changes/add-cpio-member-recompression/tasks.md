## 1. Implementation
- [x] 1.1 Add CPIO profile parsing, metadata inventory, safe extraction and a preserving writer.
- [x] 1.2 Route raw and bzip2-wrapped CPIO through bounded deep walking, keeping links and special files safe.
- [x] 1.3 Validate the rewritten CPIO and bzip2 candidate against source member metadata and authorized packer results.
- [x] 1.4 Cover CPIO profile variants, corrupt and unsafe input, nested members, limits and CLI/API behavior.
- [x] 1.5 Update user documentation and changelog.
- [x] 1.6 Run targeted tests, applicable quality checks and strict OpenSpec validation.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
