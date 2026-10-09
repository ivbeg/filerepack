# Change: Extend TIFF recompression with sample and metadata preservation

## Why

The separate Wikimedia Commons census reports 4,862,791 TIFF files and
413,643,552,524,623 bytes (413.64 TB). TIFF is already registered in filerepack,
but `pack_tif` tries an ImageMagick command with `-strip`, followed by `tiffcp`.
The census establishes a large relevant corpus, not measured recompression gains.
The current path needs format-specific preservation before expanding scientific,
archival and geospatial TIFF support.

## What Changes

- Replace stripping/object-conversion candidates with verified native TIFF rewrites.
- Compare complete IFD/SubIFD structure, exact samples and semantic metadata.
- Add tested LZW/DEFLATE and reversible predictor profiles with explicit eligibility.
- Preserve classic TIFF/BigTIFF kind, page/sample representation and reader profile.
- Handle GeoTIFF/COG/opaque metadata only within separately verified profiles;
  otherwise return a precise unsupported reason.
- Measure gain on real multipage/high-depth/geospatial/archival files before claiming it.

## Impact

- Affected specs: `tiff-recompression`.
- Affected code: `images.py`, dedicated TIFF inspection/comparison, optional decoder
  dependencies, backend capability discovery and native integration fixtures.
- Refines TIFF-specific application of `update-media-preservation-policy` and
  `add-structural-output-validation`; uses shared file publication and budgets.
- Status: approved for implementation by the user on 2026-10-04; implementation and evidence are tracked in tasks.md and validation.md.

## Evidence

- [Survey and Commons accounting](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [Commons media census](https://commons.wikimedia.org/wiki/Special:MediaStatistics).
- [LibTIFF tiffcp documentation](https://libtiff.gitlab.io/libtiff/tools/tiffcp.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
