# Change: Migrate CI from Travis CI to GitHub Actions

## Why
The project uses Travis CI (`.travis.yml`) configured to test Python 3.3–3.6, all of which are end-of-life. Travis CI itself has been largely superseded by GitHub Actions. No actual test commands are defined — the config just calls `tox`, which doesn't exist in the project.

## What Changes
- Remove `.travis.yml`
- Create `.github/workflows/ci.yml` with GitHub Actions workflow
- Configure matrix testing for Python 3.9, 3.10, 3.11, 3.12
- Add steps for linting (flake8/ruff), type checking (mypy), and test running (pytest)
- Add coverage reporting

## Impact
- Affected specs: `infrastructure`
- Affected code: `.travis.yml` (removed), `.github/workflows/ci.yml` (created)
- **BREAKING**: None — CI is internal tooling with no user-facing impact
