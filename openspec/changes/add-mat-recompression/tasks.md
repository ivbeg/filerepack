> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Establish feasible profiles

- [ ] 1.1 Acquire complete real MAT files from additional origins and reproduce the two probes.
- [x] 1.2 Measure existing `miCOMPRESSED` recompression, including unchanged and bounded-out files.
- [ ] 1.3 Prepare trusted v4/v6/v7/v7.3, endian, small-tag, padding, sparse, complex,
  cell, struct, logical, Unicode, empty and unsupported-object fixtures.

## 2. Implement Level-5 recompression

- [x] 2.1 Implement dialect detection and complete bounded passive element validation.
- [x] 2.2 Recompress existing envelopes, preserve raw unaffected records and verify exact
  decoded payloads and framing before shared candidate publication.
- [x] 2.3 Register only passing profiles and report unsupported/no-benefit reasons accurately.

## 3. Add the separately gated v7.3 profile

- [x] 3.1 Integrate HDF5 graph, reference and user-block preservation without generic alias routing.
- [ ] 3.2 Obtain native MATLAB read-back for the declared v7.3 fixture subset and record reader floor.

## 4. Verify and document

- [x] 4.1 Exercise damaged tags, zlib checksums, subsystem offsets, decode limits,
  cancellation, publication failures and larger candidates.
- [ ] 4.2 Record native MATLAB and applicable secondary-reader results, provenance,
  size/time/memory measurements and unsupported variants for each enabled profile.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
