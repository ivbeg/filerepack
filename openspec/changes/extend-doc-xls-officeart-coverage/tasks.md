## 1. Host qualification

- [x] 1.1 Inventory current accepted/rejected records and create a versioned offset/reference matrix from MS-DOC/MS-XLS.
- [ ] 1.2 Acquire pinned, licensed real populated BIFF8 and inherited/mixed/floating Word fixtures with provenance.
- [x] 1.3 Implement complete BIFF8 record identities, drawing fragmentation and BoundSheet/Index/DBCell/ExtSST relocation.
- [x] 1.4 Qualify cells/formulas, row blocks and SST/CONTINUE while preserving their original bytes and encodings.
- [x] 1.5 Resolve Word piece/style inheritance and shared property operand provenance.
- [x] 1.6 Qualify mixed Data boundaries, aliases and floating drawing/FIB-table relocation as separate profiles.

## 2. Verification and integration

- [x] 2.1 Extend independent graph comparison and account for every permitted patch and unchanged byte.
- [x] 2.2 Retain existing protection/macro gates, root budgets, native capabilities and strict fallback.
- [x] 2.3 Exercise stale/wrong-target pointers, SST continuation transitions, row-block boundaries, ambiguous aliases and unknown records.
- [x] 2.4 Test standalone aliases, archive members, dry-run, output/backup/threshold behavior and verbose/JSON diagnostics.

## 3. Delivery evidence

- [x] 3.1 Compare complete preservation manifests and pinned application output for each newly enabled profile.
- [x] 3.2 Measure real eligibility, physical savings versus compaction, time and memory; separate synthetic controls.
- [x] 3.3 Run relevant source/artifact/native/platform/static/docs checks and strict OpenSpec validation.
- [x] 3.4 Publish the exact supported record families and remaining platform/application limitations before enabling them.

## Implementation evidence (2026-10-05)

Bounded runtime profiles and local preservation/application measurements:
[portfolio report](../../../dev/ole/PORTFOLIO.md),
[public API JSON](../../../dev/ole/qualification-portfolio.json).
Controls are labelled separately from originals. Office/Hancom and remote native
platform execution are unavailable and are not reported as passed.
Original-corpus expansion items remain unchecked; final source/artifact/static/docs
gates are checked only after their completed runs. No deployment/archive is claimed.
Item 1.2 is partial: original floating/inline JPEG+PNG Word and populated
SST/LabelSst worksheet fixtures are pinned. Three originals explicitly qualify
permitted font/language inheritance. Richer piece-owned locations and populated
formula/row/continued-string pointer combinations remain controlled derivatives.
The [1,055-file census](../../../dev/ole/CORPUS.md) adds thirteen unchanged positive
DOC/XLS fixtures and two rejection fixtures, with complete public API/application
evidence for the qualified additions. Seven new LibreOffice sources include five
files with sector savings beyond strict compaction. Two distinct NPOI originals
add shared WMF and eight-image PNG/JPEG/opaque-PNG stores. It found no eligible
piece-PRM-owned Word picture operand. Unmodified originals exercising all combinations remain
pending. The audited adjacent second-MsoDrawingGroup and scalar tertiary fill
profiles retain the existing unknown-consumer/record gates and root budget.
One supplemental Apache Tika DOC with a large PNG raster is pinned outside the
1,055-file census; it saves 17,408 physical bytes with exact OLE preservation and
equal rendered pages. It does not satisfy the outstanding piece-PRM or removable-
dedup-original qualification tasks.
The supplemental Tika tree also contains `testPPT_2imgs.ppt`, whose exact empty
VBAInfoAtom (`persistIdRef=0`, `fHasMacros=0`, version 2) and absent project
storage qualify the host as macro-free. Its unknown OfficeArt record 1058 still
uses strict compaction only, so this fixture does not close the DOC/XLS original
coverage or PPT record-rewriting gap.
A pinned NapierOne tiny-subset scan adds three licensed floating DOC originals
with PNG/WMF, PNG/EMF and JPEG payloads. Eighteen of 19 qualified DOCs save
512–35,840 bytes beyond strict compaction with equal rendered pages; no
piece-PRM-owned picture operand appears in the 100-file DOC subset, and the
100-file XLS subset has no qualified populated BIFF8 OfficeArt graph. The
NapierOne archive/member/hash/license attribution is recorded in the corpus
inventory; its original source URL map is available from its researchers on
request. Task 1.2 remains partial pending a suitable populated BIFF8 original.
The follow-up NapierOne small-subset scan covered all 1,000 DOCs and 1,000 XLSs:
121 supported floating OfficeArt graphs were found among 794 host-qualified
DOCs, with no piece-PRM picture location; no XLS produced a supported OfficeArt
graph. Repacking all 121 preserved the OfficeArt interpretation, and 93 new
byte-distinct originals save 851,456 physical bytes beyond compaction. Three
representative originals have equal LibreOffice page renders and are pinned
under `test/fixtures/ole_extended/`. Inventories, measurements and render hashes
are recorded in `dev/ole/corpus-napierone-small-inventory.json`,
`dev/ole/qualification-corpus-napierone-small.json`,
`dev/ole/qualification-napierone-doc-small-positive.json` and
`dev/ole/qualification-napierone-doc-small-render.json`. Task 1.2 remains open.
The SHA-256-pinned NapierOne XLS-total scan adds 3,923 byte-distinct XLS files
after content-hash overlap with the small subset: 3,368 pass the host profile,
but none yields supported OfficeArt; the dominant reasons are BIFF records
0x87c, 0x293, 0x1ae and 0x1ba. A separate Gnumeric sample corpus adds 26 more
XLS originals, with no supported OfficeArt graph. These surveys do not justify
loosening unknown-record gates, so the populated-BIFF8 original task remains
open. Their inventories and reports are in `dev/ole/corpus-napierone-xls-total-inventory.json`,
`dev/ole/qualification-corpus-napierone-xls-total.json`,
`dev/ole/corpus-gnumeric-xls-inventory.json` and
`dev/ole/qualification-corpus-gnumeric-xls.json`.
The full NapierOne DOC-total archive adds 486 byte-distinct supported floating
graphs after overlap with DOC-small. All 486 preserve the qualified OfficeArt
interpretation; 406 save 4,731,904 bytes beyond strict compaction. The wider
4,040-file parsed DOC set still has no piece-PRM-owned picture location. Two
high-saving mixed EMF/raster originals now have equal-page render evidence and
are pinned. Their inventory, measurements and page hashes are recorded in
`dev/ole/corpus-napierone-doc-total-inventory.json`,
`dev/ole/qualification-corpus-napierone-doc-total.json`,
`dev/ole/qualification-napierone-doc-total-positive.json` and
`dev/ole/qualification-napierone-doc-total-render.json`. Task 1.2 remains open.
An additional full LibreOffice QA-tree scan pins 480 byte-distinct DOC/XLS/PPT
inputs. It found two more eligible floating-PNG DOCs, but their 6/119-byte stream
gains do not cross a CFB sector boundary; both now exercise the verbose
no-physical-savings diagnostic and render with equal pages. No piece-PRM picture
location or removable OfficeArt duplicate was found in that scan.
An expanded recursive Apache POI module-tree scan outside the root `test-data`
directories found two unique in-range OLE-named objects. The empty PPT fails the
VBA-project host gate; the example XLS is macro-bearing. A provenance review of
xberg-io/test_documents@4139c3b found ten unique locked DOC/XLS/PPT objects but
no per-file mapping from their hashes to source/license records, so none was
imported. Neither source closes the outstanding original piece-PRM or removable-
dedup fixture gaps.
Two xberg-locked DOC candidates were fetched and SHA-256 verified for read-only
analysis. LibreOffice opens and exports both, but both violate MS-CFB's
no-consecutive-red directory rule and are explicitly skipped with that reason.
The corpus's MIT notice excludes third-party document content, and these hashes
have no per-file source/license mapping, so neither binary was retained or
redistributed. This does not justify loosening the structural gate.
MS-DOC UpxChpx forbids style-owned picture/OLE identity and special-character
properties. The former positive style-location control was invalid; it is now a
negative case and its normative correction is in the design/spec. Seven prohibited
style properties and public strict fallback have regression coverage. The positive
character-style control inherits font size while preserving direct picture identity.
