# resumable-bulk

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Versioned Atomic Bulk Checkpoints

The system SHALL support bulk checkpointing through `--manifest FILE` and resumption through `--resume`. A single coordinator SHALL publish locked, versioned checkpoints atomically on the manifest filesystem, exclude checkpoint paths from discovery, and validate schema, roots, and source/output/report/backup collisions before processing. Corrupt or incompatible resume manifests SHALL fail before processing writes.

#### Scenario: Checkpoint update is interrupted

- **WHEN** a process stops during replacement of a manifest checkpoint
- **THEN** the prior complete checkpoint remains readable or the new complete checkpoint is present
- **AND** no partially written checkpoint is accepted as completion

#### Scenario: Conflicting or corrupt manifest

- **WHEN** a requested manifest aliases an input or contains invalid schema data
- **THEN** the invocation fails before compression/publication and explains the conflict

#### Scenario: Concurrent resume attempts

- **WHEN** two invocations try to update the same manifest
- **THEN** only one holds the writer lock and the other fails visibly without changing the checkpoint

### Requirement: Content and Execution Verified Resume

The system SHALL reuse only verified completed replaced or unchanged outcomes whose content, destination, effective options, tools, and capability/preservation-policy fingerprints match current execution. In-place success SHALL be verified against the post-publication source state; distinct-output success SHALL verify both original source and published output. Size, timestamps, or inode identity alone SHALL NOT authorize reuse.

#### Scenario: Unmodified completed in-place result

- **WHEN** resume finds a verified completed in-place item with matching current post-publication bytes and execution fingerprint
- **THEN** the item is reused without another compression pass

#### Scenario: Equal-size source change

- **WHEN** source bytes change while size and timestamps remain equal to the checkpoint
- **THEN** content verification invalidates reuse and current bytes are re-planned

#### Scenario: Output or execution changes

- **WHEN** a distinct output is removed/edited or effective options or tool/policy versions change
- **THEN** the item is invalidated with an explicit reason and normal destination safety rules apply

### Requirement: Resume Outcome and Savings Accounting

Resume SHALL re-evaluate failed, cancelled, predicted, unsupported, skipped, and incomplete items. Safely reused results SHALL be explicitly identified in reports and SHALL NOT count historical saved bytes as newly achieved savings. Dry-run SHALL NOT persist new completed checkpoint states; checkpoint failures SHALL produce non-success invocation status.

#### Scenario: Interrupted work is resumed

- **WHEN** a manifest contains completed items and cancelled or failed items
- **THEN** only verified eligible completion is reused and remaining items enter normal processing

#### Scenario: Historical saving is reported

- **WHEN** a previously optimized file is reused from a manifest
- **THEN** the report identifies reused completion and the current run's saved bytes exclude the earlier optimization

#### Scenario: Publication preceded checkpoint failure

- **WHEN** output publication succeeded but persisting its checkpoint failed
- **THEN** the invocation reports checkpoint failure and retains the true publication outcome
- **AND** a later run uses normal validation and collision handling instead of trusting a missing completion entry
