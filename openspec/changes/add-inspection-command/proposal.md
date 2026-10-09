# Change: Add bounded read-only file inspection and operation planning

## Why

Current dry-run performs candidate compression to measure savings. Users need an inexpensive way to learn which operations are eligible, what is missing, and which known protection or destination rules will prevent processing before starting a costly job.

## What Changes

- Add `filerepack inspect PATH --json` for a file or directory with bounded read-only discovery.
- Describe detected format, available writers/validators, tools/extras, known protection state, destination conflicts, and estimated resource needs.
- Separate estimates and unknown information from measurements; retain existing dry-run candidate measurement.

## Impact

- Priority: **P1**. Roadmap slice: **D — inspection**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); N01.
- Affected capabilities: `inspection`.
- Affected code: `filerepack/__main__.py`, `filerepack/formats.py`, `filerepack/tools.py`, `filerepack/models.py`, `filerepack/utils.py`, `docs/docs/commands/`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [refactor-format-capability-registry](../refactor-format-capability-registry/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)
- [add-operation-resource-budgets](../add-operation-resource-budgets/proposal.md)

## Validation

- Use spies and filesystem snapshots to prove inspection starts no encoder and creates no source/output/backup/scratch files.
- Cover known signed/encrypted packages, missing tools/extras, unsupported aliases, ambiguous headers, and pre-existing destination conflicts.
- Validate JSON parsing with diagnostics and interrupted directory discovery; verify bounded reader/probe behavior.
- Compare inspected routing/options against later repack planning without requiring estimated savings to equal measured results.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
