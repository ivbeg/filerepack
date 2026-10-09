# Change: Add safe checkpoint manifests and resumable bulk processing

## Why

Interrupted large jobs repeat completed compression work. Resume must distinguish genuine completed publication from stale outcomes caused by changed sources, outputs, effective options, toolchains, or policy versions, including the special case where successful in-place processing changes the source itself.

## What Changes

- Add `--manifest FILE` checkpointing and `--resume` for bulk jobs.
- Reuse completed outcomes only after source/output content and effective execution fingerprints match.
- Publish checkpoints atomically, protect manifest destinations, and make stale/corrupt state observable.

## Impact

- Priority: **P2**. Roadmap slice: **D — resume**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); N03.
- Affected capabilities: `resumable-bulk`.
- Affected code: `filerepack/__main__.py:bulk/_run_bulk_jobs`, `filerepack/jobs.py`, `filerepack/models.py`, `filerepack/tools.py`, `filerepack/utils.py`, `docs/docs/commands/bulk.md`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [add-audit-reports](../add-audit-reports/proposal.md)
- [update-bulk-execution-lifecycle](../update-bulk-execution-lifecycle/proposal.md)
- [fix-output-destination-safety](../fix-output-destination-safety/proposal.md)

## Validation

- Interrupt a batch and resume; verify completed matching inputs do not re-encode while incomplete ones are processed.
- Change bytes without changing size/time, effective options, tool version/path, policy version, and output destination; verify each invalidates reuse.
- Test in-place post-publication identity and distinct-output deletion/modification; prevent stale success or unrelated overwrite.
- Inject checkpoint replacement failure/crash and simultaneous writers; preserve a valid prior manifest and safe normal collision behavior.
- Cover malformed/unsupported manifests, aliases to inputs/outputs/reports, dry-run read-only behavior, and reconciled resumed accounting.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
