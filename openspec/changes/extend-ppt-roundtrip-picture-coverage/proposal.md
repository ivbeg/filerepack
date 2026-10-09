# Change: Qualify additional PPT round-trip records for Pictures recompression

## Why

The supplied `temp/_raw/Apps4Russia_proposal_all.ppt` passes ordinary OLE
compaction but `--ole-recompress` rejects its Pictures host at record 1058.
The measured public dry-run result is 2,694,144 -> 2,688,512 bytes (0.21%).
The file has 11 slides, one ordinary notes page, a notes master and no embedded
OLE storages. Its 32 Pictures records occupy 2,294,732 bytes.

Read-only image trials using the existing bounded PNG codec independently verify
600,990 bytes of savings on 13 PNGs, approximately 22.31% of the source file.
JPEGs and three unsupported PNGs remain unchanged. This is image-only feasibility,
not verified whole-file savings or runtime qualification. The source SHA-256
remains `971add29b0d952bf8873afb5c33cab50ad6c1ee47497cd31d67cb3e510fdb13a`.

Adding 1058 alone is insufficient: the Pictures gate also rejects layout instances
7–11 of record 1054, the color-MRU record 61722, multi-property instances of
61730 and shape-owned PPT9 tags. Existing notes/reference helpers pass when
examined independently; no production gate has been relaxed.

## What Changes

- Audit and qualify the observed standard round-trip record forms by version,
  instance, length, owner and reference semantics for Pictures-only rewriting.
- Qualify shape-owned `___PPT9` tags containing the observed record-4012 form;
  retain unknown names, versions, owners and malformed blob rejection.
- Preserve all round-trip packages, shape data, notes, logical identifiers,
  persist/edit offsets and Current User bytes exactly. Use the existing exact
  FBSE size/delay write mask and independent PNG sample/metadata verifier.
- Retain current image selection, limits, JPEG/unsupported-PNG preservation,
  native writer, physical-savings acceptance and dry-run/publication workflow.
- Make verbose diagnostics explicit when the Pictures qualification fails, even
  when the same failure also appears in compressed-record strategy diagnostics.
- Add generated positive/negative fixtures and qualify this original file and
  existing PPT corpus through native preservation and independent rendering.

## Impact

- Spec: one additive `officeart-recompression` requirement. Existing requirements
  and their unique delta owners remain unchanged.
- Expected runtime files: `ole_ppt_extensions.py`, `ole_ppt_art.py` where required
  by audited references, and CLI diagnostics; generated fixtures and OLE tests.
- No new option, dependency, lossy operation, application resave, archive format
  or default resource-limit change.
- Evidence: `dev/ole/analysis-ppt-apps4russia.json`; reproduce with
  `venv/bin/python -m dev.ole.analyze_ppt_roundtrip temp/_raw/Apps4Russia_proposal_all.ppt --output temp/apps4russia-analysis.json`.
- Approval: user authorized implementation with “Реализуй” on 2026-10-08.
  Local runtime/native/render qualification is complete; see
  `dev/ole/qualification-ppt-roundtrip-runtime.json`. Initial original-metadata publication
  hit the strict macOS provenance refusal; an exact-byte copy with ordinary
  permissions publishes and independently preserves complete document content.
  The user requested continuation on the remaining refusal. The publication
  correction retains only native stage-creation provenance when absent from the
  source; direct original output now retains mode 0700 and mtime, with the same
  independently verified candidate. See `dev/ole/qualification-ppt-macos-publication.json`.
  Remote CI and Microsoft PowerPoint are not asserted.
