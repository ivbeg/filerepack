# Change: Optimize qualified embedded payloads in DOC/XLS

## Why

Embedded files and CFB objects can dominate a document's size, while current
DOC/XLS processing preserves their bytes. Applying existing verified child
packers needs wrapper/reference-aware reconstruction and a new intended-change
contract because the old PPT pass preserves exact decoded nested storage bytes.

## What Changes

- Add separate opt-in ole_embedded_recompress / --ole-embedded-recompress,
  default false, for qualified DOC/DOT and XLS/XLT/XLA object profiles.
- Distinguish direct CFB substorages, serialized CFB payloads and recognized
  Ole10Native/package wrappers; initially admit embedded files with complete
  host/wrapper/reference maps and verified lossless child packers.
- Recurse through one root budget and compare parent/child intended-change
  manifests, preserving object class, names, links and presentation data.
- Update lengths/references and use a separately qualified bounded native
  replacement interface where substorage rewriting is required.
- Keep existing ole_recompress and exact PPT wrapper behavior independent;
  select the smallest fully verified parent candidate.

## Impact

- New capability: ole-embedded-recompression; coordinates with ole-compaction,
  officeart-recompression, child verification and archive-member preservation.
- Expected code: host object parsers, wrapper codecs, nested operation context,
  native writer, worker/verifier registration, models/CLI/dispatch and docs.
- Priority: P2. Prerequisites: strict OLE and delivered verified child packers;
  expanded DOC/XLS reference coverage where the chosen object profile needs it.
- VBA, ActiveX/controls, linked objects, arbitrary opaque payload carving,
  application resaving and lossy/conversion child operations remain excluded.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

Use real licensed embedded DOC/XLS, OOXML and archive examples with original
wrapper fields/presentation caches and deep nesting controls. Independently verify
each child and reconstructed parent, test stale lengths/IDs and budget exhaustion,
and measure final parent savings rather than extracted-child savings alone.
