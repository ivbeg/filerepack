# OLE optimization portfolio — 2026-10-05

The seven proposals are approved and their bounded runtime profiles are
implemented. This report distinguishes implemented code/local evidence from missing
fixture/application/platform qualification; approval alone is not delivery.
The original byte-exact `ole` contract and the PPT wrapper's byte-exact decoded
CFB contract are unchanged. New modes have their own intended-change verifiers.

## Implemented profiles and reference matrix

| Proposal | Implemented runtime |
| --- | --- |
| Expanded DOC/XLS | BIFF8 cells/numbers/formulas/rows, SST+CONTINUE rich/extended/encoding transitions, ExtSST string starts, BoundSheet BOF, Index XF/DBCell targets and DBCell Row/cell relative targets. One adjacent second MsoDrawingGroup may replace the first Continue; subsequent fragments are Continue. Worksheet tertiary options accept only version3/instance1/six-byte scalar fill-boolean property01BF, fBid/fComplex clear. Non-drawing and worksheet display bytes stay exact. DOC FIB/CLX PRM0/PRM1, styles/based-on chains/CIstd, paragraph/character FKPs and exact operand provenance; mixed framed PICFs/zero gaps retained, qualified final floating delayed suffix. |
| PNG/JPEG | PNG exact filtered scanlines/non-IDAT chunks with CRC/size/color/interlace gates; sequential Huffman 8-bit gray/three-component JPEG exact quantized DCT coefficients, quantization/frame/APP/COM identity. jpegtran libjpeg-turbo 3.2.0 only, `-copy all -optimize`; no progressive/arithmetic/lossless/CMYK/YCCK/APP11. One/two UID BLIPs retain UID/tag/display fields. |
| Embedded children | DOC ObjectPool/_decimal and BIFF8 MBD8hex targets; Package class/CompObj/Ole10Native/link validation; serialized DOC/XLS CFB and direct reconstructed substorages; exact ZIP/OOXML member/metadata identity, no ZIP64/descriptors/signatures/encryption/unqualified extras. CFB root-view creation time zero, outer storage metadata never imported. Recursive children bounded to four levels with ancestor/alias and cumulative root checks. |
| Image deduplication | Shared embedded XLS and delayed PPT stores, exact BLIP bytes+FBSE identity/UID compatibility. Scalar MS-ODRAW picture/print/fill/line/border image properties `104/10F/186/1C5/545/585/5C5/605`, all nested/hidden consumers, exact counts. Stable first-entry retention, index/length/delay/persist/current-user repairs, no orphan/history removal. |
| More OLE hosts | Strict MSG IPM.Note, VSD 11, Publisher 2002, MPP9, MSI database and HWP 5.0.1.0–5.0.3.2. Independent original/candidate logical manifests include every exact name, empty object, CLSID/state/FILETIME and stream. Host-specific protection/structure gates precede writing. |
| HWP streams | Already-compressed DocInfo/BodyText/SectionN; BinData embedding IDs and compression flags resolve selected streams. Raw-DEFLATE plus either no suffix or exactly validated eight-byte CRC32/ISIZE trailer, retained exactly. Encoder version 1: original/raw-zlib9 and optional Zopfli0.4.3/15 at ≤1 MiB. The binding's RFC1950 header/window/dictionary/checksum/termination and exact decoded bytes are checked before extracting and separately verifying the RFC1951 body. HWP trailers stay exact; ultra does not add HWP trials. Unknown suffix/wrapper/concatenation fails. All decoded bytes, flags/IDs/unselected streams/metadata exact. |
| Maximum effort | Version 1: original/zlib9 plus optional pinned Zopfli0.4.3/15 at ≤1 MiB; ultra retains those and adds 50 at ≤2 MiB. EMF/WMF/PNG only. Each trial is decoded/verified; original/default alternatives cannot be displaced by a larger trial. Hard limits and transformation activation remain unchanged. |

Content passes are independently built from the source. Strict, image, recursive
child and dedup alternatives compete by final CFB size; no unverified union of
root transformations is written. Category options remain effective, including
`pack_images`, `pack_archives` and `deep`; generic lossy/metadata-stripping choices
do not weaken the OLE contracts. Existing members inside outer archives use the
same options, publication and root-budget policy.

CFB v4, older Word/BIFF, arbitrary OLE, OFT/VSS/VST/MPT/MSP/MST/MSM, Works/CAD,
DIB/TIFF/PICT transforms, signed/encrypted/rights-managed inputs, VBA rewriting,
application resaving/conversion, unknown Data islands, unqualified OfficeArt
consumers, dedup of similar pixels/distinct UIDs and history/preview removal are
excluded. Word embedded-object discovery currently rejects inherited object
properties even though image discovery resolves audited inheritance. JPEG accepts
one complete sequential scan; optional encoders cannot silently widen that gate.

## Native and resource contracts

`filerepack-ole` 0.4.0 uses pinned `cfb`0.14.0 and Cargo.lock, independent Python
reader `olefile`0.47. Qualified replacement plans are ≤1 MiB/8,192 unique existing
paths within fixed host scopes. Child extraction compares a root view with every
original descendant before any optimization. Full-path matching prevents an
identically named nested stream being mistaken for a root stream.

File/live stream limit128 MiB, 8,192 directory slots; image count64, per image16
MiB and aggregate64 MiB. Root decoded512 MiB, RSS256 MiB, scratch2 GiB, nodes100k,
120 seconds by default. Worker/native subprocess usage, verification and all
recursive children share the root budget; exhaustion leaves the source intact.
Isolated byte parsers additionally cap each input buffer at one eighth of the
memory budget (32 MiB by default), below the 128 MiB CFB hard ceiling. Increasing
the memory option can raise that buffer ceiling but never the CFB hard limit.
New strict host passes also use isolated accounting. Generated filenames, not
wrapper names, own staging files. Macros, scripts, OLE objects and MSI never run.
Worksheet drawing records, including shapes without image payloads, count against
the cumulative root node limit along with BIFF and global OfficeArt records.

## Local measured evidence

Reproduce from the checkout:

```sh
FILEREPACK_OLE_COMPACTOR="$PWD/venv/bin/filerepack-ole" \
  venv/bin/python -m dev.ole.qualify_portfolio \
  --writer venv/bin/filerepack-ole --render \
  --output dev/ole/qualification-portfolio.json
FILEREPACK_OLE_COMPACTOR="$PWD/venv/bin/filerepack-ole" \
  venv/bin/python -m pytest test/test_ole*.py -q
cargo test --locked --manifest-path tools/ole-compactor/Cargo.toml
cargo clippy --locked --manifest-path tools/ole-compactor/Cargo.toml -- -D warnings
venv/bin/ruff check filerepack/ole*.py test/test_ole*.py test/ole_fixtures.py \
  dev/ole/survey_corpus.py dev/ole/qualify_portfolio.py
venv/bin/mypy filerepack/ole*.py --ignore-missing-imports --follow-imports=silent
```

`qualification-portfolio.json` records SHA-256, original/compaction/selected byte
sizes, wall time, worker peak RSS/root usage, chosen verifier, per-pass/per-object
skips and page hashes. The corpus is pinned by the fixture provenance manifests.
Originals and synthetic weak-encoding/duplicate/populated/font-style/wrapped
controls are separately labelled. The latter establish behavior, not typical
compression estimates. Source bytes remain unchanged under distinct-output runs.

Examples in bytes, selected only after complete independent preservation checks:

| Case | Source | Strict compaction | Selected |
| --- | ---: | ---: | ---: |
| Original embedded DOC |117248|117248|116224|
| Original mixed-image XLS |48128|48128|47104|
| Original two-object PPT |40448|37888|37376|
| Original MSG attachment fixture |52224|51200|51200|
| Original Visio 11 |45568|44544|44544|
| Original Publisher 2002 |72192|72192|72192|
| Original MPP9 |77824|77824|77824|
| Original MSI database |15360|14336|14336|
| Original HWP 5.0.1.7 (strict) |216576|203776|203776|
| Original HWP with compressed PNG/JPEG BinData |40448|30208|29696|
| Original HWP with two body sections |14848|7680|7680|
| Control weak HWP streams |213504|213504|203776|
| Control repeated XLS BLIP |59392|59392|47104|
| Control repeated PPT BLIP |36864|36864|36352|
| Control DOC Package ZIP |129024|129024|102912|
| Original LibreOffice JPEG DOC |27648|27648|27136|
| Original LibreOffice transparent-page PNG DOC |78336|78336|77312|
| Original LibreOffice paragraph-positioned PNG DOC |72704|72704|70144|
| Original LibreOffice character-positioned PNG DOC |73216|73216|70656|
| Original LibreOffice PNG XLS |49152|49152|45568|
| Original LibreOffice floating PNG DOC (fdo66692-2.doc) |91136|91136|91136|
| Original LibreOffice floating PNG DOC (tdf131707_flyWrap.doc) |41472|41472|41472|
| Original NPOI mixed eight-image DOC |4835840|4835840|4810240|
| Original Apache Tika PNG DOC |448000|448000|430592|

Original floating PNG DOC yields76 fewer stream bytes with optional Zopfli, but
still14336 physical bytes: the smaller allocation is not asserted when no sector
is saved. Maximum effort on the measured originals did not beat the default's
physical size; it takes longer (raw timings/RSS are in JSON). Missing tools retain
original/zlib alternatives with an explicit reason.
The three original HWP recompression runs saved 505, 455 and 101 stream bytes
respectively. The compressed PNG/JPEG BinData sample saved 512 physical bytes
beyond compaction with qualified optional Zopfli15; the other two originals
fit their existing sectors. The weak-encoding HWP control is measured separately.

Four additional unchanged originals (`28774.xls`, `29675.xls`, `two_images.doc`,
`58804_1.doc`) now have complete public API preservation and matching pages.
They retain their original physical sizes. The populated `28774.xls` qualifies
four raster payloads and saves62 stream bytes with optional Zopfli15, which still
fit the same sectors. The controlled populated workbook using an adjacent second
MsoDrawingGroup shrinks60928→47104 bytes, with formulas/cells and all reference
targets preserved. It is an encoding control, not an original compression ratio.

Seven unchanged LibreOffice originals add measured floating PNG/JPEG/WMF DOC
layouts and a PNG worksheet. Five save additional file sectors, as listed above.
`tdf104596_wrapInHeaderTable.doc` saves13 stream bytes and stays29184 physical
bytes. `tdf79553_lineNumbers.doc` saves25 stream bytes; strict compaction already
shrinks77312→74752 bytes, so its recompressed candidate cannot improve the final
size. The five positive stream savings are513/1041/2626/2626/3872 bytes,
respectively; stream savings and final sector savings are recorded independently.

Two byte-distinct NPOI originals add a shared WMF and a large eight-image Word
store. The shared WMF saves397 stream bytes but no physical sectors. The mixed
PNG/JPEG store saves25,676 stream bytes and25,600 file bytes beyond compaction;
seven eligible images are re-encoded and one PNG with an unqualified critical
chunk stays byte-identical. Both originals have complete independent manifests
and equal rendered pages. Their fixture Git blob identities differ from the
previous POI corpus even when the upstream basename matches.

One supplemental Apache Tika original adds a large PNG raster in a Word file.
Its unchanged 448,000-byte source reencodes one image, saves17,289 stream bytes
and17,408 physical bytes, and renders to the same two pages. It is pinned
separately from the 1,055-file POI/LibreOffice/NPOI census.

A supplemental full-tree LibreOffice audit added 480 byte-distinct originals.
Two floating-PNG DOCs passed exact OfficeArt preservation and same-page render
checks. Their image streams shrink by 6 and 119 bytes, but both fit the same
512-byte sectors as strict compaction, so verbose output reports why the final
file remains unchanged. The portfolio now contains 44 cases and 34 identical
rendered-page comparisons. They are diagnostic/preservation cases, not storage
reduction claims. The same audit parsed 47 more Word piece tables and found no
piece-PRM picture-location property; there were no additional qualified XLS/PPT
OfficeArt or dedup candidates.

MS-DOC UpxChpx forbids properties preserved by sprmCIstd, including picture/OLE
identity and special-character flags. The former positive synthetic style-owned
picture location was invalid. It now has rejection/fallback coverage; the positive
style control inherits font size and retains direct picture identity. Three real
inline originals explicitly verify inherited font properties and exact style bytes.
Piece-PRM locations retain a separate qualified direct-formatting profile.

LibreOfficeDev26.8.0.0.alpha0 commit
`2c87e51eeaa2b413ff4ae097b2705eea1995d8e5`, 96 dpi, isolated profiles and macro
security level3 compare source/candidate pages. The final portfolio contains
44 cases and 34 identical page comparisons. Renderer agreement supplements
exact manifests/coefficient checks; it is never used to authorize arbitrary
resaving or payload changes. Applications for MSG/VSD/PUB/MPP/MSI/HWP are not run;
strict stream manifests are their local acceptance evidence.

## Completed local validation

- Final expanded OLE suite: 545 passed.
- Fresh wheel installed outside the checkout: 817 passed / 182 skipped in its
  focused installed regression suite. Fresh sdist installed outside the
  checkout: 1,800 passed / 316 skipped in the complete source test suite.
  Collection, package metadata/licenses, public imports and both CLI entry points
  were checked in isolated environments. Fixture/license files are present in
  source releases and excluded from runtime wheels.
- Targeted OLE Ruff and whole-project mypy checks passed. A whole-project Ruff
  rerun reports C901 in the unrelated `filerepack/car.py` file. No unrelated
  NIB/WARC files were modified during this OLE expansion.
  The new mypy2.3.1 additionally warns that the configured Python3.9 target is no
  longer supported by that checker. Runtime Python3.9 compatibility is unchanged.
  Rust formatting, locked native unit tests and Clippy with warnings denied passed
  in the preceding implementation run; native code is unchanged by this expansion.
- Documentation production build and strict validation of all seven OpenSpec
  changes passed. The 44 public API measurements and 34 identical rendered-page
  comparisons were regenerated with the final host/codec/budget implementation.
- The 1,055-file census completed with every pinned length/Git blob/SHA-256
  verified, no unavailable sources and complete stage/rejection records. The
  supplemental 480-file LibreOffice QA-tree inventory is also hash-pinned and
  fully surveyed.

## Qualification limits and OpenSpec status

Native local execution is macOS arm64 only. The CI matrix includes Linux,
macOS and Windows/Python3.9+3.13 with all new OLE tests, but its remote executions
are not claimed as locally passed. Microsoft Office repair/open behavior and
Hancom Office rendering are unavailable. There is no automatic external activation.

Real originals cover PNG/JPEG, DOC/XLS/PPT, all six new hosts and multi-section/
BinData HWP. Some newly supported Word inheritance/mixed boundaries and populated
BIFF pointer/continuation combinations are controlled derivatives of real
licensed fixtures. The [original corpus census](CORPUS.md) verifies identities
and reports exact per-file reasons for1,055 pinned DOC/XLS/PPT sources:21 qualify
OfficeArt payloads, four qualify deduplication graphs and none of those four
has removable entries. An additional real populated SST/LabelSst worksheet is
qualified; original piece-PRM-owned Word picture-location operands and richer formula/row/continued-string and
duplicate-store combinations remain acquisition tasks. `WithEmbeddedObjects.xls` has
unsupported root creation metadata: its real MBD/Obj class reference stream is
checked separately, and full publication stays rejected. Newly sampled
DrawingContinue/FloatingPictures and modern FRT layouts remain outside the gate.

Tasks whose local implementation/evidence are complete are recorded in the seven
change directories. Corpus-specific qualification still missing stays unchecked;
no change is archived or declared deployed solely because its implementation
exists. Further original-corpus expansion must pass the same graph/application
checks before widening a profile.

## Primary source and licensing references

- [MS-XLS RRTabId](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/e1b235b2-c955-4d38-b7ad-fab84d93d4bc), [drawing group](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/43e0d496-45db-4f19-bb33-bcb2464aa83c), [Index](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/b06ea609-4ba2-4dab-9978-14e3b034706a), [ExtSST](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/5d981e62-9e25-490a-9a75-b177373e2d79).
- [MS-XLS continuation product behavior](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/a3ad4e36-ab66-426c-ba91-b84433312068), [MS-ODRAW tertiary options](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/a687e90c-1748-4f57-8758-be31cfb36185), [scalar Fill Style Boolean Properties](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/baf2613d-c676-43c8-8077-828bdcc70dca).
- [MS-DOC OfficeArtContent](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/8699a984-3718-44be-adae-08b05827f8b3), [Prm0](https://learn.microsoft.com/es-es/openspecs/office_file_formats/ms-doc/35226a0b-9038-4427-83c2-3830a8554267).
- [MS-XLS embedded object storage](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/b406ade0-fb1c-4512-bff2-b576fdfff545), [PictFmlaEmbedInfo](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/8a89203c-a866-4695-b7da-1e659cb3f235), [MS-OLEDS CompObj](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-oleds/142e0420-2f74-4ed9-829b-0b3d5a684d01).
- [MS-ODRAW BLIP reference families](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/9e1f4117-1431-48c1-9f2e-50091f773c3a), [MS-OXMSG](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxmsg/1a69e000-f391-4c03-9d43-32d5f554bca7), [MSI signatures](https://learn.microsoft.com/en-us/windows/win32/msi/msidigitalsignature-table).
- [Hancom parsing guidance](https://tech.hancom.com/python-hwp-parsing-1/), [HWP5 revision1.3](https://cdn.hancom.com/link/docs/%ED%95%9C%EA%B8%80%EB%AC%B8%EC%84%9C%ED%8C%8C%EC%9D%BC%ED%98%95%EC%8B%9D_5.0_revision1.3.pdf). The accepted eight-byte trailer is separately verified corpus evidence, not a license to ignore trailing data.
- [RFC1950 framing](https://www.rfc-editor.org/rfc/rfc1950.html) governs the optional HWP binding adapter; exact raw-frame and decoded-byte checks are additional project acceptance rules.

Fixtures: Apache POI/Apache-2.0, Apache Tika/Apache-2.0, pyhwp/AGPL-3.0 test data
and WiX3/MS-RL, with source commit URLs, hashes and license texts in
`test/fixtures/ole_extended`.
The nine LibreOffice fixtures carry the pinned core commit and MPL-2.0 license.
Two NPOI fixtures carry commit832eb28f142d54fb8a87b65fa61b5916a763b528 and Apache-2.0.
The Tika original and its `LICENSE.txt`/`NOTICE.txt` come from commit
`de6af231dcb721856b719966bc010f909358319c`.
No pyhwp or LibreOffice implementation is imported. cfb/native dependencies are covered by
`tools/ole-compactor/THIRD_PARTY_LICENSES.md`. Runtime optional Zopfli0.4.3 is
Apache-2.0; external libjpeg-turbo3.2.0 has IJG/BSD-3-Clause/Zlib licensing and is
not bundled in wheels. The bounded Python coefficient reader is project code.
