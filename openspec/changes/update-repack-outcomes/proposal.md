# Change: Expose typed outcomes and clean machine-readable CLI output

## Why

Corrupt gzip work is counted as processed; unsupported/missing-tool/unchanged/failed results collapse together. Bulk JSON includes ordinary stdout text and omits skip/failure details.

## What Changes

- Add typed per-input/nested outcomes with stable statuses/reasons and actual destinations/timing.
- Reconcile outer archive publication separately from staged nested savings.
- Reserve stdout for JSON/CSV and route human diagnostics to stderr.
- Define exit codes and reset per-invocation verbosity/logging state.

## Impact

- Priority: **P1**. Roadmap slice: **B3, C5**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R11, R15, B3, C5.
- Affected capabilities: `repack-outcomes`, `cli-reporting`.
- Affected code: `filerepack/models.py`, `filerepack/jobs.py`, `filerepack/repack.py:repack_zip_file/_process_walk_item`, `filerepack/__main__.py:_BulkAcc/_emit_bulk_summary/_setup_log`, `filerepack/utils.py:output_json/output_csv`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Validation

- Parse plain JSON/CSV without --quiet under success, failure, dry-run, progress, and skips.
- Verify legacy mapping/API tests and exact summary reconciliation.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
