## ADDED Requirements
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
The CI SHALL test the project against Python 3.9, 3.10, 3.11, and 3.12 via a build matrix.

#### Scenario: Python 3.9
- **WHEN** tests run on Python 3.9
- **THEN** they pass without version-specific failures

#### Scenario: Python 3.12
- **WHEN** tests run on Python 3.12
- **THEN** they pass without version-specific failures

### Requirement: Linting and Type Checking
The CI SHALL run linting and type checking in addition to tests.

#### Scenario: Lint check
- **WHEN** `flake8` runs on the codebase
- **THEN** it reports no style violations (max line length 100)

#### Scenario: Type check
- **WHEN** `mypy` runs on the codebase
- **THEN** it reports no type errors
