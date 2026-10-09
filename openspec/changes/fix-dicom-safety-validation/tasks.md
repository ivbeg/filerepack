## 1. Implementation

- [x] 1.1 Add trailing and nested signature fixtures in correct tag order.
- [x] 1.2 Scan complete datasets with bounded nesting/elements and validated value lengths.
- [x] 1.3 Retain transfer-syntax eligibility and reject truncated pixel payloads.
- [x] 1.4 Validate candidate transfer syntax, frames, decoded pixels, and preservation-relevant attributes.
- [x] 1.5 Run real available GDCM/DCMTK tests, explicitly skip missing backends, and document verification requirements.

## 2. Verification and documentation

- [x] 2.1 Assert encoders are never invoked for protected/malformed/limit-exceeded inputs.
- [x] 2.2 Assert unsupported or invalid candidates preserve original bytes.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate fix-dicom-safety-validation --strict`.

## 3. Integration and rollout

- [x] 3.1 Reconcile the implemented canonical baseline through `update-quality-and-specification-gates` before integrating/archiving the delta; record deployment status separately.

Local verification on 2026-10-03: **627 passed, 1 skipped** with DICOM dependencies, including **66 new DICOM safety cases**. The base environment without those dependencies passed **591 tests, 37 skipped**, with explicit optional-integration skips. A separate Python 3.11/pydicom 3.0.2 environment passed all **93 DICOM tests**; Python 3.9 used pydicom 2.4.4. Real GDCM 3.2.7 and DCMTK 3.7.0 encoders exercised unsigned synthetic monochrome images, signed pixel values and multiframe data, eligible transfer syntaxes and invalid candidates; DCMTK's unsupported RLE input was verified to retain source bytes. Ruff, mypy, all 25 strict OpenSpec validations, documentation and wheel builds passed. The wheel includes the verifier/extra metadata and passed a fresh-process real-encoder preservation smoke check. Clinical-corpus, cryptographic signature, color-image and broader platform evidence remain separate quality-gates work.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
