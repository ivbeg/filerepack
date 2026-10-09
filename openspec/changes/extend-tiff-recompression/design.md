## Context

A TIFF file can contain multiple images, reduced-resolution levels, typed samples,
custom tags and referenced data. Pixel rendering through Pillow or ImageMagick can
normalize that representation. `tiffcp` copies understood tags; its successful
exit does not establish that arbitrary unknown tags or their referenced bytes survived.

## Goals / Non-Goals

- Goals: retain exact samples and a declared TIFF metadata/structure contract.
- Non-goals: color conversion, JPEG re-encoding, reducing bit depth, dropping pages,
  flattening pyramids, rebuilding COG layout without evidence or claiming every TIFF dialect.

## Decisions

1. Inventory the full IFD graph, next-IFD and SubIFD relationships, page order,
   dimensions, sample format/depth/count, planar layout, photometric interpretation,
   orientation, extra samples, palettes and resolution. Detect cycles, out-of-file
   offsets, conflicting ranges and unsupported structures before invoking a writer.
2. Compare complete decoded sample bytes in the source dtype and channel/page order,
   including signed integers, high bit depth and floating-point bits. Do not substitute
   equality of rendered RGB pixels for native sample identity. Preserve semantic tags
   such as ICC, EXIF/XMP/IPTC, descriptions, GeoKeys/transforms, nodata and application tags.
3. Permit changes only to an enumerated storage-tag set: compression, compatible
   predictor, strip/tile byte counts and offsets, and necessary IFD/value offsets.
   Initially retain strip/tile geometry and byte order. Preserve classic/BigTIFF kind.
   Reversible integer/floating predictors require exact dtype-specific fixture evidence.
   JPEG and other lossy source segments are initially skipped rather than decoded and resaved.
4. Generate native LZW/DEFLATE candidates only for tested sample/backend combinations.
   Discover backend codec/predictor support instead of assuming one command-line flag
   works across LibTIFF builds. Remove `-strip` from the preserving TIFF path; a
   backend that cannot retain the required graph/tags is ineligible for that input.
5. Unknown tag values can contain private offsets. Copying their integer bytes is not
   proof that the referenced payload still exists. Retain only proven relocatable
   profiles or refuse the candidate. Opaque tags are not silently dropped. GeoTIFF
   and COG labels require their own fixture scope: a COG source must remain COG under
   a dedicated layout validator, or the input is skipped.
6. Use a read-only decoder/tag inspector distinct from the writer invocation, plus
   native-reader integration for advertised TIFF classes. All decode passes, tiles,
   IFD nodes, metadata and processes consume the shared operation budget.

## Risks / Trade-offs

- Many large TIFFs are already efficiently compressed; publish only measured gain and
  retain already optimal inputs without savings claims.
- Exact float/high-depth checks can exclude tools that render correctly but normalize
  native samples. This restriction is intentional for lossless scientific data.
- Some private metadata requires vendor-specific knowledge; a narrow profile is safer
  than a universal metadata claim.

## Migration Plan

First remove unsafe stripping from the preserving path and add complete TIFF
comparison. Enable basic single/multipage profiles, then scientific and geospatial
subprofiles only with evidence. Backend absence or unsupported tags preserves input.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.

TIFF candidates use an unchanged-address metadata prefix and a rewritten image-data
suffix rather than `tiffcp`; only declared compression/offset/count fields change.
Unsupported suffix framing or opaque/private tags prevent rewriting.
