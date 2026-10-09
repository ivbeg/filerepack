# cli-reporting

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Machine Readable Standard Output

JSON/CSV modes SHALL emit only the selected serialized report on stdout at every verbosity. Human diagnostics, progress, and errors SHALL use stderr. CSV SHALL include status/reason fields for all outcomes rather than omit failures and skips.

#### Scenario: Bulk JSON with progress and dry-run

- **WHEN** bulk runs with JSON, dry-run, and requested progress
- **THEN** stdout SHALL parse as one report without scanning or progress prefixes

#### Scenario: CSV failures

- **WHEN** a CSV-mode batch has failed and skipped inputs
- **THEN** those outcomes SHALL be represented as parseable rows

### Requirement: Isolated Invocation Logging State

Each CLI invocation SHALL initialize output/verbosity/logging state independently. A requested log file SHALL record normal operational messages by default, and later invocations SHALL NOT inherit prior logging destinations or handlers.

#### Scenario: Repeated CLI invocation

- **WHEN** one invocation uses a log file and the next does not
- **THEN** the second SHALL not write to the first invocation's log

#### Scenario: Normal log request

- **WHEN** a normal-verbosity operation requests a log file
- **THEN** its normal operational messages SHALL be recorded
