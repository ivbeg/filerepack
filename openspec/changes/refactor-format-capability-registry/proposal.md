# Change: Unify format metadata and validate tool and extra capabilities

## Why

Extension, alias, packer, tool, validator, and documentation tables are separate. Doctor accepts nonexistent overrides as ok and does not reveal write support or Python extras; old Python can silently ignore TOML.

## What Changes

- Use typed format records for aliases, families, fidelity, required tools/extras, validators, output policy, and tested support.
- Validate configured executables and expose tool versions plus per-format read/write capability.
- Generate capability documentation and consistency checks from registry metadata.
- Make Python 3.9/3.10 TOML fallback a declared tested dependency.

## Impact

- Priority: **P2**. Roadmap slice: **C1, C5**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R14, R15, C1, C5.
- Affected capabilities: `format-capabilities`.
- Affected code: `filerepack/consts.py`, `filerepack/formats.py`, `filerepack/repack.py:_PACKERS`, `filerepack/tools.py`, `filerepack/install_hints.py`, `pyproject.toml`, `docs/docs/formats/index.md`, `docs/docs/tools/index.md`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [update-container-format-policies](../update-container-format-policies/proposal.md)
- [add-structural-output-validation](../add-structural-output-validation/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)

## Validation

- Nonexistent overrides must never report ok; unsupported CAB writers remain unavailable.
- Compare derived aliases/filters with current compatibility fixtures and generated docs.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
