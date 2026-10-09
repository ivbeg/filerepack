## Context

CI covers Ubuntu/core dependencies and tests can pass without doing integration work. Canonical specs are absent, completed changes remain active, and project guidance describes a no-test monolith.

This design covers R15, C2, C3, C6 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add real preservation fixtures, explicit integration skips, fault/property tests, and meaningful coverage gates.
- Goal: Exercise optional extras, installed artifacts, macOS/Windows, and declared Python versions.
- Goal: Create a fixed benchmark corpus and record fidelity/time/memory/scratch/savings evidence.
- Goal: Reconcile verified existing requirements and update project guidance without claiming future work deployed.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Platform lanes can use representative Python versions while Ubuntu retains the core supported-version matrix; extras lanes must include genuine parsing/encoding cases.
2. Unavailable optional integration uses explicit pytest.skip with reasons; provisioned expected tools failing to work cause failure, not skip or early pass.
3. Coverage starts from the measured 62% and ratchets toward 75%; preservation assertions remain release gates even if numeric coverage passes.
4. Baseline reconciliation audits all completed/archived changes, records discrepancies such as unimplemented Flate PDF walking, and populates only verified current contracts. Rebase MODIFIED blocks to those named requirements before archive.
5. Archive existing completed changes only after deployment status is established; this proposal does not assert that a completed task checklist is deployment evidence.

## Risks / Trade-offs

- A broad platform/extra matrix is expensive; use focused fixtures per lane and keep contract-critical cases mandatory.
- Historical specifications include inaccurate examples; reconcile against code and evidence rather than blindly copying them.

## Migration Plan

1. Keep existing tooling and docs deployment; add gates incrementally.
2. Preserve historical reports/changes and identify this roadmap as proposed future work, with a separate verified current baseline.

## Verification

- Run strict OpenSpec validation and reject duplicate/conflicting requirement ownership.
- Provision real optional integrations and verify artifact/platform failures cannot be masked by checkout imports or early returns.
