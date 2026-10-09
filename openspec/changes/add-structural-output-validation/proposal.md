# Change: Require structural validators and protect PDFs before every rewrite path

## Why

Truncated JPEG/PDF and arbitrary MP4/Arrow content pass current validators. The signed/encrypted PDF gate protects only the pikepdf step and allows later rewrites.

## What Changes

- Separate signature recognition, structural validation, and preservation validation guarantees.
- Require a declared structural validator for every publishable writer and fail closed when it is unavailable.
- Compare decoded lossless payloads and format-specific preservation contracts.
- Apply PDF protection gates before qpdf/pikepdf/Ghostscript and choose the smallest valid candidate.
- **BREAKING**: Magic-valid candidates without structural validation will no longer be published. Signed/encrypted PDFs will be preserved by default across qpdf, pikepdf, and Ghostscript, not only stream replacement.

## Impact

- Priority: **P1**. Roadmap slice: **B2**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R09, B2.
- Affected capabilities: `output-validation`, `pdf`, `nested-assets`.
- Affected code: `filerepack/utils.py:verify_output/_verify_special`, `filerepack/repack.py:pack_pdf/_qpdf_linearize/_commit_output`, `filerepack/pdf_streams.py`, `filerepack/codecs.py`.
- Status: partially implemented locally. Shared structural rejection, stream/raster/IPC comparisons and whole-file PDF protection/selection are implemented; wider data/media preservation and rollout remain open. See [implementation evidence](evidence.md).

## Dependencies

- [refactor-repack-transactions](../refactor-repack-transactions/proposal.md)
- [fix-archive-member-preservation](../fix-archive-member-preservation/proposal.md)
- [fix-compressed-tar-roundtrip](../fix-compressed-tar-roundtrip/proposal.md)
- [fix-dicom-safety-validation](../fix-dicom-safety-validation/proposal.md)

## Existing requirement baseline

- nested-assets: Lossless PDF Stream Walking — openspec/changes/add-chisel-parity/specs/nested-assets/spec.md

These complete replacement blocks use the named completed change as the reviewed baseline because canonical specs are currently absent. Reconcile that baseline through `update-quality-and-specification-gates` before archiving this change; do not copy future requirements into canonical specs prematurely.

## Validation

- Every accepted corpus candidate must parse/decode and satisfy its declared preservation contract.
- Assert protected PDFs never invoke rewriting tools; missing verification must produce a visible nonpublication outcome.

## Approval and rollout

Implementation follows the user's 2026-10-02 instruction to begin applying the reviewed roadmap and subsequent continuation requests. Only verified local work is checked in [tasks.md](tasks.md); deployment and archival are not asserted. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
