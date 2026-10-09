# Change: Add transactional local Zarr v2 store recompression

## Why

The survey identified a Zarr v2 store in a pinned Hugging Face dataset revision:
5,147 visible objects with 5,571,709,641 declared bytes in a partial tree. Verified
consolidated metadata describes 33 arrays: 30 use Blosc/LZ4 level 5 with shuffle,
and three have no compressor. No chunk recompression or complete-store comparison
was performed. Numeric chunk filenames require whole-store processing; registering
a `.zarr` file extension in the existing file pipeline would be insufficient.

## What Changes

- Add an explicit `repack-store SOURCE --output-dir PARENT` command and a typed
  local-store library entry point. The initial release writes a new distinct store.
- Handle complete offline filesystem Zarr v2 groups/arrays with supported fixed-size
  dtypes, no additional filters, and verified lossless compressor configurations.
- Recompress arrays consistently, retaining keys, missing chunks and array semantics;
  synchronize `.zarray` and existing `.zmetadata` declarations.
- Add a dedicated directory staging/verification/publication contract with atomic
  no-replace publication where supported. Do not reuse file replacement semantics.
- Gate codec profiles on complete stores and real gain/read-cost measurements.

## Impact

- Affected specs: `zarr-store-recompression`, `directory-store-transactions`.
- Affected code: new store model/lifecycle and Zarr module, CLI command, optional
  Zarr/Numcodecs extra, budget accounting, validators and platform integration tests.
- Dependencies: shared outcome/budget/capability concepts; the file-only transaction
  API is not assumed sufficient for directories.
- First release excludes in-place writes, overwrite/merge, ordinary bulk discovery,
  object dtype, remote/object stores, ZIP stores, v3/sharding and active writers.
- Status: approved for implementation by the user on 2026-10-04; the partial observed tree does not establish a supported writer.

## Evidence

- [Survey and pinned store metadata](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [Zarr v2 specification](https://zarr-specs.readthedocs.io/en/latest/v2/v2.0.html).
- [Observed dataset revision](https://huggingface.co/datasets/nmasi/era5/tree/b673f560d8e8a91e6aba312b26b17e755c004b08).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
