## 1. Implementation

- [x] 1.1 Add real multi-track/subtitle/attachment/chapter and image animation/bit-depth/CUR fixtures.
- [x] 1.2 Implement structural media probing, explicit mapping, and container compatibility checks.
- [x] 1.3 Add mode selection/validation and migration help for lossy and wmv-lossless flags.
- [x] 1.4 Compare decoded frames/samples and critical metadata for lossless candidates.
- [x] 1.5 Preserve all requested tags/covers and propagate effective nested options.
- [x] 1.6 Test missing/incompatible tools and unsupported stream/frame formats; update feature and safety docs.

## 2. Verification and documentation

- [x] 2.1 Use independent probes/decoders for stream inventories and frame/sample equality.
- [x] 2.2 Assert omitted critical content rejects publication and default video never selects lossy encoding implicitly.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate update-media-preservation-policy --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
