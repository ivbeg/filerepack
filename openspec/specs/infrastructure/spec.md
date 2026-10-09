# infrastructure

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: GitHub Actions CI
The project SHALL use GitHub Actions for continuous integration, triggered on pushes and pull requests to the `master` branch.

#### Scenario: Push to master
- **WHEN** code is pushed to `master`
- **THEN** the CI workflow runs automatically
- **AND** all tests pass before the push is considered successful

#### Scenario: Pull request
- **WHEN** a pull request is opened against `master`
- **THEN** the CI workflow runs on the PR branch
- **AND** test results are visible in the PR

### Requirement: Multi-Version Testing
The core CI matrix SHALL include Python 3.9, 3.10, 3.11, 3.12 and 3.13. A newer interpreter SHALL require successful core/artifact/representative-reader qualification before it is advertised as tested.

#### Scenario: Verified current contract
- **WHEN** a newer Python version is considered
- **THEN** its qualification is recorded separately from the permissive package constraint

### Requirement: Linting and Type Checking
CI SHALL run Ruff with line length 100 and configured complexity limits, and mypy on the runtime, tests and distribution validator.

#### Scenario: Verified current contract
- **WHEN** a lint or type violation is introduced
- **THEN** the relevant CI command fails

### Requirement: pyproject.toml Configuration
pyproject.toml SHALL own package metadata, dependencies and build settings. The backend SHALL require setuptools >=77.0.3 and wheel; DuckDB and native format readers SHALL be optional extras.

#### Scenario: Verified current contract
- **WHEN** the core package is installed
- **THEN** only declared core dependencies are required

### Requirement: Development Dependencies
Development dependencies SHALL be declared under `[project.optional-dependencies]` with a `dev` extra.

#### Scenario: Dev install
- **WHEN** `pip install -e ".[dev]"` is run
- **THEN** pytest, mypy, ruff, and coverage tools are installed
- **AND** the package itself is installed in editable mode

### Requirement: Tool Configuration
Tool settings SHALL be consolidated in `pyproject.toml` under `[tool.*]` sections.

#### Scenario: pytest configuration
- **WHEN** `pytest` is run
- **THEN** it reads its settings from `[tool.pytest.ini_options]`

#### Scenario: mypy configuration
- **WHEN** `mypy` is run
- **THEN** it reads its settings from `[tool.mypy]`
