# Change: Fix Thread-Unsafe os.chdir() Calls

## Why
The `repack_zip_file()` method uses 8 calls to `os.chdir()` to switch the working directory before running external tools. Since `os.chdir()` modifies process-global state, this prevents parallel processing (the `--jobs` flag exists but cannot work safely) and creates race conditions when multiple files are processed concurrently.

## What Changes
- Replace all `os.chdir()` + `os.system()` patterns with `subprocess.run(cmd, cwd=target_dir)`
- Remove reliance on process-global working directory entirely
- Enable the existing `--jobs` CLI flag to work correctly once thread-safety is fixed

## Impact
- Affected specs: `concurrency`
- Affected code: `filerepack/repack.py` (`repack_zip_file()` method)
- **BREAKING**: None — this is an internal implementation change with no user-visible behavior change
