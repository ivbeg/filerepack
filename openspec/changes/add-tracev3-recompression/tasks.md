## 1. Implementation

- [x] 1.1 Implement a bounded `.tracev3` parser and LZ4 block recompressor in the isolated format worker.
- [x] 1.2 Register `.tracev3` detection, packing, validation, lossless comparison, compression-level forwarding, and optional dependency.
- [x] 1.3 Prevent in-place rewriting of files in the active macOS Unified Log store.
- [x] 1.4 Document supported files, dependency installation, compatibility limits, and failure behavior.
- [x] 1.5 Validate the OpenSpec change and implementation against the project checks.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
