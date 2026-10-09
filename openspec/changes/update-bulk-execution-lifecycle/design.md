## Context

The runner submits every input at once. Fail-fast breaks result consumption while queued/running jobs can continue writing, and output/backup subtrees and shared destinations are not managed centrally.

This design covers R12, B4 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Scan incrementally and bound outstanding work.
- Goal: Reserve destinations and exclude resolved output/backup trees.
- Goal: Stop submissions, cancel pending jobs, and manage running processes explicitly.
- Goal: Emit complete known-input outcomes on failure or interruption.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. The coordinator owns path reservations and input/output/backup exclusions; workers cannot race check-then-copy backup names.
2. Bound in-flight futures to a documented multiple of workers, default two, and do not materialize every discovered input in memory.
3. On fail-fast, stop scanning/submission, cancel pending work, request cooperative cancellation of running work, drain all known outcomes, and wait for publication ownership to be released.
4. Do not claim cancellation succeeded while encoders continue writing; subprocess ownership is integrated with the transaction lifecycle.

## Risks / Trade-offs

- Already running work can finish before cancellation is observed; report its actual result and preserve publication invariants.
- Streaming discovery cannot report unvisited files as known inputs; distinguish known inputs from scan completeness.

## Migration Plan

1. Retain --jobs and --continue-on-error names and serial mode.
2. Keep deterministic outcome identities without requiring completion-order reports to match input order.

## Verification

- Stress a large synthetic scan and assert the documented in-flight bound.
- Assert no unreported completed write and no target/backup conflict under competing workers.
