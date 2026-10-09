# Change: Add dialect preserving MAT recompression

## Why

The survey found 12 MAT files with 1,397,840,168 declared bytes in two projects.
Two downloaded files had Level-5-family headers and a first `miCOMPRESSED` element.
No MAT rewrite or MATLAB reader comparison was performed. This establishes a
target for a compression experiment, not measured savings or a working writer.

## What Changes

- Classify MAT v4, Level-5-family files and MATLAB v7.3/HDF5 by content.
- Recompress existing zlib `miCOMPRESSED` elements while preserving their decoded
  bytes, element order and unaffected records in the initial Level-5 profile.
- Add a distinct v7.3 profile only after HDF5 graph/user-block preservation and
  MATLAB compatibility are demonstrated.
- Preserve the source dialect; do not convert uncompressed v4/v6 data to v7/v7.3.
- Gate each writer profile independently on real gain and native-reader evidence.

## Impact

- Affected specs: `mat-recompression`.
- Affected code: dedicated MAT parser/packer, `formats.py`, `dispatch.py`, validators
  and tests; optional HDF5 adapter for the separately verified v7.3 profile.
- Dependencies: `extend-hdf5-netcdf-recompression` for v7.3 only; shared validation,
  transaction and resource-budget contracts for both profiles.
- Status: approved for implementation by the user on 2026-10-04; experimental MAT code is implemented; native MATLAB release qualification remains open.

## Evidence

- [Survey and downloaded-header checks](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [MATLAB MAT versions](https://www.mathworks.com/help/matlab/import_export/mat-file-versions.html).
- [MathWorks MAT file format specification](https://www.mathworks.com/help/pdf_doc/matlab/matfile_format.pdf).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
