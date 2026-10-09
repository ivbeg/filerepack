# Implementation validation — 2026-10-04

## Implemented and tested

The metadata-stripping path is removed. The writer retains metadata addresses and rewrites only accounted raw/LZW/DEFLATE image-data suffixes, with exact native samples, IFD/tags and storage-field checks. Classic/BigTIFF, endian, high-depth, floating and SubIFD tests pass; one complete rasterio LZW source shrank.

Integration includes CLI/bulk/library validation, unchanged reasons and JSON profile details,
shared ordinary-file candidate/source/destination transactions, isolated native workers,
cumulative decode/node/scratch/time accounting, sampled RSS supervision and cancellation.
Scientific dry-run does not encode or create candidate workspaces.

## Evidence

- [Full reproducible report and all-attempt artifacts](../../../dev/format_survey/implementation-2026-10-04/README.md).
- [Runtime profile contracts](../../../docs/docs/formats/scientific.md).
- [Trusted native and adversarial tests](../../../test/test_scientific_formats.py).

The earlier full suite passed (1,373 tests, 145 skips); the final focused integration suite passed 423 tests with 4 skips.
This includes 84 scientific tests with one filesystem-dependent skip, root-accounting closure after worker failure and preservation of prior destinations on scientific refusal.
Full repository Ruff/mypy, Python 3.9 module compilation, seven strict OpenSpec validations and the documentation production build pass.
Native CI is configured but its remote runs are not claimed as completed.

## Open qualification gates

Commons creator coverage, wider palette/alpha/EXIF/ICC/planar combinations and separately advertised GeoTIFF/COG profiles remain open. Recognized COG/opaque metadata is refused; the aggregate Commons bytes are not a savings estimate.

This validation note records actual work without declaring every broader task in
`tasks.md` complete. No change is archived or represented as universally qualified.

## Current integrated reconciliation — 2026-10-07

The [completion audit](../../../dev/quality/completion-2026-10-07.md) records
current runtime/installation checks, qualification scope and open gates.
`tasks.md` now distinguishes implemented tasks from unmet whole-corpus,
historical/native reader and platform requirements. The dated evidence above
is retained as its original experiment record; no release/deployment is asserted.
