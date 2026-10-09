# audit-reporting

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Versioned Complete Audit Records

The system SHALL support `--report FILE` in JSON and JSONL forms with an explicit schema version. Reports SHALL record every discovered input's terminal outcome and relevant nested member events, stable identities, source/destination, selected tools and versions, effective settings, validation results, timing, publication state, and separate actual/predicted size information.

#### Scenario: All outcomes are auditable

- **WHEN** a batch includes replaced, unchanged, skipped, unsupported, failed, predicted, and cancelled inputs
- **THEN** the report contains their distinct outcomes and reconciled summary
- **AND** nested member savings are distinguished from final container savings

#### Scenario: Validation explains acceptance

- **WHEN** a candidate is rejected by structural validation
- **THEN** the item record identifies the verifier and rejection reason and shows no publication

### Requirement: Bounded and Recoverable Report Persistence

Report generation SHALL use bounded memory. JSONL SHALL flush complete records at item boundaries and mark orderly completion or abort in a final summary. JSON SHALL use bounded spooling and atomic final publication. Incomplete reports SHALL be distinguishable from completed reports; previously complete JSONL records SHALL remain readable after an interrupted trailing write.

#### Scenario: Interrupted streaming report

- **WHEN** a job stops before its final summary or during the last JSONL record
- **THEN** a reader can recover earlier complete records and identifies the report as incomplete

#### Scenario: Orderly cancellation

- **WHEN** a running batch is cancelled and workers drain
- **THEN** the finalized report contains accounted terminal outcomes and an aborted summary

#### Scenario: Report persistence fails

- **WHEN** the requested report cannot be written or finalized
- **THEN** the command returns a non-success invocation status and reports the write failure
- **AND** already published file outcomes remain accurately recorded and are not silently rolled back

### Requirement: Report Destination and Path Disclosure Policy

The system SHALL reserve and validate report destinations before processing, refuse collisions with source/output/backup paths or occupied report targets by default, and exclude reports and spools from discovery. Reports SHALL remain local and provide documented absolute, run-relative, and redacted path policies; redaction SHALL also remove path-bearing diagnostic text.

#### Scenario: Report target is an input

- **WHEN** the report resolves to a source path or reserved output
- **THEN** validation fails before any processing writes

#### Scenario: Redacted local report

- **WHEN** a user selects redacted paths for a job containing private names
- **THEN** records use opaque identities and contain no source/member names or path-bearing errors
- **AND** report content is not transmitted to an external service
