# Change: Add Dataclasses for Result Types

## Why
Different functions in the codebase return results using inconsistent data structures:
- `pack_*()` functions return `[filepath, insize, outsize, share]` (a list)
- `repack_zip_file()` returns `{'stats': [...], 'files': [...], 'final': [...]}` (a dict)
- `process_single_file()` returns yet another dict schema

No dataclasses or TypedDicts are used, making it easy to access the wrong index or key and difficult to understand what a function returns without reading its implementation.

## What Changes
- Create a `PackResult` dataclass with fields: `filepath`, `insize`, `outsize`, `savings_pct`
- Create a `RepackSummary` dataclass for batch results with fields: `results: List[PackResult]`, `total_insize`, `total_outsize`, `elapsed_seconds`
- Update `pack_*()` functions to return `PackResult` instead of lists
- Update `repack_zip_file()` to return `RepackSummary`
- Update `process_single_file()` to return `PackResult`

## Impact
- Affected specs: `architecture`
- Affected code: `filerepack/repack.py`, `filerepack/__main__.py`
- **BREAKING**: Technically yes for any programmatic API users who depend on the list/dict return types. However, the package is at v0.1.4 and the internal API is not formally stabilized, so this is an acceptable change.
