# Change: Make media fidelity explicit and preserve all supported streams and frames

## Why

Default MP4 commands use CRF 18 even with lossy false, and automatic FFmpeg selection does not retain every track/attachment. Image aliases and metadata stripping need a presentation/fidelity contract.

## What Changes

- Add explicit remux/lossless/lossy video modes and migrate default behavior safely.
- Probe and explicitly map streams, chapters, dispositions, tags, and covers.
- Preserve image frame counts, bit depth, transparency, color/presentation, and cursor semantics.
- Propagate parent image/quality/metadata settings to embedded assets.
- **BREAKING**: Video will not be lossily re-encoded by default. Lossy video needs explicit permission. Metadata stripping will retain critical presentation information instead of indiscriminate removal.

## Impact

- Priority: **P1**. Roadmap slice: **B6**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R08, B6.
- Affected capabilities: `media-preservation`, `encoder-quality`.
- Affected code: `filerepack/repack.py:_encode_video/_pack_video/pack_jpg/pack_png`, `filerepack/codecs.py:_pack_ffmpeg_audio/_pack_magick/pack_svgz`, `filerepack/covers.py`, `filerepack/markup.py`, `filerepack/pdf_streams.py`, `filerepack/models.py`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [add-structural-output-validation](../add-structural-output-validation/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)

## Existing requirement baseline

- encoder-quality: Keep Metadata Flag — openspec/changes/add-chisel-parity/specs/encoder-quality/spec.md

These complete replacement blocks use the named completed change as the reviewed baseline because canonical specs are currently absent. Reconcile that baseline through `update-quality-and-specification-gates` before archiving this change; do not copy future requirements into canonical specs prematurely.

## Validation

- Use independent probes/decoders for stream inventories and frame/sample equality.
- Assert omitted critical content rejects publication and default video never selects lossy encoding implicitly.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
