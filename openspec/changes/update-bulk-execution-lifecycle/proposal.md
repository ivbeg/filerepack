# Change: Bound bulk scheduling and account for cancellation and conflicts

## Why

The runner submits every input at once. Fail-fast breaks result consumption while queued/running jobs can continue writing, and output/backup subtrees and shared destinations are not managed centrally.

## What Changes

- Scan incrementally and bound outstanding work.
- Reserve destinations and exclude resolved output/backup trees.
- Stop submissions, cancel pending jobs, and manage running processes explicitly.
- Emit complete known-input outcomes on failure or interruption.

## Impact

- Priority: **P1**. Roadmap slice: **B4**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R12, B4.
- Affected capabilities: `bulk-execution`.
- Affected code: `filerepack/__main__.py:_collect_bulk_files/_run_bulk_jobs/_BulkAcc`, `filerepack/jobs.py`, `filerepack/utils.py:create_backup/parse_jobs`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [fix-output-destination-safety](../fix-output-destination-safety/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)

## Validation

- Stress a large synthetic scan and assert the documented in-flight bound.
- Assert no unreported completed write and no target/backup conflict under competing workers.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
