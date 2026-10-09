# Change: Verify preservation, platforms, extras, and the canonical specification baseline

## Why

CI covers Ubuntu/core dependencies and tests can pass without doing integration work. Canonical specs are absent, completed changes remain active, and project guidance describes a no-test monolith.

## What Changes

- Add real preservation fixtures, explicit integration skips, fault/property tests, and meaningful coverage gates.
- Exercise optional extras, installed artifacts, macOS/Windows, and declared Python versions.
- Create a fixed benchmark corpus and record fidelity/time/memory/scratch/savings evidence.
- Reconcile verified existing requirements and update project guidance without claiming future work deployed.

## Impact

- Priority: **P2**. Roadmap slice: **C2, C3, C6**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R15, C2, C3, C6.
- Affected capabilities: `quality-gates`, `spec-governance`.
- Affected code: `test/`, `.github/workflows/ci.yml`, `pyproject.toml`, `openspec/project.md`, `openspec/changes/`, `openspec/specs/`, `CONTRIBUTING.md`, `docs/docs/development/contributing.md`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [fix-distribution-test-support](../fix-distribution-test-support/proposal.md)

## Validation

- Run strict OpenSpec validation and reject duplicate/conflicting requirement ownership.
- Provision real optional integrations and verify artifact/platform failures cannot be masked by checkout imports or early returns.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
