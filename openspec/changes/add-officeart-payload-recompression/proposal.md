# Change: Recompress OfficeArt payloads through DOC/XLS/PPT adapters

## Why

Container compaction cannot improve compressed pictures in a live OLE stream.
OfficeArt supplies a shared representation of EMF/WMF in legacy Word, Excel and
PowerPoint, but each host owns its placement and references. Replacing arbitrary
CFB stream bytes or searching for image signatures cannot establish preservation.

## What Changes

- Extend the existing opt-in `ole_recompress` operation with a shared OfficeArt
  codec and explicitly qualified DOC/DOT, XLS/XLT/XLA and PPT/POT/PPS adapters.
  The first runtime stage recompresses RFC1950-wrapped EMF/WMF. Preserve every
  decoded metafile byte, both UIDs, geometry, references and other metadata.
- Parse host-owned records and fully account for the references and lengths
  affected by resizing. Initially reject unsupported layouts, protection,
  ambiguous references, macros and unqualified private/offset-bearing records.
- Keep the strict `ole` verifier. Add independent OfficeArt intended-change
  comparison and retain a verified compaction baseline when recompression is
  unsupported or does not reduce the final file size.
- Qualify a bounded native replacement interface for host-selected root streams,
  share existing isolated-worker/root budgets and the publication transaction.
- Report discovered/recompressed payload counts, actual strategy, stream/file
  savings and explicit no-op/fallback reasons through the existing API/CLI.
- Prepare PNG/JPEG as a subsequent stage of this architecture. Runtime image
  rewriting requires its own measured pixel/coefficient, metadata and UID
  contract; it is not enabled by the initial EMF/WMF stage.

## Impact

- Affected specs: `officeart-recompression`; coordinates with `ole-compaction`
  and `ppt-ole-recompression` without weakening either preservation contract.
- Expected runtime changes: dedicated OfficeArt codec/adapters/verifier,
  `ole.py`, worker and verifier registration, the native writer and Office docs.
  Reuse the existing option, extras and archive-member propagation.
- Pre-approval work: primary-source research, real fixture acquisition and the
  checksum-bound development experiment `dev/ole/officeart_pilot.py`. This
  experiment is not imported by runtime code and has no publication or dispatch.
- Approval status: approved by the user's “Продолжай” on 2026-10-04 after the
  concrete proposal and measured prototype were presented for approval. Runtime
  implementation of the initial EMF/WMF stage is authorized; raster image
  rewriting remains a subsequent separately qualified contract.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
