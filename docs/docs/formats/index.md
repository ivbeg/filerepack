---
title: "Supported formats"
description: "Format coverage, nested walking, and per-format tools"
slug: /formats
---

# Supported formats

filerepack identifies files by extension (including compound names such as
`archive.tar.gz` and `archive.tar.gzip`). Nested members inside archives are
walked with the same rules. Missing optional tools or Python extras leave the file unchanged. Candidate
publication also requires its structural validator: raster decoding needs
Pillow, media needs ffmpeg/ffprobe, and scientific profiles need the optional readers
and encoders listed in their profile documentation. See [Safety](/getting-started/safety).

JPEG, PNG, and PDF default to **lossless** tools. Use `--lossy`,
`--jpeg-quality`, `--png-quality`, or `--pdf-profile` for lossy codecs. Output
that is not smaller than the original is discarded unless `--allow-grow`.

CLI: [CLI reference](/commands/). Tools: [External tools](/tools/). Library:
[Python API](/library/).

The generated [capability registry](/formats/capabilities) describes registered
adapter metadata, which can group profiles and omit backend prerequisites. Its
SPSS family entry groups SAV with experimental ZSAV; SAV itself does not require
`--experimental-formats`. Use the per-format guides below and the installation
extra list for precise compatibility and dependency requirements.

## Nested walking

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten:

1. **ZIP family** (OOXML, ODF, EPUB, JAR, APK, …) — extract, pack members, rewrite as ZIP. OOXML-like files prefer Info-ZIP `zip` when it is on PATH so extra 7-Zip fields do not break Word/Excel.
2. **7z / RAR / WIM** — same walk; RAR is rewritten as 7z when `rar` is missing. CAB is recognized but has no qualified writer.
3. **Tarballs** (`tar`, `tar.gz` / `tgz`, `tar.bz2`, `tar.xz`, `tar.zst`, `tar.br`, `tar.lz4`, `tar.lzo`, `tar.lz`, `tar.lzma`, `tar.Z` / `taz`, plus `crate` / `unitypackage`) — decode the outer stream, extract tar members, pack eligible files, rebuild one tar, then encode the original outer codec. `--no-deep` skips member optimization while retaining the same tar layout. RubyGems `.gem` files are plain tar; their checksummed nested payloads remain unchanged during outer rewriting. A compressed stream whose payload is a tar (`.gz`, `.zst`, …) is detected by peeking the first 512 decompressed bytes.
4. **Nested XML / JSON** inside those containers is minified (see [Markup](#markup-xml-json-svg)).
5. **`--no-archives`** skips nested archive rewriting. **`--no-images`** skips image, video, and audio packers (including cover art), not XML/JSON or PDF.
6. **CPIO** (`cpio`, `cpbz2`, `cpio.bz2`) — native record-aware rewriting of safe regular single-link members; linked/special entries retain their original bytes. See [CPIO usage](/use-cases/archives#cpio-and-bzip2-compressed-cpio).

`--include-ext tar.gz` matches `foo.tar.gz`. `--include-ext gz` matches it too.
`--include-ext jpg` matches `.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.jif`, `.jfi`,
and `.thm`.

Archive publication checks the complete intended member set, entry types and
decoded payload hashes. Hidden files and empty directories are included, and
literal member names cannot become writer options or wildcard expressions.
ZIP rewrites preserve entry order, timestamps, attributes, extra fields and
comments; restoring this metadata adds a streaming rewrite of the candidate.
Tar rewrites preserve supported ownership, permissions, timestamps and PAX
metadata. Generic-tool archives also need their listed metadata to round-trip.
Verification adds read/decoding work before size acceptance.

Duplicate names, case/Unicode-normalization collisions, unsafe paths, links,
sparse files, encrypted ZIP members, prepended ZIP wrappers and unsupported metadata/type round-trips
leave the archive unchanged with a warning. These member checks do not establish
application-specific signature, checksum or package-layout validity; specialized
container policies have their own checks below, and broader alias policies remain
open qualification work. CPIO separately preserves supported linked/special
entries without materializing them.

## Nested assets (not ZIP)

These run on the host file even when it is not an archive:

| Host | Extra / tool | What is packed |
|------|----------------|----------------|
| MP3, FLAC, M4A/M4B/MP4, Ogg, APE | `filerepack[media]` (mutagen) | Attached cover pictures, then the usual codec packer |
| XML / SVG | none | `data:image/…;base64` URIs decoded, packed, written back compact |
| PDF (lossless) | `filerepack[pdf]` (pikepdf) | JPEG/JPX and supported Flate images, recursively through Form resources; compare qpdf alternatives |

If the extra is missing, or nothing shrinks, the host is left unchanged
(codec-only packers may still run). Encrypted or digitally signed PDFs skip
all rewriting paths, including qpdf and Ghostscript. `--lossy` / `--pdf-profile` /
`--jpeg-quality` skip pikepdf and use Ghostscript instead.

## Office and ZIP-family archives

### Legacy Office OLE compaction

`doc`, `dot`, `xls`, `xlt`, `xla`, `ppt`, `pot`, `pps`, `msg`, `vsd`, `pub`,
`mpp`, `msi`, `hwp` use a separate CFB v3
handler, requiring `filerepack[ole]` (`olefile 0.47`) and the optional
`filerepack-ole` writer (`cfb 0.14.0`). Install the native tool as described in
[Office documents](/use-cases/office-documents/#legacy-word-excel-and-powerpoint-ole).
The Office FIB/BIFF8/edit-persist profile must match the extension.

The writer preserves all logical streams, exact names/hierarchy, empty storages
and streams, CLSIDs, state bits and raw FILETIMEs. Independent allocation and
directory validation plus a second reader compare every object before the shared
size/dry-run/publication policy runs. Free-sector remnants can disappear; live
stream history, pictures and embedded document bytes stay unchanged.

Canonical unsigned DOC/DOT `Macros` and XLS/XLT/XLA `_VBA_PROJECT_CUR` projects
are preserved as opaque streams, including code, caches and editor-lock metadata.
Required project headers and host signature locations are checked: DOC's
FIB-addressed StwUser names (`Sign`, `SigAgile`, `SigV3`) and the complete
DocumentSummaryInformation property index (`GKPIDDSI_DIGSIG`, ID `0x18`).
Property values and VBA code are not decoded or executed. Unknown property
sections, incomplete indices and non-simple property storages cause a skip.

PPT/POT/PPS VBA support requires a single user edit and one canonical VBAInfoContainer
under the current document's DocInfoList, with a unique persist reference to a
top-level project. Compressed RFC1950 and uncompressed CFB storage wrappers are
supported; both encoded and decoded project bytes are limited to 16 MiB. Exact
declared length, checksum, end of stream and absence of trailing data are checked.
The nested CFB is independently inspected for structure, protection and the
canonical root PROJECT/VBA layout. The original encoded record stays unchanged.
Multiple edits with VBA, empty/unknown flags, duplicate IDs/ambiguous references
and malformed wrappers cause a skip. Macro-free PPT retains edit-history support.

CFB v4, signed/encrypted/rights-managed files, unknown/embedded/incomplete or
history-dependent VBA layouts, unclassified and malformed files skip with a reason. The bounded
subset accepts minor versions 0x3B/0x3E, BMP names whose uppercase mappings do
not expand, recorded root creation/modification times and
storage entries with zero stream allocation fields. Observed nonzero root creation
FILETIMEs are preserved exactly. Other Unicode/root/storage
variants remain unsupported. Limits: 128 MiB file/aggregate stream bytes, 8,192
directory slots, 32 storage levels, 128 traversal levels, 200,000 application
records, 4,096 PPT edits and a 120-second writer timeout. Each inspected property
stream or StwUser table is limited to 4 MiB and 4,096 properties or user variables.

Real DOC/XLS/PPT fixtures and controlled holes are covered by native tests.
Local rendering was checked with a pinned LibreOffice build; Microsoft Office
and Linux/Windows application rendering are not locally qualified. Native CI
jobs cover Linux/macOS/Windows. Savings depend on unused allocations and may be zero.

### Legacy Office payload recompression

`--ole-recompress` enables qualified DOC/XLS/PPT OfficeArt EMF/WMF, PNG and
sequential JPEG encoding, PPT storage wrappers and HWP compressed streams.
`--ole-embedded-recompress` handles audited DOC/XLS Package files/direct CFB
children; `--ole-deduplicate-images` handles byte-identical shared XLS/PPT images.
All three options default to off. Native helper 0.4.0+ and the `ole-recompress`
extra support the new profiles. JPEG entropy optimization optionally requires
libjpeg-turbo 3.2.0 `jpegtran`; unknown versions leave JPEG unchanged.

Expanded host adapters retain populated BIFF8 cells/formulas/SST and audited Word
piece/style properties, mixed PICFs and final delayed pictures. Unknown layouts
retain verified compaction. Exact decoded bytes/coefficients, metadata and
normalized graph identities are compared by separate `officeart`, `ppt-ole`,
`hwp-ole`, `ole-embedded` and `ole-dedup` verifiers; strict `ole` remains byte-exact.
Root budgets and a 120-second deadline apply. `--ultra` retains default candidates
and adds bounded Zopfli50 trials at ≤2 MiB to eligible EMF/WMF/PNG only.
A stream reduction must improve the selected physical file to be accepted.
See [profiles, exclusions and measurements](/use-cases/office-documents/#recompress-officeart-pictures).

### Modern Office ZIP containers

Needs `7zz` or `7z`. OOXML also benefits from `zip`.

| Group | Extensions |
|-------|------------|
| Microsoft OOXML | `docx`, `docm`, `dotx`, `dotm`, `xlsx`, `xlsm`, `xltx`, `xltm`, `xlsb`, `xlam`, `pptx`, `pptm`, `ppsx`, `ppsm`, `potx`, `potm`, `ppam`, `sldx`, `sldm`, `thmx`, `vsdx`, `vsdm`, `vstx`, `vstm`, `vssx`, `vssm`, `accdt`, `crtx`, `gcsx`, `glox`, `gqsx`, `vdw`, `zipx`, `xps`, `oxps`, `dwfx` |
| OpenDocument / OpenOffice | `odt`, `ods`, `odp`, `odg`, `odf`, `odb`, `odc`, `odi`, `odm`, `ott`, `ots`, `otp`, `otg`, `oth`, `otm`, `otc`, `oti`, `sxw`, `sxc`, `sxi`, `sxd`, `sxg`, `sxm`, `stw`, `stc`, `sti`, `std` |
| Apple iWork | `pages`, `key`, `numbers`, `kth`, `nmbtemplate`, `template` |
| E-books / packages | `epub`, `lpf`, `ibooks`, `oxt` |
| App / language packages | `jar`, `egg`, `whl`, `war`, `ear`, `aar`, `apk`, `aab`, `xapk`, `apks`, `ipa`, `appx`, `msix`, `appxbundle`, `nupkg`, `snupkg`, `vsix`, `xpi`, `crx`, `npz` |
| Design / comics / other ZIP | `zip`, `xmind`, `idml`, `sketch`, `kra`, `ora`, `xd`, `afpub`, `afphoto`, `afdesign`, `scrivx`, `cbz`, `kmz`, `3mf`, `usdz`, `ifczip`, `fcstd`, `mxl`, `rtb`, `onepkg`, `wgt`, `air`, `pk3`, `xap`, `ipsw`, `osk`, `oex`, `puz`, `rmskin`, `notebook`, `nbk`, `mcworld`, `mcpack`, `mcaddon` |
| QGIS | `qgz` |
| Mellel | `mellel` |

`.otf` is packed as ODF only when the file is a ZIP (OpenType fonts are skipped).

Other archive families:

| Family | Extensions | Notes |
|--------|------------|--------|
| 7z | `7z`, `cb7` | |
| RAR | `rar`, `cbr` | Rewritten as `.7z` if `rar` is missing |
| WIM | `wim` | Requires a working backend writer and successful member/metadata verification; otherwise unchanged |
| CAB | `cab` | Recognized, but no qualified writer; unchanged |
| Tar | `tar`, `cbt`, `tgz`, `taz`, `tbz`, `tbz2`, `txz`, `tzst`, `tlz`, `tzo`, `gem`, `crate`, `unitypackage` | `gem` is plain tar, `crate`/`unitypackage` are gzip-wrapped tar, `taz` uses Unix compress; checksummed gem payloads are not walked |
| CPIO | `cpio`, `cpbz2`, `cpio.bz2` | Native old-binary/odc/newc/CRC-newc profiles; compressed shallow mode preserves exact decoded CPIO bytes |

### ODF and EPUB package rules

ODF and EPUB require `mimetype` as the first physical ZIP entry, stored without
compression or an extra field. The writer enforces that layout independently of
the archive backend. ODF manifests must agree with the MIME type and reference
existing members; EPUB container rootfiles, publication manifests and spine
references must resolve inside the package. Package control files (`mimetype`,
`META-INF/*` and EPUB publication documents) retain their original bytes during
nested walking and are compared again before publication.

Signed, encrypted, rights-managed, malformed or unsupported packages are skipped
before extraction. ODF checksums/unknown manifest records, external EPUB resource
references and control files larger than 4 MiB are unsupported. This is a
preservation gate for the supported package structure, not a complete ODF/EPUB
conformance or application-rendering validator. Other ZIP aliases retain their
existing policies and still need individual audits.

### QGIS package rules

QGZ requires exactly one root-level `.qgs` project and, when present, an auxiliary
`.qgd` with the same basename. The project uses the QGS XML policy below. A
nonempty QGD must be a supported, valid SQLite database; an empty auxiliary
payload is retained. Project XML inside QGZ is limited to 4 MiB. Deep walking can compact the project and vacuum the
auxiliary database, comparing its schema, rows, rowids and application metadata.
All unrelated members retain their original bytes and names. `--no-deep`
recompresses the ZIP without editing member payloads. Invalid project/auxiliary
structure skips the package before extraction.

### Mellel package rules

Mellel requires a valid `main.xml` with the Mellel archive creator and version
attributes, and existing resources for its image-data references. Every internal
file, including document XML, images and unknown assets, retains its exact bytes.
Only the ZIP compression changes. Control XML is limited to 4 MiB; the usual
archive manifest, metadata and extraction limits apply. This checks preservation
of the supported package structure; opening/rendering in Mellel is not verified.

## Interface Builder NIB

| Kind | Extensions | Behaviour |
|------|------------|-----------|
| Compiled Interface Builder archive | `nib` | Share identical stored value sequences; preserve every object, reference, property and class fallback. Python only |

```bash
filerepack repack View.nib
filerepack bulk ./resources --include-ext nib
```

The supported profile is `NIBArchive` format version 1, coder version 9 or 10,
with complete contiguous object/key/value/class tables and documented value
types 0–10. The coder version, object identities, cyclic/shared references,
duplicate keys, property order, opaque bytes, integer/float bit patterns, class
fallback indexes and unused records are retained. A separate parser compares
source/candidate preservation before publication; archived classes are never
instantiated. `--no-images` does not skip this document format.

Keyed-plist nibs, nib directory bundles, other versions, malformed records and
unparsed trailing data are skipped. This includes coder-10 files with an
undocumented trailer. `.nib` members inside archives use the same policy during
deep walking. Dry-run inspects without encoding or predicting savings. Backup
and minimum-savings rules apply; a distinct output is created only for an
accepted smaller candidate. Already compact archives remain unchanged.

Parsing, value visits and verification share the root `--format-max-*` budgets
and cooperative deadline/cancellation checks. At the default 256 MiB memory
budget, byte input is limited to 32 MiB with a further record/buffer estimate;
the default cumulative record/value-visit budget is 100,000. The absolute byte
profile is capped at 256 MiB even when memory limits are increased.

Local qualification covered 41 real AppKit coder-10 files and an independently
published ibtool coder-9 sample. AppKit `NSNib` construction was checked without
instantiation. UI rendering and UIKit loading have not been verified. Optimize
application resources before code signing.

## Compiled Apple asset catalog CAR

| Kind | Extension | Behaviour |
|------|-----------|-----------|
| CoreUI asset catalog | `car` | Lossless DEFLATE MLEC/CELM recompression and BOMStore block/index compaction |

The qualified profile supports Apple BOMStore v1 with CARHEADER storage versions
8–17, KEYFORMAT v0 and CSI v1. It retains every live block ID, rendition key,
variant, name, TLV, tree page and unknown block. Known version 0 single-stream
and version 1 KCBC-banded codec-2 resources are recompressed as zlib/gzip while
preserving their decoded bytes and envelope metadata. LZFSE, LZVN, Deepmap,
palette, ASTC, raw payloads and unrecognized codecs are retained exactly.

The writer removes only free allocations, zero padding and unused trailing block
index slots; it retains block order, per-block 16-byte alignment, complete padded
tree pages and every occupied index ID. It rejects malformed or overlapping
allocations, invalid BOM tree references, unsupported versions or framing,
corrupt compression, unclassified nonzero gaps and catalogs outside the bounded
profile. It does not thin asset variants or rebuild from `.xcassets`. Structural
and decoded-byte checks run before standard size, dry-run, backup and destination
policies. A catalog that is already compact or uses only opaque compression may
remain the same size.
Dry-run inspects without encoding or predicting savings. A distinct CAR output
is created only for an accepted smaller candidate.

Native assetutil qualification used six temporary copies of installed catalogs:
all 975 rendition descriptions and 953 allocated CSI block digests matched.
Five catalogs passed native validation before and after; SSHProxy retained its
pre-existing native validation failure. This is local macOS evidence for these
catalogs, with [measurements](/development/quality-evidence), rather than a
claim about all private CoreUI versions.

```sh
filerepack repack Assets.car
filerepack bulk ./MyApp.app --include-ext car
```

`.car` members inside app bundles use the same policy during ZIP-family deep
walking. Rewriting application resources changes bundle contents and invalidates
code signatures; re-sign the bundle after modifying its assets.

## Markup (XML, JSON, SVG)

| Kind | Extensions | Behaviour |
|------|------------|-----------|
| JSON | `json`, `geojson`, `ipynb`, `map`, `har`, `topojson`, `gltf` | Remove only whitespace outside tokens in UTF-8 input; preserve exact numbers, strings, duplicate members and order. Scalar roots supported; invalid input skipped. Notebook cells, outputs and attachments are retained |
| JSON Lines | `jsonl`, `ndjson` | Stream one valid JSON value per record; retain exact tokens, LF/CRLF and the presence or absence of a final newline |
| XML | `xml`, `ui`, `rels`, `xhtml`, `kml`, `gpx`, `dae`, `rss`, `atom`, `xmp`, `xsl`, `xslt`, `fb2` | Compact tag syntax and known OPC indentation; preserve character data and lexical regions. XML 1.0 in UTF-8/ASCII; unsupported input skipped |
| QGIS project | `qgs` | Same conservative XML compaction, with a validated `qgis` root/version and known inert QGIS DOCTYPE declarations retained verbatim |
| SVG | `svg` | `svgo` or `scour` first; native XML fallback if both are missing. Complete image `data:` URIs in `href`, `xlink:href` or `src` attributes can be packed |
| SVGZ | `svgz` | Decompress, pack as SVG, recompress |

These are **document** packers: `--no-images` does not skip them. Document-enabled
deep walking applies the same native XML/JSON rules to parts inside ZIP, OOXML,
ODF and EPUB.

JSON retains UTF-8 BOMs, escape spelling and numeric lexemes, including large
exponents and integers, without converting or reserializing values. `NaN`,
`Infinity`, invalid syntax and non-UTF-8 encodings leave the input unchanged.

JSON Lines rejects blank records, BOMs, invalid/non-finite JSON and records over
16 MiB, including their line ending. A malformed record anywhere rejects the
whole candidate. GeoJSON and notebooks receive lexical JSON compaction only;
notebook output removal or embedded image rewriting is not performed.

Source maps, HAR, TopoJSON and glTF receive the same lexical JSON compaction.
Non-JSON `.map` files are skipped. Geometry, external resources, inline image
payloads and HAR bodies are not transformed. `--include-ext json` matches these
aliases; `--include-ext xml` also matches `.rels`.
Single-document JSON input is bounded to 256 MiB before parsing, matching the
structural validator's input bound. Larger HAR/source-map files remain unchanged.

Native XML processing preserves text and tail whitespace in unknown vocabularies,
including WordprocessingML, OpenDocument and XHTML. It retains CDATA, predefined
and character entity references, namespace prefixes, comments, processing
instructions, declarations, attribute values and UTF-8 BOMs. Extra whitespace in
tag syntax can shrink. Inter-element indentation is removed only in OPC
`Types` and `Relationships` roots with their recognized empty children; mixed
content, extensions and `xml:space="preserve"` disable that removal. These two
structures have element-only content in the
[ECMA-376 Part 2 schemas](https://ecma-international.org/wp-content/uploads/ECMA-376-2_5th_edition_december_2021.zip).

DTD-bearing XML, declared/external entities, XML versions other than 1.0 and
encodings other than UTF-8/ASCII are skipped. This policy uses the standard-library
parser consistently. Debug logging records validation rejection reasons. Image
URI optimization preserves text, CDATA, comments and processing instructions;
only whole supported attribute values are eligible. External SVG tools apply
their own transformations before this URI step.

QGS accepts the known QGIS public DOCTYPE declarations without loading a DTD or
resolving external entities. Other declarations remain unsupported. Project
text, identifiers, paths, embedded payloads and the accepted declaration retain
their original spelling; QGS does not perform image URI rewrites. Qt Designer
`.ui` files use the ordinary XML policy, retaining text and widget attributes.

## Images

`--no-images` skips this category. Lossless JPEG/PNG retain required orientation
and color metadata; `--keep-meta` additionally requests incidental metadata.
The current adapters conservatively retain all metadata when presentation fields
are present. Lossless PNG also retains encoded bit depth and color type.

| Kind | Extensions | Tools |
|------|------------|-------|
| JPEG | `jpg`, `jpeg`, `jpe`, `jfif`, `jif`, `jfi`, `thm` | Lossless: `jpegtran` then `jpegoptim`. Lossy: jpegoptim `-m` (`--jpeg-quality` / `--lossy`) |
| PNG / APNG | `png`, `apng` | `oxipng` / `optipng`; `--ultra` also tries `zopflipng`. Lossy: `pngquant` |
| GIF | `gif` | `gifsicle` |
| WebP | `webp` | `dwebp` + `cwebp` |
| TIFF | `tif`, `tiff` | Preserving native suffix writer; `scientific` extra |
| AVIF | `avif` | `avifenc`/`avifdec` (ImageMagick fallback). `--lossy` selects a lossy encode |
| HEIC | `heic`, `heif` | ImageMagick. `--lossy` selects a lossy encode |
| JPEG XL | `jxl` | `cjxl` + `djxl` |
| JPEG 2000 | `jp2`, `j2k`, `jpf`, `jpx` | ImageMagick |
| OpenEXR / DNG | `exr`, `dng` | ImageMagick; DNG also `tiffcp` |
| ICO / CUR / ICNS | `ico`, `cur`, `icns` | ImageMagick |
| BMP / TGA / PNM / PCX | `bmp`, `dib`, `tga`, `targa`, `pnm`, `ppm`, `pgm`, `pbm`, `pcx`, `dcx` | ImageMagick lossless |
| Photoshop | `psd` | Recompress ZIP-encoded layer/composite channels (RLE/raw left unchanged) |
| Photoshop large document | `psb` | Native version-2 ZIP-channel recompression with structural and decoded-channel verification; raw/RLE channels and unknown metadata retained |
| Aseprite | `ase`, `aseprite` | Native zlib image/tilemap cel recompression; frames, durations, links, layers, palettes and unknown chunks retained |
| Flash movie | `swf` | Native FWS/CWS zlib recompression; movie header and exact decoded tag bytes retained |
| Telegram animation | `tgs` | Exact Lottie JSON bytes recompressed as gzip; optional `filerepack[tgs]` uses Zopfli |
| DICOM | `dcm`, `dicom`, `dic` | Lossless JPEG-LS via `gdcmconv` or `dcmcjpls`, with `filerepack[dicom]` verification. Qualified uncompressed/RLE sources only; signed, non-image and other compressed instances are skipped. `--lossy` does not apply |

### DICOM preservation

Install `filerepack[dicom]` and a JPEG-LS encoder. A bounded Part-10 inspection
checks the complete dataset, including elements after Pixel Data and nested
sequence items. It seeks past pixel payloads without decoding them. Digital
Signatures Sequence `(FFFA,FFFA)` at any depth, malformed/truncated lengths,
invalid ordering and exceeded bounds prevent encoding. Limits are **100,000
elements/items in total**, **64 sequence levels** and **4 MiB of File Meta**.
Implicit VR uses pydicom's dictionary; undefined-length UN values and opaque
UN sequences are skipped conservatively. GDCM also uses its public dictionary
when writing JPEG-LS, retaining known sequences from Implicit VR inputs.
Sources may use Implicit/Explicit VR Little Endian,
Explicit VR Big Endian or RLE Lossless. `dcmcjpls` cannot decode an RLE source;
that path needs `gdcmconv` and otherwise retains the source.

Publication requires the JPEG-LS **Lossless** transfer syntax
`1.2.840.10008.1.2.4.80`, valid complete structure, matching image/frame
attributes, and equal decoded pixels in every frame. Dataset attributes,
including private values, nested sequences and SOP identity, must be retained.
Encoding offsets, group lengths, dataset padding and File Meta encoder/version
bookkeeping may change; an encoder application title may be added if absent.
The preamble and other File Meta values remain unchanged. Near-lossless output,
failed decoding and unavailable verification leave the source unchanged.
JPEG/PNG quality flags and `--lossy` do not change this policy.

pydicom 3 compares frames using its raw pixel iterator. On Python 3.9, pydicom
2.4 compares complete decoded arrays, which can require substantial memory;
cumulative decode/memory budgets remain roadmap work. Local real-encoder tests
cover synthetic 8/16-bit monochrome, signed and multiframe images; these tests
do not establish clinical IOD conformance or cryptographic signature validity.
See [DICOM sequence encoding](https://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_7.5.html)
and [pydicom frame decoding](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.pixels.iter_pixels.html).

## Documents (PDF)

Every PDF writer first checks protection. Signed/encrypted or uninspectable PDFs
stay unchanged. Lossless candidates require qpdf 11+ object/decoded-stream
comparison; `--pdf-linearize` explicitly requires linearized output. Shared XObjects and nested Form resources are visited once per object, with
cycle detection and cumulative depth limits. Eligible Flate images support
predictor 1/2/10–15, 1/2/4/8/16-bit samples, Gray/RGB/CMYK, ICC and Indexed
color spaces, image masks and soft masks. Decode parameters, color/decode
semantics and dimensions remain unchanged; unsupported filter chains are
retained. Flate candidates contain PDF-compatible compressed sample data. See [Safety](/getting-started/safety).

| Kind | Extensions | Lossless | Lossy |
|------|------------|----------|-------|
| PDF | `pdf` | pikepdf recursive JPEG/JPX/Flate stream walk (`filerepack[pdf]`) and qpdf 11+ alternatives; smallest verified result. Without pikepdf: qpdf only | Ghostscript `--lossy` (`/ebook` unless `--pdf-profile`) or `--pdf-profile`. `--jpeg-quality` sets Distiller QFactor |
| Illustrator | `ai` | Same as PDF when the file is a PDF wrapper | Same Ghostscript path |

## Video and audio

`--no-images` skips these. WMV/AVI/ASF/3GP/MPEG-TS convert to MP4 unless
`--no-convert-container`. MKV/WebM/MOV/M4V keep their container.

| Kind | Extensions | Tools |
|------|------------|-------|
| Video | `mp4`, `mkv`, `webm`, `mov`, `m4v`, `wmv`, `avi`, `asf`, `3gp`, `ts`, `mts`, `m2ts` | `ffmpeg`. `--wmv-lossless` is CRF 0 (VP9 lossless for WebM) |
| FLAC | `flac` | `flac` recompress; covers with `filerepack[media]` |
| ALAC / M4A | `m4a`, `m4b` | ffmpeg ALAC when applicable; covers with mutagen |
| Ogg / Opus | `ogg`, `opus`; `oga` | `optivorbis` for Vorbis; the registered Opus route has no qualified OptiVorbis codec optimization. Cover-art changes may still apply. FLAC-in-Ogg `.oga` stays on ffmpeg |
| WavPack / TTA | `wv`, `tta` | ffmpeg |
| Monkey's Audio | `ape` | `mac` when installed; covers with mutagen |
| MP3 | `mp3` | `mp3packer` (lossless frame packing). `--ultra` passes `-z`. Covers with mutagen |

`optivorbis` and `mp3packer` are not in Homebrew/apt; see [External tools](/tools/).
Video defaults to stream-copy remuxing and requires both `ffmpeg` and `ffprobe`.
`--video-mode lossless` explicitly re-encodes losslessly; `--video-mode lossy --lossy`
permits lossy encoding. Unsupported streams or failed preservation checks prevent
publication.

## Compressed streams and data

| Kind | Extensions | Tools / extra |
|------|------------|----------------|
| gzip / xz / bzip2 / zstd / brotli | `gz`, `gzip`, `xz`, `bz2`, `zst`, `br` | `pigz`/`gzip`, `xz`, `bzip2`, `zstd`, `brotli` |
| CPIO and bzip2-compressed CPIO | `cpio`, `cpbz2` (also `cpio.bz2`) | Safe regular single-link members are deep-walked; links, metadata and untouched payloads are preserved |
| WARC web archives | `warc`, `warc.gz`, `warc.gzip` | Standard library; exact decoded WARC 1.0/1.1 bytes, one level-9 gzip member per record |
| lz4 / lzip / lzma / lzo / compress | `lz4`, `lz`, `lzma`, `lzo`, `z` | `lz4`, `lzip`, `lzma`, `lzop`, `compress` |
| SQLite | `sqlite`, `sqlite3`, `db`, `gpkg`, `mbtiles` | Verified `VACUUM`; in-place work requires `--sqlite-offline` and no sidecars. Distinct outputs use a consistent snapshot, including committed WAL pages. `.db` requires the SQLite header |
| SQLite application aliases | `vscdb`, `sqlitedb` | Verified offline `VACUUM INTO`, preserving schema, rowids, values and application settings |
| DuckDB | `duckdb` | `filerepack[duckdb]`: fresh database copy with independent catalog and value verification |
| Parquet | `parquet` | `filerepack[parquet]` or `[data]` (PyArrow 19+). Schema, metadata and ordered values are verified before publication. `--ultra` is zstd level 22 |
| ORC / Avro / Feather / Arrow | `orc`, `avro`, `feather`, `arrow`, `ipc` | `filerepack[data]` |
| HDF5 / NetCDF | `h5`, `hdf5`, `hdf`, `nc`, `nc4` | `h5repack` / netCDF4; `scientific` extra |
| R serialization | `rds`, `rda`, `rdata` | `serialization` extra; passive XDR v2/v3 |
| PyTorch checkpoint | `pt`, `pth` | `serialization` extra; explicit mmap compatibility |
| SPSS system file | `sav`, `zsav` | `serialization` extra; ZSAV experimental |
| MATLAB | `mat` | `scientific` extra; experimental pending MATLAB |
| Safetensors / GGUF | `safetensors`, `gguf` | Bounded passive inspection; no qualified writer is registered |
| ONNX | `onnx` | `filerepack[onnx]` for bounded protobuf/checker inspection; no writer |
| PyTorch Distributed Checkpoint | local directory | `inspect-dcp`; opaque inventory only, completeness and recompression are not verified |
| FITS | `fits`, `fit`, `fts` | `filerepack[fits]`: verified GZIP tiled-image compression with floating-point quantization disabled |
| NRRD | `nrrd` | Standard library: attached raw/gzip/bzip2 arrays, with decoded bytes and header metadata verified |
| Blender | `blend` | Standard-library gzip; Zstandard with `filerepack[blend]`. Entire decoded project stream verified |
| QGIS auxiliary database | `qgd` | Native SQLite `VACUUM INTO`; schema, rows, rowids and application metadata verified |
| WOFF / WOFF2 | `woff`, `woff2` | `filerepack[fonts]` (fontTools/Brotli); native exact-table validation is required |

### Native format policies and limits

WARC has a separate conversion policy: standalone plain `.warc` becomes
`.warc.gz`, while nested plain WARC files are retained. See
[Web archives](/use-cases/data-files/#web-archives-warc) for index handling,
supported framing and resource limits.

All newly added formats retain their filename extension, including when nested
in an archive. Missing optional backends, unsupported variants, invalid input or
failed candidate verification leave the source unchanged. Normal dry-run,
distinct-output and minimum-savings rules also apply.

- **PSB:** version 2, supported 8/16/32-bit channels. Only ZIP and ZIP-prediction
  streams are recompressed; prediction bytes, raw/RLE channels, layer records,
  image resources and unknown tail blocks remain intact. ZIP-compressed mask
  channels are unsupported and cause the file to be skipped.
- **Aseprite:** 8/16/32-bit sprites and zlib image/tilemap cels. Raw and linked
  cels are retained. Tileset chunks are retained as opaque payloads rather than
  recompressed. Frame/chunk lengths and decoded cel fingerprints are checked.
- **FITS:** Astropy/CFITSIO GZIP_2 tiles with quantization disabled, even with
  `--lossy`. Supported image arrays have up to six axes and standard integer or
  floating-point BITPIX values. Verification compares every image bit, including
  NaN payloads and signed zeros, header values/comments and the order of repeated
  keywords, plus exact non-image data bytes. Scaling keywords are retained.
  A compressed primary image becomes a compressed image extension after an empty
  primary HDU; image HDU indices consequently increase by one. Header card
  positions and regenerated checksums may change. Readers need FITS tiled-image
  compression support. Random groups are unsupported.
- **NRRD:** attached binary arrays with known type, dimensions and endianness.
  Raw data becomes gzip; existing gzip/bzip2 retain their codec. Array bytes and
  every header byte except the encoding value are compared. Detached data,
  ASCII/hex encodings and nonzero line/byte skips are unsupported.
- **Blender:** structurally checked 12-byte `BLENDER` headers and BHead blocks,
  including 32/64-bit pointers and both endiannesses. Existing gzip/Zstandard
  retain their codec; raw version 3.00+ streams use Zstandard when installed,
  otherwise gzip. Older raw versions use gzip. Decoded project bytes remain
  identical; compression wrapper metadata and seek indexes can change. No
  Blender process or embedded script is run.
- **QGD:** offline valid SQLite databases without WAL/journal sidecars or virtual
  tables. VACUUM must preserve schema, rows, explicit/implicit rowids, encoding,
  application ID and user version. A changed rowid rejects the candidate.
- **SQLite aliases:** `.vscdb` and `.sqlitedb` require an exact SQLite header and
  the QGD preservation checks. WAL, journal and shared-memory sidecars cause a
  skip before opening the source. Inputs are limited to 256 MiB; active editor
  databases must be closed and transaction sidecars cleared by their application.
- **DuckDB:** offline databases up to 256 MiB, built-in scalar columns (including
  decimals and nanosecond timestamps), lists, structures, maps, schemas and indexes.
  Catalog definitions, comments/tags and ordered typed Arrow values must match,
  including nested floating-point bits. Views, sequences, macros, custom types and
  unsupported Arrow types (such as intervals) are skipped; `.wal` sidecars cause a skip.
  Verification requires PyArrow 19+ (included in the `duckdb` extra) and is limited
  to one million rows and 256 MiB of decoded/serialized values.
  Extension installation/loading and external access are disabled during data
  processing. Physical row locations and implicit `rowid` values can change.
- **SWF:** FWS or CWS movies, up to 256 MiB encoded/decoded. Version 6+ can use
  CWS; earlier FWS and LZMA ZWS are left unchanged. Header lengths, frame header,
  tag framing and final End tag are checked; exact decoded bytes are compared.
  Embedded scripts are never run and tag payload semantics are not rewritten.
- **TGS:** a single valid gzip member containing Lottie JSON with `tgs`, version
  and layers fields. Exact decoded JSON bytes, including lexical numbers and
  whitespace, are retained. Input and decoded payloads are limited to 4 MiB;
  optional Zopfli is used only up to 1 MiB decoded. Concatenation, trailing data
  and invalid JSON are rejected. Gzip wrapper metadata can change. SWF and TGS
  obey `--no-images` and the normal dry-run/savings rules.

PSB, Aseprite, NRRD, FITS, QGS and QGD inputs are limited to **256 MiB**. Decoded
PSB composite/layer payloads, Aseprite cels, NRRD arrays and FITS images have
256 MiB bounds as well. Blender limits its complete decoded stream to 256 MiB.
NRRD headers are limited to 1 MiB. These are supported-input bounds, not a promise
that peak memory use stays below 256 MiB: parsing and verification can hold
multiple buffers/arrays. JSON Lines uses bounded records instead of reading the
complete file. Application-rendering equivalence and large-file performance
benchmarks are separate from these structural/data checks.

## Not supported

These stay untouched (no extract + rewrite):

- Signed installers: `deb`, `rpm`, `pkg`, `dmg`
- CAB (recognized, but no qualified writer), ISO and AR / `a` / `lib`
- OpenType `.otf` fonts (ZIP ODF templates with that extension are packed)
- LAS/LAZ point clouds (no extension-changing conversion is added)

## Python extras

The complete extra list and installation commands are maintained in
[Installation](/getting-started/installation#optional-extras).

See [preserving scientific profiles](scientific.md) for exact support, reader gates,
resource options, checkpoint compatibility and the separate `repack-store` command.
See [model-weight inspection](model-weights.md) for Safetensors, GGUF, ONNX, and
PyTorch Distributed Checkpoint inspection limits and current writer status.

## Preserving web fonts

WOFF and WOFF2 candidates run through an isolated fontTools worker. Acceptance
compares every decoded SFNT table byte, flavor/version fields, optional metadata
and private payloads. DSIG-bearing sources are protected. Writers that serialize
a table differently are refused even if a reader can load the result. Unknown
framing, overlapping ranges, bad checksums and exceeded budgets retain the source.
External WOFF2 tools can supply candidates, but they do not replace this native
verification requirement. Generated real-reader fixtures establish the supported
positive cases; they do not qualify every third-party font corpus.
