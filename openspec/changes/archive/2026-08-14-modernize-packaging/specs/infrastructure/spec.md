## ADDED Requirements
### Requirement: pyproject.toml Configuration
The project SHALL use `pyproject.toml` as the primary configuration file for build system, dependencies, and tool settings.

#### Scenario: Build configuration
- **WHEN** `pyproject.toml` is read by pip or build tools
- **THEN** it specifies `setuptools>=68.0` and `wheel` as build requirements
- **AND** project metadata includes name, version, description, and Python version constraints

#### Scenario: Dependency declaration
- **WHEN** `pip install filerepack` is run
- **THEN** `typer>=0.9.0` is installed automatically
- **AND** `duckdb>=0.9.0` is only installed if `pip install filerepack[parquet]` is used

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
