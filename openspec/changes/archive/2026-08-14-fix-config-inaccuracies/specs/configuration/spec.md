## ADDED Requirements
### Requirement: Accurate Package Metadata
All package configuration files SHALL reference the correct package name `filerepack` and correct repository URL `https://github.com/ivbeg/filerepack`.

#### Scenario: setup.py metadata
- **WHEN** `setup.py` is read or executed
- **THEN** the `url` field is `https://github.com/ivbeg/filerepack`
- **AND** classifiers list Python 3.9+ versions only

#### Scenario: coverage configuration
- **WHEN** `coverage` is run on the project
- **THEN** it measures the `filerepack` package as specified in `.coveragerc`
- **AND** the coverage report is generated successfully

### Requirement: No Stale References
All configuration and build files SHALL use the current package name consistently, with no residual references to `filesrepack`.

#### Scenario: grep for old name
- **WHEN** searching for `filesrepack` in source and config files
- **THEN** no matches exist outside of HISTORY.md (historical record)
- **AND** all functional references use `filerepack`
