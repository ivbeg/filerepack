# Change: Support notes-bearing legacy PPT hosts for Pictures recompression

## Why

The three supplied presentations fail the record-recompression gate first at
record type 1008 (`NotesContainer`). The generic record reader already parses
these containers. Adding this type alone would reveal other failures: 27
currently unqualified record types, richer programmable tags, embedded Photoshop
objects referenced by masters, shared Pictures entries and aggregate image limits.

Read-only experiments preserve every PNG filtered scanline and non-IDAT chunk
while saving 595,977 / 2,138,915 / 1,634,445 stream bytes respectively. A narrower
Pictures-order selection within the existing 64 MiB original-sample workload saves
595,977 / 1,499,469 / 1,431,579 bytes. These are feasibility measurements, not
verified whole-file savings or runtime eligibility claims.

## What Changes

- Add an audited, notes-aware single-edit host graph shared by PPT inspection
  strategies. Validate notes lists, notes IDs, reverse slide links and the notes
  master selected by DocumentAtom. Preserve all notes bytes.
- Qualify the observed old notes-master variant separately from the normative
  form. The supplied files have `(slideIdRef, slideFlags) = (0x80000000, 2)` in the
  uniquely referenced notes master, instead of the specified `(0, 0)`.
- Separate Pictures eligibility from nested DOC/XLS record-recompression
  eligibility. Preserve the seven Photoshop storage wrappers, their master
  references, persist directory and edit offsets byte-identically.
- Audit the observed standard records and PPT9/PPT10/PPT12 tags by role and
  reference semantics; preserve their bytes. Unknown types or extensions remain
  outside the first new profile.
- Support positive shared FBSE `cRef` values without changing BStore indexes,
  entry counts, UID, sharing or shape properties. Update only selected BLIP
  payloads and the corresponding FBSE size/delay-store offsets.
- Select a deterministic bounded subset of PNG records and retain other records
  byte-identically, keeping existing operation limits and Python 3.9+ support.
- Independently verify the complete intended change and measure native candidate
  size against ordinary compaction before publication.

## Impact

- Specs: additive requirements in `ppt-ole-recompression` and
  `officeart-recompression`; existing requirements retain their unique owners.
- Expected code: `ole_ppt_records.py`, a shared PPT host/notes validator,
  `ole_ppt_art.py`, `ole_officeart.py`, `ole_recompress.py`, verification and tests.
- No new CLI option, default behavior change, mandatory dependency, history
  rewriting, OLE-object deduplication or application resave is proposed.
- Evidence: `dev/ole/analyze_ppt_notes.py` and
  `dev/ole/qualification-ppt-notes-analysis.json`.
- Approval: user authorized implementation with “Сделай это” on 2026-10-08.
  Implementation and local Python/native/independent-renderer qualification are
  complete. Evidence: `dev/ole/qualification-ppt-notes-runtime.json` and
  `dev/ole/README.md`. Remote CI and Microsoft PowerPoint qualification are not
  asserted; no release/deployment or archive is implied.
