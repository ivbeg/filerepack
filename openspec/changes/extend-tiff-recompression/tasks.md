> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Establish TIFF profiles

- [ ] 1.1 Sample complete real TIFF files from multiple Commons creators/collections and
  scientific/geospatial sources, with versions, checksums and provenance.
- [ ] 1.2 Measure lossless native candidates and read cost across current compression
  methods; include all unchanged, rejected and unsupported files.
- [ ] 1.3 Prepare multipage/SubIFD/pyramid, classic/BigTIFF, endian, palette, alpha,
  high-depth, signed/float, planar, ICC/EXIF/XMP and GeoTIFF/COG fixtures.

## 2. Implement preservation and candidate selection

- [x] 2.1 Add complete bounded IFD/tag inspection and typed sample comparison.
- [x] 2.2 Enumerate mutable storage tags and reject unknown non-relocatable metadata.
- [x] 2.3 Remove stripping from the preserving path and select eligible native codec/predictor backends.
- [x] 2.4 Integrate shared budgets, acceptance and file transaction publication.
- [ ] 2.5 Enable GeoTIFF/COG subprofiles only with semantic and layout validation.

## 3. Verify and document

- [x] 3.1 Exercise corrupt offsets/IFD cycles, decompression limits, dropped tags/pages,
  source changes, cancellation, missing decoders and larger candidates.
- [ ] 3.2 Verify exact native samples and metadata with independent read-only adapters
  and document tested backend/platform and reader coverage.
- [x] 3.3 Publish observed corpus gain/cost and precise supported sample/tag/IFD profiles.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
