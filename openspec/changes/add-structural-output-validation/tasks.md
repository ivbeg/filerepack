## 1. Implementation

- [x] 1.1 Add header-valid corrupt/truncated and malformed fixtures across every declared validator and reject unknown kinds.
- [x] 1.2a Implement structural adapters and require every publishable writer to declare its validator; fail closed on missing parsers/decoders.
- [ ] 1.2b Complete preservation adapters for all remaining data/media/image writer contracts, including required metadata and encoded sample-depth qualification.
- [x] 1.3a Compare decoded stream bytes, supported raster frames/pixels, Arrow/Feather/ORC schema metadata and ordered values, and lossless PDF object/decoded-stream graphs; retain existing archive/Parquet/DICOM/native proofs.
- [ ] 1.3b Finish Avro/HDF5/NetCDF/font/SQLite and remaining image/audio/video preservation contracts and their real positive/adversarial corpus. Structural validation alone does not complete these guarantees.
- [x] 1.4 Gate all PDF paths on signature/encryption/protection detection with fail-closed handling, including direct stream walking and AI wrappers.
- [x] 1.5 Retain PDF alternatives through validation and size selection; expose explicit linearization through CLI/library/bulk/worker options.
- [x] 1.6 Verify unavailable parsers, subprocess failure/timeout/output bounds and real protected/unprotected PDFs; update safety docs.

## 2. Verification and documentation

- [ ] 2.1 Establish every advertised lossless format's complete preservation contract across the positive/adversarial corpus; remaining contracts are listed above.
- [x] 2.2 Assert protected PDFs never invoke rewriting tools; missing verification logs a visible nonpublication reason.
- [x] 2.3 Run focused/full tests, lint/type checks, source/wheel installation checks and documentation builds against the final local slice; record actual evidence and limits.
- [x] 2.4a Validate this change and all active changes with strict OpenSpec checks.
- [x] 2.4b Reconcile the canonical baseline before archive and record deployment separately; no local test result establishes deployment.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
