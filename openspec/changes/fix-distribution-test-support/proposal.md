# Change: Include complete test support in source distributions

## Why

The built source distribution includes tests but omits conftest, package initialization, DICOM fixtures, and the new local helper. Collection fails although the wheel/sdist build succeeds.

## What Changes

- Include all supporting test modules and configuration in source artifacts.
- Add build/extract/collection and installed-wheel smoke checks.
- Align license metadata with BSD-3-Clause using a compatible backend.

## Impact

- Priority: **P1**. Roadmap slice: **A7**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R15, A7.
- Affected capabilities: `distribution-validation`.
- Affected code: `pyproject.toml`, `setup.py`, `test/conftest.py`, `test/dicom_fixtures.py`, `test/helpers.py`, `.github/workflows/ci.yml`, `LICENSE`.
- Status: implemented and verified locally on 2026-10-03; artifact CI gates are configured. No remote CI run, release, deployment or archival is asserted.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Validation

- Assert test helper files are present in the sdist and absent from the runtime wheel.
- Run artifact validation using fresh temporary environments with required test dependencies.

## Approval and rollout

The user authorized implementation on 2026-10-02. Implementation and local verification tasks are complete; canonical integration and deployment remain separate work. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
