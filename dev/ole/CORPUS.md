# Original DOC/XLS/PPT coverage census — 2026-10-05

The census contains 1,055 unchanged originals from three regression collections.
It is not a representative sample of user documents. All lengths, Git blob
SHA-1 identities and SHA-256 hashes were verified.

| Source | Pinned commit | Selection | Originals |
| --- | --- | --- | ---: |
| Apache POI, Apache-2.0 | `12c3688d130035f3dc2ca2a0f50d929456435a93` | Regular DOC/XLS/PPT in the three `test-data` directories, 512 bytes–2 MiB |711|
| Apache POI, Apache-2.0 | Same commit | Same directories, >2 MiB–8 MiB |11|
| LibreOffice core, MPL-2.0 | `cf80890d16f7ef318155efe5843f99153d199e07` | DOC in `sw/qa/extras/ww8export/data` and `ww8import/data`, XLS in `sc/qa/unit/data/xls`, PPT in `sd/qa/unit/data/ppt`, 512 bytes–2 MiB |277|
| NPOI, Apache-2.0 | `nissl-lab/npoi@832eb28f142d54fb8a87b65fa61b5916a763b528`, `dotnetcore/NPOI@9fc667e32476f1a251730141df12e1927349c75c` | DOC/XLS/PPT, 512 bytes–8 MiB, excluding Git blobs already in the three pinned inventories and duplicates between repositories |56|

The Apache-2.0 license/NOTICE and LibreOffice MPL-2.0 license accompany the
selected repository fixtures. Only unchanged test data is imported.

A separate supplemental scan covers the full LibreOffice `sw/qa`, `sc/qa` and
`sd/qa` trees at the same pinned revision. It adds 480 byte-distinct DOC/XLS/PPT
files (169/269/42), 512 bytes–8 MiB, after excluding the primary census by Git
blob identity and excluding `.ppt`-named files under `pptx/`. The pinned
inventory and read-only eligibility report are
[`corpus-libreoffice-qa-extra-inventory.json`](corpus-libreoffice-qa-extra-inventory.json)
and [`qualification-corpus-libreoffice-qa-extra.json`](qualification-corpus-libreoffice-qa-extra.json).

An additional recursive scan of every `poi*` code-module tree and the repository
`src` tree outside the root `test-data` corpus, at the same pinned commit, found
only two byte-distinct OLE-named objects in range: `empty.ppt` (10,240 bytes)
and the example `mortgage-calculation.xls` (37,376 bytes). The PPT is a valid
CFB container but fails the empty/unknown VBA-project host gate. The XLS is
macro-bearing and is therefore excluded from OfficeArt rewriting. The inventory and
read-only eligibility report are
[`corpus-poi-module-extra-inventory.json`](corpus-poi-module-extra-inventory.json)
and [`qualification-corpus-poi-module-extra.json`](qualification-corpus-poi-module-extra.json).

A separate provenance review of
[xberg-io/test_documents at `4139c3b`](https://github.com/xberg-io/test_documents/tree/4139c3b5ad3cbcfca23e181a8b188062ce5f930e)
found ten unique locked DOC/XLS/PPT objects. The pinned attribution and license
records do not map those OLE object hashes to per-file source/license entries,
so none was imported into this fixture corpus.
Two of those DOCs were fetched to temporary storage and matched their locked
length/SHA-256 values: `unit_test_lists.doc` (16,384 bytes,
`fdc498588ed691e016fca96065af8da06cf7fed0fe349294bee76a5f2e98a932`) and
`vendor_renewal_letter.doc` (17,408 bytes,
`61ca2d6060dc66485195a16a0eafce30c651e866b2bf4ee0a6ca04ae9cdca626`). Both
open and export to PDF in LibreOffice and both are readable by olefile, but our
bounded parser rejects them because every live child directory entry is marked
red, creating consecutive red nodes. MS-CFB explicitly forbids that coloring;
the parser also preserves name ordering, cycle, ownership and depth checks, so
this is a clear conformance diagnostic rather than an unexplained DOC failure.
The objects were not retained or added as fixtures because the corpus license
notice says its MIT terms do not cover third-party documents and these hashes
have no per-file source/license attribution.

The pinned inventories record every accepted source URL and identity. Their
corresponding `qualification-corpus*.json` reports record every accepted profile
or exact rejection reason. The survey never
rewrites documents or runs applications. Each independent
content inspector receives a fresh default budget; those stage checks do not
measure cumulative public API resource use or predict compression.

```sh
venv/bin/python -m dev.ole.survey_corpus \
  --cache /tmp/filerepack-corpus-audit/poi --download \
  --output dev/ole/qualification-corpus.json
venv/bin/python -m dev.ole.survey_corpus \
  --inventory dev/ole/corpus-poi-large-inventory.json \
  --cache /tmp/filerepack-corpus-audit/poi-large-survey --download \
  --output dev/ole/qualification-corpus-poi-large.json
venv/bin/python -m dev.ole.survey_corpus \
  --inventory dev/ole/corpus-libreoffice-inventory.json \
  --cache /tmp/filerepack-corpus-audit/libreoffice-survey --download \
  --output dev/ole/qualification-corpus-libreoffice.json
venv/bin/python -m dev.ole.survey_corpus \
  --inventory dev/ole/corpus-npoi-inventory.json \
  --cache /tmp/filerepack-corpus-audit/npoi --download \
  --output dev/ole/qualification-corpus-npoi.json
venv/bin/python -m dev.ole.survey_corpus \
  --inventory dev/ole/corpus-libreoffice-qa-extra-inventory.json \
  --cache /tmp/filerepack-lo-qa-extra/cache --download \
  --output dev/ole/qualification-corpus-libreoffice-qa-extra.json
venv/bin/python -m dev.ole.survey_corpus \
  --inventory dev/ole/corpus-poi-module-extra-inventory.json \
  --cache /tmp/filerepack-poi-module-extra/cache --download \
  --output dev/ole/qualification-corpus-poi-module-extra.json
```

Omit `--download` to verify and inspect an existing cache without fetching files.
A missing/mismatched original makes the census exit unsuccessfully; a partial
report remains available. No unverified download is accepted into the cache.

| Stage | DOC | XLS | PPT | Total |
| --- | ---: | ---: | ---: | ---: |
| Selected and source verified |353|524|178|1055|
| Structural CFB validator |221|328|123|672|
| Application host profile |210|299|39|548|
| Qualified OfficeArt payloads |16|4|1|21|
| Qualified deduplication graph |0|3|1|4|
| Qualified graph with removable entries |0|0|0|0|
| Qualified Word picture operand owned by piece PRM |0|0|0|0|

Across the primary census and the supplemental LibreOffice scan, 256 Word piece
tables parsed successfully; none contains a piece-PRM-owned
`sprmCPicLocation` property. The supplemental scan found two additional
floating-PNG DOCs, no qualified XLS/PPT OfficeArt candidate and no qualified
dedup graph. Those DOCs re-encode 6 and 119 stream bytes respectively, but neither
saves a 512-byte CFB sector beyond strict compaction; both are retained as
diagnostic/preservation fixtures, not compression wins.

Host-profile acceptance alone is not independent-reader/native/application
qualification. Some originals are encrypted, malformed, macro-bearing, older
formats or purpose-built regression inputs. A missing drawing store is also a
normal reason to skip image optimization. The 21 accepted OfficeArt sources are
not all guaranteed to save bytes after CFB sector allocation.

The most common structural rejections are consecutive red directory nodes (122),
unsupported root storage (115), invalid file size/alignment (51), invalid
directory type/name (23) and storage allocation fields (20). Nonzero root
creation time remains rejected: the [MS-CFB root directory specification](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/026fde6e-143d-41bf-a7da-c08b2130d50e)
requires a zero creation field. An application being able to open a file does not
establish that the project can safely rewrite its allocation graph.

After host qualification, the largest OfficeArt exclusions are XFCRC/FRT `0x87c`
(123), SupBook `0x1ae` (49), missing inline Data with an unsupported floating store
(35), no single global drawing group (30) and macro-bearing hosts (20).
The complete per-file reasons, including later compound reasons for Word, are in
the JSON. Word/FOPT rejections now include the numeric property code, for example
`0x242a`, `0x4a51` or `0x186`; those values also survive verbose/JSON and isolated
bulk-worker boundaries. These counts identify qualification priorities; they do not establish
that accepting one record would make every affected file eligible.

## New bounded profiles and pinned originals

- `28774.xls` contains a populated SST, a LabelSst cell and worksheet drawings
  with tertiary scalar fill flags. Version 3/instance 1/size 6/property `0x01BF`
  with fBid/fComplex clear is now qualified for payload recompression. All
  worksheet drawing bytes remain exact. Unknown tertiary properties and all
  tertiary deduplication consumers remain rejected. Each parsed worksheet
  drawing record counts against the same cumulative root node budget as the
  surrounding BIFF/OfficeArt records, including shapes without image payloads.
- A second adjacent MsoDrawingGroup may replace the first Continue, as described
  in [MS-XLS product behavior note 6](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/a3ad4e36-ab66-426c-ba91-b84433312068).
  One complete OfficeArt root is required; third/nonadjacent group fragments are
  rejected. A controlled populated workbook verifies relocated string/worksheet/
  row pointers and byte-exact formulas/cells for this convention.
- `29675.xls` adds a real embedded metafile drawing; `two_images.doc` adds a real
  inline JPEG/PNG pair; `58804_1.doc` adds a real floating PNG. All four originals
  have complete source/candidate preservation and passive rendering evidence in
  `qualification-portfolio.json`.
- `DrawingContinue.xls` and `FloatingPictures.doc` are pinned rejection examples.
  Their unsupported FRT/Word/property/store variants must retain specific skips.
- Seven unchanged LibreOffice originals add six floating DOC layouts (header
  table, transparency, paragraph/character placement, JPEG brightness/contrast
  and WMF line-number case) and an XLS with PNG. Complete independent public API
  preservation and passive page comparisons pass for all seven. Five save file
  sectors beyond strict compaction: JPEG DOC 512 bytes, transparent DOC 1,024,
  two positioning DOCs 2,560 each and PNG XLS 3,584. The other two save stream
  bytes only; their strict-compaction outputs are retained.
- The supplemental full-tree scan adds `fdo66692-2.doc` and
  `tdf131707_flyWrap.doc`, each with a qualified floating PNG. They save 6 and
  119 stream bytes respectively, but fit the same physical allocation as strict
  compaction. Equal page renders and the explicit no-sector-savings diagnostic
  are recorded in the portfolio.
- NPOI `nissl-lab-TestSectionDictionary.doc` has a WMF shared by two consumers:
  397 fewer stream bytes still occupy the same file sectors. The 4,835,840-byte
  `nissl-lab-multimedia.doc` qualifies seven PNG/JPEG payloads in an eight-image
  store and saves25,600 physical bytes beyond compaction. One PNG with an
  unqualified critical chunk remains byte-identical. These variants were selected
  by exact Git blob identities distinct from the prior corpus, not by filenames.
- A supplemental Apache Tika original, `testControlCharacters.doc`, is pinned
  separately from this three-repository census. Its 99,441-byte PNG raster saves
  17,289 stream bytes and 17,408 allocated file bytes with equal rendered pages.
  The fixture includes the pinned Tika license and notice; provenance is in
  `test/fixtures/ole_extended/provenance.json`.
- The expanded Apache Tika scan also found `testPPT_2imgs.ppt` with one exact
  empty VBAInfoAtom `(persistIdRef=0, fHasMacros=0, version=2)` and no VBA storage
  record. It now qualifies for macro-free PPT host compaction; its OfficeArt
  rewriter still rejects record type 1058, so no drawing payload is changed. The
  verified strict-compaction fallback retains the 124,928-byte file and reports
  that record-level reason; it provides no physical-size reduction. The pinned
  Tika original is covered by the same Apache-2.0 fixture notice.
- A pinned scan of the 100-file DOC/XLS/PPT NapierOne tiny subsets found 19
  OfficeArt-qualified DOCs, no picture locations owned by a piece PRM, and no
  qualified OfficeArt graphs among the XLS/PPT subsets. Eighteen DOC originals
  saved 512–35,840 bytes beyond strict compaction with exact OfficeArt/CFB
  preservation and 18/18 equal LibreOffice page sets. Three diverse DOCs (PNG +
  WMF, PNG + EMF, and JPEG) are added as external originals under Open Government
  Licence v3.0 and the Edinburgh Napier University dataset license. Their source
  archive, member paths, hashes, and required attribution are pinned; NapierOne's
  original URL mapping is available from its researchers on request and is not
  included in this repository.
- A follow-up survey of all 1,000 DOCs and 1,000 XLSs in the NapierOne small
  subsets found 121 supported floating OfficeArt DOC graphs among 794 files
  passing the CFB/Word gates. None of the 794 parsed DOCs has a piece-PRM picture
  location. Repacking all 121 supported graphs preserved the OfficeArt
  interpretation; 111 saved physical bytes beyond strict compaction. After
  excluding the 19 tiny-subset overlaps, 93 new originals save 851,456 bytes in
  aggregate beyond compaction. Three new originals representing three EMFs, a
  12-raster PNG store and a separate PNG each render to identical pages after
  recompression; these are pinned as regression fixtures. Among the 1,000 XLSs,
  698 were valid CFB containers and 679 passed the XLS host profile, but none
  produced a supported OfficeArt graph. The SHA-256-pinned inventories,
  per-file reasons and full candidate measurements are in
  [`corpus-napierone-small-inventory.json`](corpus-napierone-small-inventory.json),
  [`qualification-corpus-napierone-small.json`](qualification-corpus-napierone-small.json)
  and [`qualification-napierone-doc-small-positive.json`](qualification-napierone-doc-small-positive.json).
  The populated-BIFF8 original fixture gap remains open.
- A SHA-256-verified scan of all 4,999 ordinary `.xls` members in NapierOne's
  628 MB `XLS-total.zip` adds 3,923 byte-distinct workbooks after deduplicating
  the 1,000 small-subset entries by content hash. Of these, 3,447 pass CFB
  validation and 3,368 pass the XLS host profile, but none yields a supported
  OfficeArt graph. The largest
  OfficeArt barriers are BIFF records `0x87c` (1,703 files), `0x293` (530),
  `0x1ae` (425) and `0x1ba` (325); macro-bearing hosts remain rejected. The
  full inventory and per-file diagnostics are
  [`corpus-napierone-xls-total-inventory.json`](corpus-napierone-xls-total-inventory.json)
  and [`qualification-corpus-napierone-xls-total.json`](qualification-corpus-napierone-xls-total.json).
  The separate 100-file `XLS-NOMAGIC-tiny` subset has zeroed leading bytes and
  none of its files is a CFB container; it is documented in
  [`corpus-napierone-xls-nomagic-tiny-inventory.json`](corpus-napierone-xls-nomagic-tiny-inventory.json)
  and [`qualification-corpus-napierone-xls-nomagic-tiny.json`](qualification-corpus-napierone-xls-nomagic-tiny.json).
- A scan of all 5,000 DOC members in NapierOne `DOC-total.zip` found 608
  supported floating OfficeArt graphs among 4,030 host-qualified documents.
  Across the 4,040 parsed Word documents, none has a piece-PRM-owned picture
  location. After content-hash overlap with DOC-small, 486 new unique supported
  graphs were repacked and passed preservation checks; 406 saved 4,731,904 bytes
  in aggregate beyond strict compaction. Two high-saving originals (one EMF plus
  one raster, and one EMF plus nine rasters) render to identical LibreOffice
  page sets and are pinned as fixtures. The inventory, per-file qualification,
  measurements and render hashes are in
  [`corpus-napierone-doc-total-inventory.json`](corpus-napierone-doc-total-inventory.json),
  [`qualification-corpus-napierone-doc-total.json`](qualification-corpus-napierone-doc-total.json),
  [`qualification-napierone-doc-total-positive.json`](qualification-napierone-doc-total-positive.json)
  and [`qualification-napierone-doc-total-render.json`](qualification-napierone-doc-total-render.json).
- An independent Gnumeric 1.12.57-1.1 source scan covers all 26 `.xls` samples
  under `samples/`: 23 are valid CFBs, 20 pass the XLS host profile, and none
  yields a supported OfficeArt graph. Individual source URLs, lengths and
  SHA-256 hashes, plus the Debian copyright file hash, are pinned in
  [`corpus-gnumeric-xls-inventory.json`](corpus-gnumeric-xls-inventory.json);
  per-file profile outcomes are in
  [`qualification-corpus-gnumeric-xls.json`](qualification-corpus-gnumeric-xls.json).
- Two additional xberg-locked DOC candidates were checked against their pinned
  SHA-256 values and opened/exported by LibreOffice. Both fail the MS-CFB
  no-consecutive-red rule (all live sibling nodes are marked red), which verbose
  repacking reports as `OLE: consecutive red directory nodes`; their missing
  source/license mapping also prevents fixture redistribution. This confirms
  that a readable document can still be rejected for a specific structural-
  conformance reason.

Primary property references:
[OfficeArtTertiaryFOPT](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/a687e90c-1748-4f57-8758-be31cfb36185),
[Fill Style Boolean Properties](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/baf2613d-c676-43c8-8077-828bdcc70dca).

## Remaining original-fixture qualification

The census found no removable duplicate in the four fully qualified graphs and
no piece-PRM-owned picture operand in the qualified Word layouts. Repeated empty
FBSE slots are not evidence of duplicated live images. The positive repeated-entry,
piece-owned picture locations and richer formula/row/continued-string cases remain controlled
derivatives of licensed originals and are labelled accordingly.

Qualified inline originals already inherit font/language properties from paragraph
styles; their picture locations are direct character-FKP operands. Three originals
now explicitly verify permitted inherited font properties, aliases and unchanged
style bytes through image recompression.

The earlier search for a style-owned picture location was based on an incorrect
synthetic case. [MS-DOC UpxChpx](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/0188ecda-b590-4cb4-bb95-e76a47a9a2e2)
forbids properties preserved by [sprmCIstd](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/7022285b-9621-42e9-ad4d-4e02c115ef18),
including picture/OLE identity and special-character flags. That case is now
rejected, not treated as an outstanding original-fixture goal. The positive
character-style control inherits font size and keeps picture identity direct.
Piece PRMs belong to [direct character formatting](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/be58bf9c-d1d3-40cc-91ee-36452d7939b2)
and retain their separate location-provenance qualification.

The two broader original-fixture acquisition tasks remain open. This census does
not widen protection/CFB/FRT/history/private-consumer gates to manufacture a
positive case. Microsoft Office repair behavior, Hancom Office and remote native
platform runs remain unqualified; LibreOffice page agreement supplements the
independent byte/reference contracts.
