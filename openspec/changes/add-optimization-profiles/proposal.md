# Change: Add versioned optimization profiles and predictable execution budgets

## Why

Users currently combine compression level, ultra, metadata, quality, worker and extraction settings manually. Named profiles should resolve to reproducible effective options, make effort/time trade-offs understandable, and keep costly inputs within shared budgets without implicitly enabling loss.

## What Changes

- Add `--profile fast|balanced|maximum|preserve` and equivalent library selection with versioned definitions.
- Resolve profile defaults before explicitly supplied CLI/library overrides; expose effective options and definition version.
- Add per-input timeout/temp-space and worker/tool-thread controls integrated with the shared resource context.
- Benchmark profile trade-offs on a fixed corpus without promising unmeasured savings.

## Impact

- Priority: **P2**. Roadmap slice: **D — profiles**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); N04.
- Affected capabilities: `optimization-profiles`.
- Affected code: `filerepack/models.py:RepackOptions`, `filerepack/__main__.py:_build_options/repack/bulk`, `filerepack/repack.py:_normalize_options/_dispatch_packer`, `filerepack/tools.py`, `filerepack/jobs.py`, `docs/docs/commands/shared-options.md`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [add-operation-resource-budgets](../add-operation-resource-budgets/proposal.md)
- [update-media-preservation-policy](../update-media-preservation-policy/proposal.md)
- [refactor-format-capability-registry](../refactor-format-capability-registry/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)
- [update-quality-and-specification-gates](../update-quality-and-specification-gates/proposal.md)

## Validation

- Check the exact profile version 1 settings and precedence for explicit false/default-valued CLI and library overrides.
- Verify none of the profiles alone selects lossy video/image/PDF paths and preserve retains requested metadata or explicitly skips incapable writers.
- Exercise nested option inheritance and cumulative worker/tool-thread/temp/deadline enforcement.
- Record elapsed time, peak memory/scratch, accepted candidates and final bytes saved for the same corpus/tool versions.
- Ensure changes to profile definitions or adapters invalidate execution fingerprints where resume is available.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
