# Change: Fix Config File Inaccuracies

## Why
Multiple configuration files contain outdated or incorrect values from the project's previous name (`filesrepack`). These inaccuracies cause broken links, failed coverage reports, and confusion during development.

## What Changes
- Fix `setup.py`: Correct GitHub URL from `ivbeg/filesrepack` to `ivbeg/filerepack`
- Fix `.coveragerc`: Change source from `filesrepack` to `filerepack`
- Fix `Makefile`: Change lint target from `filesrepack` to `filerepack`
- Update Python version classifiers in `setup.py` to reflect actual supported versions (3.9+)

## Impact
- Affected specs: `configuration`
- Affected code: `setup.py`, `.coveragerc`, `Makefile`
- **BREAKING**: None — these are metadata/formatting corrections only
