# Change: Modernize Packaging with pyproject.toml

## Why
The project uses the legacy `setup.py` + `setup.cfg` pattern without a `pyproject.toml`. Modern Python packaging standards (PEP 517/518/621) recommend using `pyproject.toml` as the single source of truth for build configuration. This simplifies the build process, enables better tool interoperability, and is the standard approach for new projects.

## What Changes
- Create `pyproject.toml` with build system requirements and project metadata
- Move metadata from `setup.py` into `pyproject.toml`
- Simplify `setup.py` to a minimal shim (or remove it entirely)
- Add `[project.optional-dependencies]` for dev and parquet extras
- Configure `pytest`, `mypy`, and `ruff` in `pyproject.toml`

## Impact
- Affected specs: `infrastructure`
- Affected code: `pyproject.toml` (new), `setup.py` (simplified), `setup.cfg` (may be removed)
- **BREAKING**: None — the package installs and works identically from the user's perspective
