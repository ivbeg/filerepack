## 1. Feasibility and corpus

- [ ] 1.1 Collect complete self-contained ONNX files and external-data bundles from multiple projects, recording versions and provenance.
- [ ] 1.2 Measure model protobuf and tensor storage composition, external references, reader acceptance, and bounded same-format savings.
- [ ] 1.3 Record unchanged, unsupported, failed, and resource-limited cases; keep any profile without a passing gate inspection-only.

## 2. Inspection and preservation

- [x] 2.1 Implement bounded, passive ONNX identification and distinguish inline tensor data from external-data references.
- [x] 2.2 Validate external locations, offsets, lengths, file existence, and containment without following unsafe paths or symlinks.
- [ ] 2.3 Compare graph structure, opsets, metadata, tensor descriptors, and all raw tensor bytes for candidates.
- [ ] 2.4 Establish ONNX checker/runtime reader coverage for self-contained models and complete external-data bundles.

## 3. Qualified writer, if feasible

- [ ] 3.1 Implement only independently qualified self-contained or whole-bundle profiles.
- [ ] 3.2 Verify structural validity and reader acceptance before shared size acceptance.
- [ ] 3.3 Integrate resource budgets, protected nested routing, and atomic transactional publication of complete bundles.
- [x] 3.4 Document supported ONNX variants, external-data constraints, and inspection-only outcomes.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
