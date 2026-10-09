## Context

Corrupt gzip work is counted as processed; unsupported/missing-tool/unchanged/failed results collapse together. Bulk JSON includes ordinary stdout text and omits skip/failure details.

This design covers R11, R15, B3, C5 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add typed per-input/nested outcomes with stable statuses/reasons and actual destinations/timing.
- Goal: Reconcile outer archive publication separately from staged nested savings.
- Goal: Reserve stdout for JSON/CSV and route human diagnostics to stderr.
- Goal: Define exit codes and reset per-invocation verbosity/logging state.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Statuses are replaced, unchanged, skipped, unsupported, failed, predicted, and cancelled. Reasons distinguish size rejection, disabled/protected paths, missing tools, corrupt input, conflict, budget, and verification failure.
2. Distinct unchanged output copies retain status unchanged with a published-artifact marker; replaced denotes an accepted transformation.
3. Dry-run reports predicted sizes and staged nested effects, never published replacements.
4. Single-file exit codes: 0 for successful/unchanged/intentional-skip/predicted, 1 for failed/unsupported/invalid requests, 130 for user interruption. Bulk: 0 clean, 1 fatal/fail-fast, 2 partial errors under continue-on-error, 130 user interruption.
5. Preserve existing PackResult/RepackSummary exports and legacy mapping keys; serialize through a versioned additive schema.
6. Default requested log files record normal CLI messages and invocation state resets without leaking prior handlers/options.

## Risks / Trade-offs

- Consumers may depend on old JSON shape or success counts; document additive fields and explicit schema/exit-code migration.

## Migration Plan

1. Keep legacy summary mapping and established fields as compatibility projections.
2. Keep stderr progress and optional logs separate from serialized stdout; CSV emits all terminal outcomes with status/reason.

## Verification

- Parse plain JSON/CSV without --quiet under success, failure, dry-run, progress, and skips.
- Verify legacy mapping/API tests and exact summary reconciliation.
