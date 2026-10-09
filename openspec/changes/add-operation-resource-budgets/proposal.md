# Change: Enforce cumulative decode, nesting, scratch, and process budgets

## Why

RAR size checks occur after extraction, nested archives receive fresh limits, standalone/PSD decompression is unbounded, and stream peeking can block without a read deadline.

## What Changes

- Carry an operation context through nested packers, asset walkers, validators, and subprocesses.
- Enforce root-input cumulative decoded bytes/member/depth/deadline budgets and shared live batch scratch/memory/CPU policy.
- Validate extraction member identities and link containment.
- Bound stream peeking, decoder output, subprocess logs, and cancellation.
- **BREAKING**: Limits will apply to standalone and nested decoding, not only estimated top-level archive extraction. Unsafe paths/links and exceeded budgets will stop work rather than proceed.

## Impact

- Priority: **P1**. Roadmap slice: **B5**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R13, B5.
- Affected capabilities: `operation-budgets`.
- Affected code: `filerepack/repack.py:_pack_stream_codec/_pack_pipe_codec/_extract_7z/_extract_rar/_deep_walk`, `filerepack/formats.py:_peek_cli_tar`, `filerepack/codecs.py:_rezip_payload`, `filerepack/containers.py`, `filerepack/jobs.py`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [refactor-repack-transactions](../refactor-repack-transactions/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)
- [update-bulk-execution-lifecycle](../update-bulk-execution-lifecycle/proposal.md)

## Validation

- Assert budget failures preserve sources and release process/scratch reservations.
- Measure memory/scratch behavior and document external monitoring bounds rather than claim unsupported hard guarantees.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
