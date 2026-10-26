# Lossless raster representations inside parsed BLIPs

## Decisions

### PNG first

Initially support static PNG with valid bounded chunks, CRCs and the declared
IHDR/filter/compression layout. Concatenate IDAT, strictly decode its zlib stream
and recompress the exact filtered scanline bytes with zlib9 and qualified optional
Zopfli. This preserves sample depth, interlacing, palette and alpha without
converting to an 8-bit/RGB image or selecting new row filters. Rebuild IDAT lengths
and CRCs; preserve every other chunk byte, ordering and metadata exactly.

Qualify recognized ancillary/color/text chunks and safe-to-copy unknown chunks.
Unknown critical/unsafe-to-copy chunks, signatures, APNG, malformed or ambiguous
data remain unchanged. Bound the inflated scanline size from IHDR before decode
and charge decoding and verification to the root budget. An independent parser
compares exact inflated bytes and non-IDAT chunks; pixel decoding is additional
evidence, not a substitute for sample/chunk equality.

### JPEG second

Initially qualify 8-bit sequential Huffman gray/three-component JPEG and the
matching OfficeArt record instances. Use optional pinned libjpeg-turbo jpegtran
entropy optimization with marker copying. Its output is untrusted: independently
compare every quantized DCT coefficient, quantization table, component/sampling
layout, dimensions and color/interpretation fields, plus APP/COM marker bytes and
ordering. Preserve EXIF, ICC, JFIF and Adobe information and orientation.

Entropy tables, encoded scan data and their proven bookkeeping may change.
Progressive/arithmetic, CMYK/YCCK, unusual precision, duplicate/ambiguous metadata
and signature-bearing variants remain copied until separately qualified. No
decode/re-encode via Pillow and no metadata stripping is allowed. If a qualified
read-only coefficient adapter or jpegtran is unavailable, skip JPEG independently
of PNG. The coefficient-reader dependency/interface must be measured and recorded
before activation; it must parse source/candidate itself rather than trust an
encoder-supplied digest. Rendering checks supplement that comparison.

### OfficeArt identity and host placement

Use parsed PNG/JPEG BLIPs, never carve image signatures from opaque streams.
Qualify one/two-UID layouts and their documented uncompressed-content identity
conventions; retain both original UID fields, the FBSE UID, tag, names, geometry
and display properties. Unsupported identity conventions leave the BLIP unchanged
rather than guessing a new UID. Reuse audited host relocation and fixed root
stream replacement modes.

### Candidate contracts and dependencies

Keep strict OLE stream equality and exact PPT decoded-storage equality unchanged.
The raster verifier accepts only an explicit per-BLIP change manifest and repairs
independently resolved host references. It can share one OfficeArt candidate with
EMF/WMF only when the verifier accounts for both contracts together. Composition
with the separate PPT embedded-storage pass requires complete union verification;
otherwise retain independently verified alternatives and select the smallest.

Reuse stdlib zlib; Zopfli and JPEG encoding/coefficient tools remain optional,
pinned and license-documented. Missing a codec or one image profile does not
prevent processing other qualified pictures. Budgets, worker termination,
transactions and physical minimum-savings acceptance remain unchanged.

Honor effective parent image/category selections: disabled images are copied
even when other document work proceeds. Generic quality or metadata-stripping
preferences cannot weaken this codec's exact content/metadata contract. Coordinate
these restrictions with the existing media-preservation proposal; do not reuse
a generic lossy/image-metadata backend for this capability.

## Qualification and rollout

Deliver PNG, then JPEG after coefficient/metadata evidence. Test palette, alpha,
gray, truecolor, high-depth/interlaced PNG, chunk boundaries, ICC/EXIF/orientation,
one/two UIDs, baseline JPEG sampling, and explicit unsupported variants. Include
candidate faults changing a single coefficient/sample, UID, profile, marker,
anchor, pointer or unrelated byte. Publish original/compaction/selected sizes,
counts, time and memory on pinned real fixtures; weak-encoding controls are
separate. Rollback disables only the raster codecs, retaining EMF/WMF behavior.

## Primary references

- [MS-ODRAW PNG BLIP](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/7af7d17e-6ae1-4c43-a3d6-691e6b3b4a45)
- [MS-ODRAW JPEG BLIP](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/704b3ec5-3e3f-425f-b2f7-a090cc68e624)
- [MS-ODRAW FBSE](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/2f2d7f5e-d5c4-4cb7-b230-59b3fe8f10d6)
- [PNG compression specification](https://www.w3.org/TR/png-3/#10Compression)
- [jpegtran behavior and marker policy](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/doc/usage.txt)
