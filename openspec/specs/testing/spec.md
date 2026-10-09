# testing

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Unit Test Coverage
The test suite SHALL exercise size parsing/formatting, input filters and shared utility behavior with positive and invalid values.

#### Scenario: Verified current contract
- **WHEN** parse_size receives 1MB
- **THEN** the result is 1048576

### Requirement: CLI Integration Tests
Typer CliRunner tests SHALL verify help, valid dry-run requests, invalid requests and machine-readable terminal outcomes.

#### Scenario: Verified current contract
- **WHEN** a supported valid input is processed in dry-run mode
- **THEN** the original bytes are retained and the result declares no publication

### Requirement: Test Infrastructure
The project SHALL use pytest and pytest-cov. Explicit coverage runs SHALL measure filerepack lines and branches; ordinary pytest SHALL discover test/ without requiring a coverage invocation.

#### Scenario: Verified current contract
- **WHEN** pytest is invoked with --cov=filerepack
- **THEN** the report covers the application package
