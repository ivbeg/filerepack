## Findings on the supplied corpus

The input files remain unchanged. The root-normalized copy of
`mapping_rus_v1.ppt` has the same logical stream hashes as its original, and is
not a fourth independent presentation. The report pins all four input hashes.

| File | Slides | Notes pages | Notes master | Pictures | Pictures bytes | PNG zlib9 stream savings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| crimemapping_v2.ppt | 12 | 12 | 1 | 19 | 5,928,838 | 595,977 |
| mapping_rus_v1.ppt | 45 | 45 | 1 | 50 | 20,014,327 | 2,138,915 |
| ruslocal_v1.ppt | 31 | 31 | 1 | 31 | 14,411,725 | 1,634,445 |

Each file has one document, seven main masters, one persist directory, one user
edit and seven compressed storage atoms in the trailing object block. Notes
containers are already structurally readable. Their ordinary slide/notes
references agree in both directions; the notes-master field deviation is
recorded separately from graph errors.

The seven storage payloads in each presentation are identical, including across
presentations: 720,810 encoded bytes and 2,368,000 decoded bytes each. Their
CompObj identifies Adobe Photoshop Image, their ExOleObjAtom subtype is 0
(`ExOleSub_Default`), and their ExObjRefAtom consumers belong to main masters
(1016), not slides (1006). Zlib9 produces 721,240 bytes, an increase of 430 bytes.
The nested strict CFB validator rejects consecutive red directory nodes, although
olefile reads the four nested streams without reporting defects. This disagreement
does not justify relaxing the nested DOC/XLS contract. The Pictures strategy can
leave the complete nested wrapper and every associated reference untouched.

All Pictures records parse individually within the current per-image limits.
There are 18/49/31 PNGs and 1/1/0 JPEGs. Their aggregate parsed sample workloads
are 23,614,700 / 101,383,402 / 77,037,361 bytes, so the current 64 MiB aggregate
selection gate rejects the two larger files. No JPEG rewrite was attempted by
this experiment. PNG trials only re-encode the exact original filtered bytes,
and reparse each candidate to compare the full existing preservation fingerprint.

The BStore entries include shared reference counts: 7 and 11 in the first/third
files, and 7 and 13 in the second. All other entries have count 1. Sharing already
exists; recompression does not require deduplication or rewriting consumers.

## Why adding 1008 to the allowlist is insufficient

1. `_extensions()` also rejects 1009 (`NotesAtom`) and 25 other observed types.
2. `_extensions()` currently admits only one tiny PPT10 blob form. Actual tags
   also carry text, build, timing and round-trip records, with blobs of 9–318 bytes.
3. `inspect_records()` allows only document/main-master/slide top-level objects,
   and only SlideListWithText instances 0 and 1. Notes use instance 2.
4. Its liveness set omits DocumentAtom.notesMasterPersistIdRef and notes links.
5. `_embedded()` requires DOC/XLS subtype 2/3 and a slide owner, excluding all
   seven observed subtype-0 objects with master owners.
6. `inspect_ppt()` calls this entire embedded-object-specific gate before looking
   at Pictures, then rejects shared FBSE entries and oversized aggregate workloads.
7. PPT deduplication additionally rejects secondary/tertiary FOPT records. It is
   a separate, more invasive operation and remains outside this proposal.

Observed unqualified outer record kinds are:

| Types | Role to audit |
| --- | --- |
| 1008, 1009 | Notes container and fixed-size notes atom |
| 1017, 1025, 1031 | Slide-show data and outline view |
| 1038, 1039, 1052–1056, 1059, 1063, 1064 | Round-trip themes, IDs, placeholders, styles and tables |
| 4006, 4018 | Text ruler and extended text master styles |
| 4051, 4055, 4057, 4058, 4063, 4082, 4083 | Hyperlinks, headers/footers and interaction data |
| 11019, 11021 | Round-trip animation and its checksum |
| 61730 (0xF122) | OfficeArt tertiary property table |

BinaryTagDataBlob content is a separate record space: it must be bounded and
qualified under the enclosing tag name and owner, not treated as generic unknown
bytes merely because outer offsets stay fixed. The report includes each blob's
name, size, contained kinds and hash.

## Proposed host graph

Introduce `PptHostLayout` (or a comparably small internal type) containing the
original Document/Current User bytes, parsed records, persist IDs/field locations,
edit/index boundaries and typed live objects. It must not require an embedded
DOC/XLS payload to exist merely to qualify a presentation with pictures.

Keep the current single-edit restriction, protection checks, independent outer
manifest check, complete record bounds, unique persist IDs/targets and complete
top-level liveness accounting. Build a child-position index once to avoid repeated
whole-record scans. Never infer an object role from its record kind alone.

Interpret SlideListWithText (4080) by instance:

- 0: SlidePersistAtom -> live SlideContainer (1006), keyed by slideId.
- 1: MasterPersistAtom -> live MainMasterContainer (1016), keyed by masterId.
- 2: NotesPersistAtom -> live NotesContainer (1008), keyed by notesId.

Resolve notesMasterPersistIdRef from the 40-byte DocumentAtom. For the first
profile, keep unsupported handout-master layouts rejected instead of claiming
support incidentally. Zero notesIdRef on a slide means no notes; zero notes-master
reference is only eligible when other inheritance/reference constraints allow it.

For each ordinary notes page require an unambiguous notesId -> persist target,
exactly one NotesAtom with version 1/instance 0/length 8, a valid containing
NotesContainer version 15/instance 0, and agreement between
SlideAtom.notesIdRef and NotesAtom.slideIdRef. Reject duplicates, wrong target
roles, missing references, unreferenced containers and ambiguous ownership. Check
required drawing/color children, permitted optional ordering and unique round-trip
records. IDs are logical identifiers; they must never be interpreted as byte offsets.

Use the DocumentAtom reference to identify the notes master. Accept the normative
master fields `(0, 0)`. The proposed compatibility form is exactly
`(0x80000000, 2)` in the unique separately referenced notes master, never in an
ordinary notes page or as an unresolved regular slide reference. Preserve both
fields, plus the nonzero `unused` field, verbatim. The latter is explicitly ignored
by MS-PPT and must not be zero-normalized. This narrow old variant needs an
independent reader/rendering qualification before runtime acceptance; the supplied
corpus alone is insufficient to call arbitrary nonzero master fields supported.

Audit header versions, allowed owners, lengths and references for every admitted
outer/extension variant. Unknown extensions remain rejected in the first profile.
Nested ECMA-376 round-trip theme/animation atoms are retained as exact bounded
payloads; they are not converted, recompressed, removed or used to resave the PPT.

## Separate operation eligibility

`inspect_records()` should use the host graph plus the existing strict embedded
selection contract. Its DOC/XLS subtype rules, strict nested manifest checks and
trailing-block relocation rules remain scoped to records actually re-encoded.

`inspect_ppt()` should use the host graph plus a Pictures-specific contract:

- Account for every external object reference and its live owner, including main
  masters, but treat unselected subtype-0 storage wrappers as immutable spans.
  They remain precisely bound to their original persist IDs and consumers.
- Require one recognized BStore under the live document drawing group, complete
  Pictures record framing and valid BLIP headers/UIDs/resource tags.
- Allow positive `cRef` values; validate the referenced BStore index and recorded
  size/UID/type. Keep entry count, order, indexes and sharing unchanged. Audit the
  ordinary `pib` consumers (including notes/master drawings) and relevant property
  forms; do not confuse complex-property lengths with simple BLIP indexes.
- Reject missing/aliased delay-store ownership until an explicit contract exists.
  A shared FBSE's `cRef > 1` is distinct from multiple entries aliasing a payload.
- Retain all original records if they are not selected for re-encoding. No nested
  Photoshop CFB parsing or repair is required to prove the bytes stayed identical.

A Pictures-only rewrite preserves the Document stream length and every PPT record
position. It changes only the exact allowed FBSE `size` and `foDelay` fields.
Consequently persist targets, UserEdit, Current User, OLE wrappers, notes text,
themes, animation metadata and all shape properties remain at their original
locations and are compared exactly. Moving delay-store BLIPs still requires
complete delay-reference discovery; opaque extensions are not a shortcut around it.

## Bounded selection and preservation

Do not simply increase the 64 MiB gate. First parse the record directory and
bounded image headers, then choose PNGs in Pictures order whose declared filtered
sample sizes fit a cumulative 64 MiB selection allowance. Retain the remaining
BLIPs byte-identically. Per-image, file, object-count, root decoded-byte, memory,
scratch and timeout budgets continue to apply; a real root-budget exhaustion must
fail the trial, not be swallowed as an unsupported image.

The research's PNG-only selection saves 595,977 bytes on 18 selected PNGs;
1,499,469 on 37; and 1,431,579 on 27. This is one deterministic policy to qualify,
not an optimal compression claim. A stronger selection policy can follow measured
evidence later. JPEGs remain unchanged for the first corpus qualification.

Encode and compare selected PNGs sequentially, release expanded samples between
images, and bind each selected record to its index/header/hash. Reparse the
candidate with an independently derived selected-record contract: original filtered
samples and every non-IDAT chunk must match. Compare unselected BLIPs byte-for-byte.
Compare the complete Document bytes after normalizing only the enumerated FBSE
size/delay fields; verify each normalized value maps to the same logical image.
Do not normalize NotesAtom bytes, OLE data, count/UID fields or unknown bytes.

Continue comparing all outer CFB object metadata and other live stream hashes,
using the existing native replacement capability and transaction workflow. Select
by actual fully verified file size relative to compaction; stream-byte savings do
not establish physical savings. A native whole-file candidate, union verification,
negative mutations and bounded-worker memory measurements are implementation tasks.

## Validation and rollout

Use generated format fixtures for normative and old notes-master cases plus the
three pinned presentations locally. Include notes on/off, multiple masters, shared
picture references and records with no embedded DOC/XLS data. Mutate notes IDs,
persist roles, child headers, duplicate masters, storage bytes, extension records,
shared counts, FBSE UID/size/delay fields and bytes outside the write mask. Verify
rejection before publication and unchanged sources/destinations on every failure.

Qualify rendering with an independent PPT implementation (and, where available,
PowerPoint notes/slide extraction) to check notes-master compatibility and document
appearance. Rendering supplements the exact verifier; it does not replace it.
Run affected PPT/OfficeArt/verification/transaction/archive tests, compatibility
checks and native integration under the existing supported Python/platform matrix.
Record peak memory on the largest supplied file and fail closed at existing limits.

## Primary references

- [MS-PPT NotesContainer](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/50bfc0f7-c101-4c32-8754-6ca59772b785)
- [MS-PPT NotesAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/9bb3e352-1014-477b-b286-cd43127c3b74)
- [MS-PPT DocumentAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/121f2728-3497-4a0a-829e-6f416fee2ee6)
- [MS-PPT NotesListWithTextContainer](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/55453e37-0674-4703-bd8d-fcaba335f840)
- [MS-PPT NotesPersistAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/b595ad14-a46c-4fcc-b4bd-7298712043a4)
- [MS-PPT SlideAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/57e11e6c-e550-4c43-80b6-72731eee8abd)
- [MS-PPT NotesRoundTripAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/95d576ad-f038-4062-83f1-c8b31e01db00)
- [MS-PPT programmable tag forms](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/ac9aa6bd-3c15-49bd-81d9-5b8bfd966053)
- [MS-PPT PP10SlideBinaryTagExtension](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/ccb82f60-e1ae-4379-b1e0-00909bb70b17)
- [MS-PPT ExOleObjAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/a3517016-8e32-4585-9a42-adae02eea798)
- [MS-PPT ExOleObjSubTypeEnum](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/9851ea47-c044-476a-9302-6904de72d279)
- [MS-ODRAW OfficeArtTertiaryFOPT](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/a687e90c-1748-4f57-8758-be31cfb36185)
