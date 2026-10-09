# Change: Complete lossless PDF Flate-image handling and traverse nested form resources

## Why

The completed parity proposal already promised Flate-decoded PNG-like PDF images, while the current walker handles only direct-page DCT/JPX streams. Completing that gap and walking nested forms can improve more existing PDFs, provided decoded image semantics, shared references, and whole-file protection remain intact.

## What Changes

- Complete eligible Flate/PNG-like image handling and recursively discover images in nested form resources.
- Deduplicate shared image objects and avoid resource cycles under root decode/depth/deadline budgets.
- Preserve decoded pixels, masks, color spaces, filter/decode parameters and PDF structure; report unsupported streams explicitly.

## Impact

- Priority: **P3**. Roadmap slice: **D — PDF stream expansion**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); N06.
- Affected capabilities: `nested-assets`.
- Affected code: `filerepack/pdf_streams.py:rebuild_pdf_images/_filter_name/_pack_stream_bytes`, `filerepack/repack.py:_maybe_walk_pdf_images/pack_pdf`, `filerepack/containers.py:pack_members`, `test/test_pdf.py`, `docs/docs/use-cases/pdfs.md`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [add-structural-output-validation](../add-structural-output-validation/proposal.md)
- [update-media-preservation-policy](../update-media-preservation-policy/proposal.md)
- [add-operation-resource-budgets](../add-operation-resource-budgets/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)

## Existing requirement baseline

- nested-assets: Lossless PDF Stream Walking — openspec/changes/add-chisel-parity/specs/nested-assets/spec.md; reviewed implementation lacks the promised Flate branch. This change adds detailed extension requirements, while add-structural-output-validation owns the single MODIFIED replacement of the existing requirement.

These complete replacement blocks use the named completed change as the reviewed baseline because canonical specs are currently absent. Reconcile that baseline through `update-quality-and-specification-gates` before archiving this change; do not copy future requirements into canonical specs prematurely.

## Validation

- Verify exact decoded image samples, masks, color/decode semantics, dimensions and bit depth for accepted Flate/DCT/JPX candidates.
- Render real before/after pages with a pinned renderer/settings and compare pixels for nested forms, transparency and color fixtures.
- Verify shared streams encode once, references remain intact and resource cycles/deep graphs stay within limits.
- Test protected/uncertain PDFs, missing pikepdf, lossy selection, unsupported filter chains and larger rebuilt candidates; originals stay intact when ineligible.
- Check per-object work accounting versus whole-file savings and rerun the original completed parity PDF scenarios under the updated protection contract.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
