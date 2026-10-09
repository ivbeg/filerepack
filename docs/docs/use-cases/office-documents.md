---
title: "Office documents"
description: "Shrink Word, Excel, PowerPoint, ODF, and iWork files"
---
# Office documents

Modern Office files are ZIP containers. filerepack extracts them, packs nested images
and minifies XML, then rewrites the archive. OOXML-like files prefer Info-ZIP
`zip` when it is on PATH so extra 7-Zip fields do not break Word/Excel.

## Word, Excel, PowerPoint

```bash
filerepack repack contract.docx
filerepack repack workbook.xlsx --dryrun --stats
filerepack repack slides.pptx --progress
```

Needs `7zz` or `7z`. Install `zip` as well for OOXML.

## Legacy Word, Excel and PowerPoint (OLE)

DOC/DOT, BIFF8 XLS/XLT/XLA and PPT/POT/PPS use CFB structured storage. filerepack
rebuilds their allocation tables to reclaim unused sectors and mini-stream holes.
Every live stream byte and logical directory field is compared before publication;
images, application history and embedded objects retain their original payloads.
The same compaction runs on qualified members inside archives.

```bash
pip install 'filerepack[ole]'
# From the project checkout or extracted source distribution, with Rust 1.89+:
cargo install --locked --path tools/ole-compactor
filerepack repack contract.doc --dryrun --stats
filerepack repack workbook.xls
filerepack repack slides.ppt
filerepack repack contract.doc --dryrun --verbose
```

Add Cargo's bin directory to PATH, or set `FILEREPACK_OLE_COMPACTOR` to the
executable's absolute path. Missing writer/reader dependencies leave the input
unchanged with a warning. A compact file may have no reclaimable space.

The default preserves every live stream byte and only reclaims container space.
Enable `--ole-recompress` for the qualified image and HWP stream passes below.
Use `--verbose` for strategy, encoder, payload counts and the reason for an
unchanged result. JSON and bulk results retain the same diagnostic details.
Fewer compressed stream bytes can yield zero physical sector savings.

Some legacy Office files record a nonzero creation FILETIME in the root OLE
storage. Qualified files retain this value exactly, along with the modification
time; it is neither cleared nor treated as a reason to skip compaction. Unsigned
VBA projects can be copied unchanged during strict compaction, while OfficeArt
image recompression still requires a host without macros.

The native helper is optional and built from the checkout/source distribution.
Set `FILEREPACK_OLE_COMPACTOR` to its absolute path if it is absent from PATH.
Windows uses the same variable with the executable's `.exe` suffix.
New nested/path replacement profiles require helper 0.4.0+; old helper capabilities
retain compatible passes or ordinary compaction with an explicit reason.

Strict compaction now also accepts these independently inspected CFB v3 hosts:

| Extension | Qualified profile |
| --- | --- |
| MSG | IPM.Note messages, bounded property/recipient/attachment inventories; protected message classes excluded |
| VSD | Visio binary version 11 with a valid document size/trailer pointer |
| PUB | Publisher 2002 Contents, Quill and Escher structures |
| MPP | Project MPP9 with unprotected Props9 and task/resource/calendar streams |
| MSI | Installer database class, encoded table names and bounded string/summary structure; signatures, transforms and patches excluded |
| HWP | HWP 5.0.1.0–5.0.3.2, qualifying header flags and empty script template; encrypted, distributed, signed and active script files excluded |

All live streams, names/hierarchy, empty objects, CLSIDs, state bits and FILETIMEs
remain exact under strict compaction. Limits remain CFB v3, 128 MiB file/live
streams, 8,192 directory slots and a 120-second root deadline. Isolated byte
parsers also limit an input buffer to one eighth of the memory budget: 32 MiB
with the default 256 MiB budget. CFB v4, arbitrary
OLE applications, OFT/VSS/VST/MPT/MSP/MST/MSM and Works/CAD families remain outside
the allowlist. No macro, embedded object or installer is executed.

### Recompress OfficeArt pictures

```bash
pip install 'filerepack[ole-recompress]'
cargo install --locked --force --path tools/ole-compactor
filerepack repack report.doc --ole-recompress --ultra --dryrun --verbose
filerepack bulk ./documents --include-ext doc,dot,xls,xlt,ppt,pps,hwp --ole-recompress
```

The codec preserves decoded EMF/WMF bytes, both UIDs, display/crop/geometry and
CFB metadata. PNG preserves every non-IDAT chunk and exact samples: filtered
scanlines in the original codec, unfiltered 8-bit samples in the qualified DOC/PPT
refiltering profiles;
CRC, palette/alpha, interlace and sample-size boundaries are checked. Animation,
unknown unsafe chunks and authenticated encodings are excluded. Sequential
8-bit grayscale/three-component JPEG uses optional libjpeg-turbo 3.2.0 `jpegtran`
with all metadata copied, and an independent Huffman/DCT coefficient reader.
Quantization tables, components and APP/COM metadata must match. Progressive,
arithmetic, lossless, CMYK/YCCK and APP11 authentication profiles remain unchanged.
The generic lossy and metadata-stripping options do not weaken OLE contracts.

Qualified host subsets:

- Word: FIB/CLX/FKP/style-resolved inline PICFs, audited piece PRMs and inherited
  formatting. Picture/OLE identity and special-character flags must come from
  direct/piece formatting; forbidden style properties cause a specific skip.
  Mixed Data accepts framed unreferenced PICFs, fully resolved binary fields
  (NilPICFAndBinData), chained HugePapx/TableProps formatting and zero padding.
  Binary bytes, table formatting and padding remain exact; every affected
  external and internal Data offset is relocated and independently compared.
  Audited borders, pagination, revision metadata and conditional table styles
  are supported. Conditional formatting is checked for hidden picture/Data
  references; its original bytes remain exact. Word drawing properties also
  admit scalar protection/shape flags, shape-owned tertiary z-order and empty
  complex fill/line image defaults. Unknown nested properties remain unsupported.
  Static, noninterlaced 8-bit PNGs use the bounded optional oxipng 10.2.0 filter
  selection profile. Exact sample checks include invisible colors, and every
  source non-IDAT chunk is restored. Interlaced/high-depth PNGs retain their
  original filtering and representation. Missing or failed optional encoders
  retain verified original/zlib/Zopfli alternatives. Opaque history stays exact.
  Floating pictures require a completely
  resolved delayed store in the final WordDocument suffix. Unknown Data regions,
  fast-save/history and ambiguous overlapping/shared operand roles cause fallback.
- Excel: audited BIFF8 cells, formulas, rows, SST/CONTINUE/ExtSST and Index/DBCell.
  Cell/formula/string bytes and original SST fragments remain exact. Only explicit
  absolute pointers and drawing fragmentation change. The first drawing-group
  continuation may use a second adjacent MsoDrawingGroup. Worksheet tertiary
  options accept only a single scalar Fill Style Boolean property; their display
  bytes remain exact and tertiary consumers still exclude image deduplication.
  All worksheet drawing records count against the shared root node limit.
  Pivot/chart/macro/control,
  unknown future records and delayed drawing stores remain outside this profile.
- PowerPoint: the audited single-edit live drawing/Pictures graph, including
  notes pages and the notes master. Slide/notes links and shared BStore reference
  counts must agree with all live consumers. Notes, shape properties, themes,
  animation data and master-owned Photoshop objects remain byte-identical.
  Audited round-trip records can retain slide-layout packages, recent drawing
  colors, multi-property tertiary shape tables and bounded PPT9 shape-text runs
  with zero masks or audited null picture-bullet/numbering fields. Composite
  master/slide identities must resolve consistently to their live original master
  and non-overlapping layouts; unknown forms still cause fallback.
  Sound-free checker and fly-from-bottom entrance animations are supported,
  including audited PPT10 checker/visibility timing and linear x/y fly keyframes.
  Font-only PPT10 document defaults require an unambiguous font target.
  Visual animation targets must resolve to unique shapes
  on their containing page; all animation bytes stay exact. Complete identical
  OLE storage wrappers remain separate: sharing their physical persist offsets
  failed independent reader qualification. Verbose output and reports explain
  this skip and inventory duplicate bytes without claiming them as savings.
  PNGs are selected in Pictures order under a conservative root decode reservation;
  unselected BLIPs and JPEGs in the notes-bearing profile stay exact. The existing
  JPEG codec remains available for qualified presentations without notes.
  Static, noninterlaced 8-bit PNGs additionally use optional oxipng 10.2.0 to
  choose better row filters. Exact source metadata is restored, and independent
  sample checks include transparent pixels' hidden colors. Other PNG layouts
  retain the original codec. Missing/unqualified oxipng retains the verified
  original, zlib and Zopfli alternatives and reports the reason.
  Current OLE helper builds accelerate independent row verification through
  `png-unfilter-v1`; rebuild with
  `cargo install --locked --force --path tools/ole-compactor`. Older helpers
  retain Python row checks. The bounded encoder profile uses libdeflate level 9, a one-second local trial ceiling and a final-verification time reserve. Local trial expiry retains verified prior encodings; actual root exhaustion still refuses publication.
  Historical edits, unknown extensions, missing references, aliased entries and
  unreferenced delay-store regions cause fallback. Handout masters are excluded.

Default effort retains original representations, zlib9 and optional pinned Zopfli
0.4.3 with 15 iterations at ≤1 MiB. `--ultra` adds 50 iterations at ≤2 MiB, retaining
all default alternatives. This version 1 mapping initially applies only to
EMF/WMF and PNG; JPEG/PPT wrappers/HWP retain their own mapping. Missing Zopfli
retains original/zlib candidates. Hard decode, memory and deadline limits do not
increase: 64 images and 16 MiB per encoded/decoded image. DOC/XLS retain the
64 MiB aggregate content bound. Sequential DOC/PPT PNG processing reserves five
decode passes per selected sample workload under the existing root decoded-byte
limit, retaining only compact identities between images. Additional pictures
stay unchanged. The whole operation retains its decode, scratch, memory and
deadline limits; oxipng respects the configured tool thread count.

Combined OLE options qualify their independent candidates before picture
encoding, using the verified source already in memory. Encoded streams are
staged and released before native assembly; preservation identities remain for
the final comparison. This avoids redundant whole-file buffers under the default
256 MiB worker limit without increasing operation budgets.
The independently checked final OfficeArt host is bound to source/candidate
SHA-256 digests. Publication verifies those exact file snapshots and retains all
filesystem conflict guards, avoiding redundant full image decoding.

### Embedded files and duplicate images

```bash
filerepack repack report.doc --ole-embedded-recompress --ole-recompress --verbose
filerepack repack workbook.xls --ole-deduplicate-images --verbose
```

Embedded mode resolves DOC ObjectPool or XLS MBD storage references, preserving
class/link/ObjInfo/presentation cache streams. Qualified Package Ole10Native
wrappers retain all non-payload fields; serialized DOC/XLS CFB children use their
own protection/manifest contracts. Direct substorages are reconstructed through
an independently verified root view; only existing descendant streams return to
the parent. Qualified ZIP/OOXML members are recompressed with exact member bytes
and metadata, excluding signatures, encryption, ZIP64, descriptors and unqualified
extra fields. Wrapper names never become filesystem paths. Recursion is bounded
to four child levels and shares root budgets; `--no-deep` disables deeper children.
Inherently ambiguous inherited OLE-object properties remain outside discovery.
`--no-archives` disables ZIP children; `--no-images` disables child image changes.

Deduplication initially covers complete shared XLS/PPT stores. Only identical
whole BLIP bytes and compatible FBSE identity/UID metadata can share an entry.
Every scalar picture/fill/line/print/hidden consumer is resolved, counts and
indices are repaired, and all display bytes remain exact. Unknown/private
consumers reject the pass. Similar pixels, distinct UIDs, inline Word PICFs,
orphans, history and preview deletion are outside the profile.

Strict, image, embedded and deduplication candidates are separately verified;
the smallest complete file wins. Passes are not composed without a union verifier.
Dry-run, output/backup/threshold rules and cancellation use the common transaction.

### HWP compressed streams

`--ole-recompress` also handles already-compressed HWP DocInfo, BodyText/SectionN
and BinData streams selected by DocInfo IDs and compression policy. Raw-DEFLATE
must terminate exactly; the real 5.0.1.7 corpus's eight-byte CRC32/ISIZE trailer is
accepted only when both fields match and is retained exactly. Other suffixes,
concatenated/wrapped streams and uncompressed-mode conversion are excluded.
Decoded bytes, unselected streams, flags, IDs and all metadata remain exact.
HWP encoder version 1 retains original/raw-zlib9 alternatives and can add pinned
Zopfli 0.4.3 with 15 iterations for streams up to 1 MiB. Its zlib wrapper is
validated for header/window/dictionary/checksum, complete termination and exact
decoded bytes before extracting and independently validating the raw frame.
HWP trailers remain exact. Missing Zopfli and larger streams retain the original/
zlib alternatives with diagnostics. `--ultra` does not add HWP iterations.

With qualified DOC PNG filter selection, the supplied `gov.doc` saves 492,544
bytes (10.82%) and `rosspending_fullreport.doc` saves 299,520 bytes (22.21%).
This improves the earlier exact-filtered candidates by 219,136 and 145,408 bytes,
respectively. Both select lossless
image recompression over strict compaction. Independent document preservation
and all 34/48 original/candidate page pixels match; original inputs remain
unchanged. Measurements and source hashes are in
[`qualification-word-png-refilter-2026-10-08.json`](../../../dev/ole/qualification-word-png-refilter-2026-10-08.json).
These documents are local user inputs, not redistributed regression fixtures.

Local public API qualification compares original/compaction/selected sizes and
worker usage on pinned licensed originals and separately labelled controls.
Seventeen DOC/XLS/PPT original/control comparisons produced identical LibreOffice
pages with macro security level 3. Microsoft Office repair behavior, Hancom and
native Linux/Windows execution have not been qualified locally; CI contains the
native platform matrix. These are documented limits, not passed checks.

The notes-bearing PPT qualification additionally compared all 88 slides and 88
notes pages in the three supplied presentations: source and candidate RGB pages
matched exactly in LibreOffice. Whole-file savings were 633,344 / 1,548,288 /
1,447,936 bytes; the largest measured worker peak was 222 MiB, within the default
256 MiB limit. Source hashes, unchanged notes/object spans and exact qualification
scope are recorded in
[`qualification-ppt-notes-runtime.json`](../../../dev/ole/qualification-ppt-notes-runtime.json).

The subsequently qualified PNG refiltering profile improves whole-file savings
on the same inputs to 1,579,520 / 3,531,264 / 2,382,336 bytes, selecting all
18 / 49 / 31 PNGs. All 88 slide and 88 notes RGB pages still match, and every
Photoshop wrapper and notes span remains byte-identical. Default single-operation
times were approximately 61 / 118 / 74 seconds, with peak memory at most 194 MiB.
Exact hashes, resource usage and renderer scope are recorded in
[`qualification-ppt-png-refiltering.json`](../../../dev/ole/qualification-ppt-png-refiltering.json).

### Recompress embedded objects in legacy PowerPoint

The same option also retains the existing embedded DOC/XLS storage-wrapper pass
for the audited PPT profile. Each complete decoded nested CFB remains identical;
its own `ppt-ole` verifier checks persist/edit references and all other content.
Strict compaction, embedded-storage and OfficeArt candidates are independently
verified; the smallest wins. The two stream transformations are not composed.
On the real PPT fixture, compaction gives 40,448 → 37,888 bytes and embedded-storage
Zopfli gives 37,376 bytes, so the existing pass wins over OfficeArt.
