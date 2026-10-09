# configuration

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Accurate Package Metadata
pyproject.toml SHALL declare the filerepack name, ivbeg/filerepack repository, BSD-3-Clause license and Python >=3.9 constraint. CI SHALL qualify Python 3.9 through 3.13.

#### Scenario: Verified current contract
- **WHEN** a built distribution is inspected
- **THEN** its metadata and license match the source declarations

### Requirement: No Stale References
Functional package/build configuration SHALL use filerepack consistently. Historical documents and specification audits MAY quote obsolete names.

#### Scenario: Verified current contract
- **WHEN** coverage and package discovery run
- **THEN** both select filerepack
