# Change: Inspect complete DICOM datasets and verify lossless output

## Why

Synthetic datasets with signatures after Pixel Data or inside sequence items were accepted as packable. Current output verification checks only DICM bytes.

## What Changes

- Scan the full dataset and all nested sequences for signature elements without decoding large pixels during eligibility inspection.
- Fail closed on malformed lengths, unsupported syntax, truncation, and parser limits.
- Verify JPEG-LS output structure, transfer syntax, frames, attributes, and decoded pixels.

## Impact

- Priority: **P0**. Roadmap slice: **A5**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R05, A5.
- Affected capabilities: `dicom`.
- Affected code: `filerepack/dicom.py`, `filerepack/codecs.py:pack_dcm`, `filerepack/utils.py:verify_output`, `test/dicom_fixtures.py`, `test/test_dicom.py`.
- Status: implemented and verified locally on 2026-10-03; canonical integration and deployment remain open.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Existing requirement baseline

- dicom: Unsafe DICOM Instances Are Skipped; DICOM Output Verification — openspec/changes/add-dicom-support/specs/dicom/spec.md

These complete replacement blocks use the named completed change as the reviewed baseline because canonical specs are currently absent. Reconcile that baseline through `update-quality-and-specification-gates` before archiving this change; do not copy future requirements into canonical specs prematurely.

## Validation

- Assert encoders are never invoked for protected/malformed/limit-exceeded inputs.
- Assert unsupported or invalid candidates preserve original bytes.

## Approval and rollout

The user authorized roadmap implementation on 2026-10-02 and continued it on 2026-10-03. Implementation and local verification tasks are complete. Existing aliases, packer entry points and unconditional lossless encoding remain. Processing now requires `filerepack[dicom]`; direct DICOM `verify_output` calls require an unchanged original as `source_path`. Missing verification support prevents encoding/publication, and the migration is documented. Canonical integration, deployment and archival remain the separate unchecked rollout task.

Local verification: 627 tests passed, 1 skipped with DICOM dependencies, including 66 new safety cases. Without those dependencies, 591 passed and 37 explicitly skipped. The Python 3.11/pydicom 3 branch passed all 93 DICOM tests. Both installed GDCM/DCMTK encoders were exercised. Ruff, mypy, strict OpenSpec validation, documentation and wheel builds, and a real-encoder wheel smoke check passed.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
