## ADDED Requirements
### Requirement: Unit Test Coverage
The system SHALL have unit tests covering all pure utility functions in `utils.py` and all constant definitions in `consts.py`.

#### Scenario: parse_size tests
- **WHEN** `parse_size()` is called with "1MB"
- **THEN** it returns 1048576
- **AND** calling it with "500KB" returns 512000

#### Scenario: format_size tests
- **WHEN** `format_size()` is called with 1048576
- **THEN** it returns "1.0 MB"

#### Scenario: should_process_file tests
- **WHEN** a file matches the extension filter and is within size limits
- **THEN** `should_process_file()` returns True
- **AND** when the extension is not in the filter, it returns False

### Requirement: CLI Integration Tests
The system SHALL have integration tests verifying CLI command behavior using Typer's `CliRunner`.

#### Scenario: Help command
- **WHEN** `--help` is passed to the `repack` command
- **THEN** the output includes all option flags and descriptions

#### Scenario: Dryrun mode
- **WHEN** `--dryrun` is passed with a file path
- **THEN** the command exits with code 0
- **AND** no file is modified

### Requirement: Test Infrastructure
The project SHALL use `pytest` as the test runner with `pytest-cov` for coverage reporting.

#### Scenario: Running tests
- **WHEN** `pytest` is run from the project root
- **THEN** all tests in the `test/` directory are discovered and executed
- **AND** a coverage report is generated for the `filerepack` package

#### Scenario: Coverage configuration
- **WHEN** coverage is run
- **THEN** it measures the `filerepack` package (not `filesrepack`)
- **AND** the report includes line and branch coverage
