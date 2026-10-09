## 1. Early A6: ODF/EPUB implementation

- [x] 1.1 Add real ZIP package fixtures with mimetype order/storage/local-header extra-field checks.
- [x] 1.2 Enforce ODF/EPUB writer layout independently of backend compression choices and validate required manifest/member references.
- [x] 1.3 Preserve control-file bytes during nested walking and verify them again before publication.
- [x] 1.4 Test protected/malformed/unsupported ODF/EPUB inputs before extraction and invalid candidates before publication; update manual package support documentation.

## 2. Early A6 verification

- [x] 2.1 Verify package-level rules with deep/no-deep, dry-run, distinct-output, generic-ZIP identification and controlled backend/candidate faults.
- [x] 2.2 Run focused/full tests and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.3 Validate this change with `openspec validate update-container-format-policies --strict`.

## 3. Remaining container-policy work

- [ ] 3.1 Audit headers, checksums, signatures, compression constraints and metadata for broad ZIP aliases and implement validated format-specific policies.
- [ ] 3.2 Require proven write support for CAB/WIM and every advertised family.
- [ ] 3.3 Probe actual available writer commands; a backend E_NOTIMPL must never be called successful repacking.
- [x] 3.4 Test remaining protected/unsupported outcomes and update generated/manual support tables.
- [ ] 3.5 Verify ODF/EPUB with representative application-produced fixtures and application readers, beyond the current standards-shaped package tests.

## 4. Integration and rollout

- [x] 4.1 Reconcile the implemented canonical baseline before integrating/archiving the delta and record deployment status separately.

This is a partially implemented change. Early A6 covers supported ODF/EPUB package structure; broad aliases, capability registry, CAB/WIM and application-level evidence remain open.

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
