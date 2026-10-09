# code-quality

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Type Annotations
Public requests, outcomes, worker messages and shared publication interfaces SHALL have type annotations checked by the configured mypy lane. Heterogeneous compatibility option mappings SHALL remain explicitly supported.

#### Scenario: Verified current contract
- **WHEN** a typed public request is checked
- **THEN** mypy enforces the declared field types

### Requirement: Static Type Checking
The project SHALL run `mypy` as part of the CI pipeline to enforce type correctness.

#### Scenario: Type error detection
- **WHEN** a type error is introduced (e.g., passing `str` where `int` is expected)
- **THEN** `mypy` reports the error before the code is merged

#### Scenario: CI pipeline
- **WHEN** a pull request is opened
- **THEN** the CI runs `mypy filerepack/` and fails on any type errors

### Requirement: Immutable Default Arguments
Functions SHALL avoid shared mutable default option arguments. Omitted options SHALL create isolated effective settings and explicit caller options SHALL not be contaminated by a preceding call.

#### Scenario: Verified current contract
- **WHEN** a caller invokes a packer twice without options
- **THEN** the calls do not share mutable option state

### Requirement: No Redundant CLI Entry Points
The filerepack console script SHALL point to filerepack.__main__:main through pyproject.toml and expose the Typer CLI.

#### Scenario: Verified current contract
- **WHEN** the installed console command is invoked
- **THEN** it opens the supported Typer commands

### Requirement: Single README Format
The project SHALL maintain README documentation in Markdown format only. Outdated reStructuredText README files SHALL be removed.

#### Scenario: README access
- **WHEN** viewing the project on GitHub or PyPI
- **THEN** `README.md` is rendered as the project description
- **AND** no outdated `README.rst` exists to confuse contributors

### Requirement: Clean Build Artifacts
Generated build, distribution and documentation outputs SHALL be excluded from version control. Source changes SHALL not be erased merely to obtain a clean git status.

#### Scenario: Verified current contract
- **WHEN** distribution validation builds artifacts
- **THEN** the artifacts do not become application source files
