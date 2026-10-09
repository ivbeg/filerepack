# Change: Extend HDF5 and NetCDF with preserving compression profiles

## Why

These formats already have writers, but current `pack_hdf5` and `pack_netcdf`
select broad compression commands and rely on structural output checks. The survey
found 46 H5 files with 35,681,053,458 declared bytes in Dataverse and four NC files
with 37,847,824,385 bytes in Zenodo. Each category is concentrated in one project;
no gain on those scientific files was measured. Their volume and existing writer
coverage justify native-format experiments and stronger preservation checks, not
a broad prevalence claim or a predicted percentage saving.

## What Changes

- Add graph-aware HDF5 source/candidate comparison and per-dataset lossless policies.
- Preserve user blocks, datatypes, references, links and reader compatibility.
- Add a separate NetCDF model/attribute/raw-value verifier and explicit same-kind
  `nccopy` execution for NetCDF-4 and NetCDF-4 classic-model files.
- Keep CDF-1/CDF-2/CDF-5 unchanged when compression would require format conversion.
- Add bounded, measured compression profiles instead of blanket writer arguments.
- Treat MAT v7.3 and future H5AD/Loom profiles as specializations with additional
  evidence, not automatic aliases enabled by this change.

## Impact

- Affected specs: `hdf5-recompression`, `netcdf-recompression`.
- Affected code: `data.py`, format-specific validators, optional scientific-data extras,
  backend capability discovery, dispatch and real-format integration fixtures.
- Refines the hierarchical-format requirements of `update-data-format-preservation`;
  it does not duplicate its Parquet/Arrow/SQLite work or change its task status.
- Uses shared transaction, structural-validation and resource-budget contracts.
- Status: approved for implementation by the user on 2026-10-04; existing approval of generic preservation work is not approval of this proposal.

## Evidence

- [Survey](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [HDF Group h5repack guide](https://support.hdfgroup.org/documentation/hdf5/latest/_h5_t_o_o_l__r_p__u_g.html).
- [Unidata NetCDF utilities](https://docs.unidata.ucar.edu/netcdf-c/current/netcdf_working_with_netcdf_files.html).
- [Unidata NetCDF FAQ](https://docs.unidata.ucar.edu/netcdf-c/current/faq.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
