# Change: Recompress qualified OfficeArt PNG and JPEG without image loss

## Why

PNG/JPEG BLIPs currently remain byte-identical even when the host supports their
placement. Documents dominated by raster images therefore miss a major possible
source of savings. Generic image packers do not establish the required OfficeArt
pixel/coefficient, metadata, UID and reference preservation contract.

## What Changes

- Extend the existing opt-in ole_recompress mode with qualified PNG IDAT
  recompression and JPEG entropy optimization, selecting only smaller results.
- Preserve PNG filtered samples and every unaffected chunk; preserve JPEG
  quantized DCT coefficients, quantization/color data and required markers.
- Preserve BLIP/FBSE UIDs, tags, geometry, drawing properties and reference
  identities; update only approved payload/record lengths and host pointers.
- Add independent raster intended-change verification instead of weakening
  strict OLE or reusing the generic decoded-pixel-only image contract.
- Keep unsupported image variants unchanged and report missing dependencies.

## Impact

- Affected capability: officeart-recompression; additive requirements.
- Affected code: shared raster codecs, ole_officeart.py, qualified host adapters,
  ole_recompress.py, verification registration, extras/tool discovery and docs.
- Priority: P1, following the [coverage proposal](../extend-doc-xls-officeart-coverage/proposal.md)
  for ordinary DOC/XLS layouts; existing qualified hosts can be delivered first.
- Prerequisite: [initial OfficeArt](../add-officeart-payload-recompression/proposal.md).
- Supersedes the initial proposal's deferred raster work as a concrete follow-on;
  it does not modify or mark those historical tasks completed.
- No downsampling, palette reduction, lossy JPEG, image conversion, APNG,
  DIB/TIFF/PICT or newly enabled protected/macro-bearing host rewriting.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

Use licensed real DOC/XLS/PPT image fixtures and independent corruption cases.
Measure final file sizes against strict compaction and existing metafile/PPT
alternatives. Verify exact content and metadata before application rendering;
rendering alone cannot accept a candidate. Qualify optional backends on supported
platforms and installed distributions, with explicit skips when unavailable.
