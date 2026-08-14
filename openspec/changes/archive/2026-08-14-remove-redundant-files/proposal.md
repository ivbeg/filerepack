# Change: Remove Redundant Files

## Why
The codebase contains files that are duplicates or severely outdated, adding maintenance burden without providing value.

- `bin/filerepack.py` (124 lines) is a simplified duplicate of `__main__.py`. The `console_scripts` entrypoint already provides full CLI functionality.
- `README.rst` (71 lines) is severely outdated — it still says "docx to csv convertor", references the old URL, and describes only basic usage. The Markdown version (1004 lines) is comprehensive and current.
- `build/lib/` is a stale build artifact directory that should not be tracked.

## What Changes
- Remove `bin/filerepack.py`
- Remove `README.rst`
- Remove `build/lib/` (or add to `.gitignore`)

## Impact
- Affected specs: `code-quality`
- Affected code: `bin/filerepack.py`, `README.rst`, `build/`
- **BREAKING**: None — `bin/filerepack.py` is redundant with the entrypoint; removing it doesn't affect functionality
