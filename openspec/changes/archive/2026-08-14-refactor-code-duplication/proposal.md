# Change: Refactor Code Duplication in repack.py

## Why
The `repack.py` file is 2,156 lines with an estimated 60% code duplication. This makes the file difficult to maintain, increases the chance of inconsistent bug fixes, and inflates the codebase unnecessarily:

- **Standalone file handling**: ~700 lines for 14 formats with identical dryrun/non-dryrun patterns
- **Deep-walking dispatch**: Same 25-line `if ext == 'jpg': ... elif ext == 'png': ...` block repeated across 5 code paths (ZIP, 7z, RAR variants)
- **OS-specific quiet redirection**: `if os.name == 'nt'` pattern repeated ~40 times
- **Size calculation**: `(insize - outsize) * 100.0 / insize` repeated ~20 times
- **Duplicate function**: `pack_jpg_re()` defined twice identically

## What Changes
- Extract a `_pack_file()` helper that handles the common dryrun/non-dryrun + size tracking pattern
- Extract a `_dispatch_packer()` function that maps extensions to packer functions (replacing the repeated dispatch blocks)
- Extract OS-specific quiet suffix into a constant (`QUIET_SUFFIX = '2>nul' if os.name == 'nt' else '2>/dev/null'`)
- Remove the duplicate `pack_jpg_re()` definition
- Remove unused `random` calls (3 occurrences)
- Remove unnecessary `.encode('utf8')` on file paths passed to logging (5 occurrences)

## Impact
- Affected specs: `architecture`
- Affected code: `filerepack/repack.py` (target: reduce from ~2156 to ~800-1000 lines)
- **BREAKING**: None — internal refactoring with unchanged external behavior
- Depends on: `fix-shell-injection-vulnerability` and `fix-thread-safety` (should use the new `_run_command()` helper)
