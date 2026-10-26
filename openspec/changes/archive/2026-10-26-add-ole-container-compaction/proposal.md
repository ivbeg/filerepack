# Change: Add preserving OLE container compaction

## Why

Legacy Office binary files can contain unused Compound File Binary (CFB) sectors
that occupy disk space without belonging to live document streams. filerepack
currently supports ZIP-based Office documents, but has no DOC/XLS/PPT writer or
CFB preservation verifier. A container compactor can reclaim that space while
retaining the original format and every live stream byte.

## What Changes

- Add a bounded CFB inspection and preservation manifest, including empty
  storages, stream hashes and directory metadata.
- Qualify an optional writer using real Office fixtures and independently read
  its candidates before advertising support.
- Initially compact eligible version-3 CFB Office 97–2003 profiles: DOC/DOT,
  BIFF8 XLS/XLT/XLA and PPT/POT/PPS. Route by both extension and document structure.
- Preserve all stream bytes and logical storage metadata; rebuild allocation
  structures to eliminate reclaimable container space.
- Skip encrypted, signed, rights-managed, malformed, unclassified or unsupported
  files, including cases where protection cannot be determined.
- Retain qualified canonical unsigned DOC/XLS/PPT VBA projects opaquely after
  bounded host signature checks; keep unknown VBA layouts unsupported.
- Use the existing candidate transaction, verification, dry-run, size acceptance
  and filesystem preservation contracts for standalone and archive-member work.
- Document that this stage performs compaction, with no arbitrary compression of
  Office content. Record later opportunities for PPT compressed OLE objects,
  OfficeArt images/metafiles and embedded documents in the design.

## Impact

- Affected specs: new `ole-compaction`; coordinates with pending
  `format-capabilities`, `output-validation`, `nested-assets`, `inspection`,
  `operation-budgets` and `repack-outcomes` work without duplicating their APIs.
- Expected code: new `filerepack/ole.py` and `filerepack/ole_verify.py`, extension
  routing, standalone dispatch, validators, optional backend discovery,
  tests and Office documentation. Exact backend packaging awaits qualification.
- Implementation authorized by the user's follow-up on 2026-10-04. The selected
  backend is an optional native `cfb 0.14.0` helper with `olefile 0.47` validation;
  measured qualification evidence is in `dev/ole/qualification.json` and
  `dev/ole/qualification-vba.json`. The user's “Продолжай” follow-up authorizes
  the continued unsigned-VBA qualification within the original conditional scope.
- The next “Продолжай” authorizes extending that qualification to canonical
  single-edit PPT/POT/PPS projects. This retains every outer stream and encoded
  project byte; record-level recompression remains a later, separate change.
