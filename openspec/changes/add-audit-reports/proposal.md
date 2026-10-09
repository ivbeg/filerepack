# Change: Add persistent versioned audit reports for every processing outcome

## Why

Console summaries and current JSON/CSV output do not provide a durable explanation of every skipped, failed, nested, or interrupted operation. A local report should let users trace what was attempted, why publication happened, and which tools and policies were used.

## What Changes

- Add `--report FILE` with JSON and streaming JSONL formats for repack and bulk.
- Persist versioned terminal outcomes and nested member records with settings, tools, validators, timing, source/destination identity, and actual versus predicted sizes.
- Record partial/aborted completion with bounded memory and explicit local path disclosure and write failure behavior.

## Impact

- Priority: **P2**. Roadmap slice: **D — audit**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); N02.
- Affected capabilities: `audit-reporting`.
- Affected code: `filerepack/__main__.py:repack/bulk`, `filerepack/models.py`, `filerepack/jobs.py`, `filerepack/utils.py:output_json/output_csv`, `filerepack/progress.py`, `docs/docs/commands/`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [update-repack-outcomes](../update-repack-outcomes/proposal.md)
- [update-bulk-execution-lifecycle](../update-bulk-execution-lifecycle/proposal.md)
- [fix-output-destination-safety](../fix-output-destination-safety/proposal.md)

## Validation

- Parse JSON and JSONL reports for all typed statuses, nested members, dry-run predictions, and serial/parallel jobs.
- Inject interruption, process termination/truncated line, disk-full, and final replacement failure; verify partial versus complete state and non-success exit.
- Check bounded report memory across many records and clean machine-readable stdout alongside stderr diagnostics.
- Verify occupied paths, source/target aliases, report discovery exclusion, and redaction of names and path-bearing errors.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
