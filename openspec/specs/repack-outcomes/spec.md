# repack-outcomes

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Typed Terminal Repack Outcomes

Every known input SHALL receive a typed terminal status from replaced, unchanged, skipped, unsupported, failed, predicted, or cancelled, with a stable reason code when applicable. Outcomes SHALL identify source, effective destination, durable nested member identity, elapsed time, actual/predicted sizes, publication state, and established tool/validator guarantees. Missing tools and corrupt input SHALL NOT be counted as successful transformations.
Human repack/bulk output SHALL explicitly label successful completion, including
unchanged size rejection and dry-run, separately from errors, intentional skips
and cancellation. Optional transform skips SHALL be identified as skipped steps
rather than whole-operation errors. Error reasons SHALL be visible at normal
verbosity and in quiet mode. Completion labels SHALL agree with terminal status
and command exit codes, including report/checkpoint/scan failures. JSON/CSV
stdout SHALL retain structured reports without human status prefixes.

#### Scenario: Corrupt gzip

- **WHEN** a gzip input fails decoding
- **THEN** its outcome SHALL be failed with a decoding reason rather than processed with zero savings

#### Scenario: Missing optional tool

- **WHEN** a requested eligible transform lacks its required tool
- **THEN** the outcome SHALL distinguish unavailable support from unchanged size rejection

#### Scenario: Archive rejection and dry-run

- **WHEN** nested candidates shrink but the outer archive is rejected or is only measured
- **THEN** reports SHALL distinguish staged/predicted changes from actual outer publication

#### Scenario: Verified candidate has no size reduction

- **WHEN** a verified candidate is rejected only because it does not reduce size
- **THEN** human output SHALL explicitly label the result as successful and unchanged or predicted
- **AND** optional recompression skip details SHALL remain informational

#### Scenario: Encoding or report output fails

- **WHEN** decoding, encoding, report writing, checkpointing or scanning fails
- **THEN** human output SHALL explicitly label the failure as an error with its reason
- **AND** the command SHALL NOT claim successful completion
- **AND** quiet mode SHALL retain the error on stderr

### Requirement: Reconciled Outcome Summaries

Reports SHALL retain every known input outcome, including skipped, unsupported, failed, unchanged, and cancelled work. Counters and actual/predicted byte totals SHALL reconcile with those outcomes and SHALL NOT double-count inner and outer archive savings.

#### Scenario: Mixed batch outcomes

- **WHEN** a batch contains successes, skips, no-growth results, and failures
- **THEN** each input SHALL appear once and summary counts SHALL reconcile

#### Scenario: Unchanged output copy

- **WHEN** an explicit destination receives an unchanged validated copy
- **THEN** the outcome SHALL report unchanged with the published artifact/destination rather than a transformed source

### Requirement: Deterministic CLI Outcome Exit Codes

Single-file commands SHALL exit 0 for replaced/unchanged/intentional-skipped/predicted work, 1 for failed/unsupported/invalid requests, and 130 for user interruption. Bulk commands SHALL exit 0 for clean completion, 1 for fatal or fail-fast errors, 2 for partial errors under continue-on-error, and 130 for user interruption.

#### Scenario: Partial continue-on-error batch

- **WHEN** a batch continues after a failed or unsupported input
- **THEN** it SHALL emit complete outcomes and exit 2

#### Scenario: User interruption

- **WHEN** the user interrupts an operation
- **THEN** the command SHALL report known completed/cancelled work and exit 130
