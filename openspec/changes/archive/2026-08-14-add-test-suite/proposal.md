# Change: Add Initial Test Suite

## Why
The project has zero test coverage. The `test/` directory is empty. This makes every change risky — there's no safety net to catch regressions in the compression logic, CLI argument handling, or utility functions. Adding tests is essential before any refactoring effort.

## What Changes
- Add `pytest` and `pytest-cov` as dev dependencies
- Create `conftest.py` with shared fixtures (sample files, temp directories)
- Add unit tests for `utils.py` (pure functions — easiest to test)
- Add unit tests for `consts.py` (constants, extension mappings)
- Add integration tests for CLI commands (using Typer's `CliRunner`)
- Add a few end-to-end tests with small sample files for key formats

## Impact
- Affected specs: `testing`
- Affected code: `test/` (new files)
- **BREAKING**: None — tests are additive only
