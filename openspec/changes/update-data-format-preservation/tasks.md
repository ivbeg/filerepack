## 1. Early A6: Parquet implementation

- [x] 1.1 Add real Parquet custom-metadata, nullable/nested-type, decimal/timestamp, identifier and floating-point fixtures.
- [x] 1.2 Preserve and compare Parquet physical/logical schema, file/schema/field metadata, ordered values and identifiers before publication.
- [x] 1.3 Write and verify batches one row group at a time; declare and test PyArrow 19+ optional dependencies.
- [x] 1.4 Measure Parquet peak RSS, verify unsupported inputs/candidate faults preserve the source and document row-group/buffer limits.

## 2. Early A6 verification

- [x] 2.1 Compare real Parquet output through PyArrow and independent DuckDB reads; test deep value/schema/metadata fidelity, distinct outputs and dry-run.
- [x] 2.2 Run focused/full tests and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.3 Validate this change with `openspec validate update-data-format-preservation --strict`.

## 3. Remaining data preservation and C4 work

- [x] 3.1 Define and implement logical schema, metadata, value and identifier preservation/verification for each remaining data writer (ORC, Avro, Feather, Arrow, HDF5 and NetCDF).
- [x] 3.2 Retain Arrow IPC framing and expose explicit conversion separately.
- [x] 3.3 Implement documented SQLite offline eligibility, sidecar handling, snapshot output and concurrent-source checks.
- [ ] 3.4 Stream/batch remaining data paths and enforce the operation memory/resource policy, including large Parquet row groups and backend buffers.
- [ ] 3.5 Measure remaining writers' peak memory, verify optional backends/unsupported cases and update data documentation.
- [ ] 3.6 Use independent readers to compare remaining writers' values/schema/metadata and file-versus-stream form.
- [x] 3.7 Test SQLite WAL/writer snapshots and no in-place replacement of known live inputs.

## 4. Integration and rollout

- [x] 4.1 Reconcile the implemented canonical baseline before integrating/archiving the delta and record deployment status separately.

This is a partially implemented change. Early A6 covers Parquet only; it does not establish the other writer, SQLite or operation-wide resource requirements.

Local verification on 2026-10-03: **718 passed, 1 skipped** with DICOM dependencies;
**682 passed, 37 skipped** in the base environment. Early A6 adds **29 Parquet**
and **62 package** cases. All **91** passed on PyArrow 19.0.1; primary full checks
used PyArrow 21. Ruff, mypy, all **25** strict OpenSpec validations, documentation
and wheel builds passed. A fresh-process installed-wheel check on PyArrow 19
verified Parquet/ODF/EPUB preservation, dry-run and distinct outputs; the installed
CLI also recompressed real Parquet while retaining schema, values and metadata.
These are local macOS/Python 3.9 results, not deployment or broad platform evidence.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
