# Change: Centralize typed candidate transactions and destination-local publication

## Why

Candidates are created in system temp storage, inode replacement changes permissions, and codec modules reach into repack.py through dynamic Any imports. Publication and subprocess policy need one portable typed lifecycle.

## What Changes

- Move staging, command execution, validation/acceptance, and publication behind shared typed internal interfaces.
- Publish verified candidates using destination-local staging and retain declared filesystem metadata.
- Detect source changes and define symlink/hardlink and crash-durability policies.
- Split codec families incrementally while preserving public import paths.

## Impact

- Priority: **P1**. Roadmap slice: **B1, C5**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R10, B1, C5.
- Affected capabilities: `repack-transactions`.
- Affected code: `filerepack/repack.py`, `filerepack/codecs.py`, shared `candidates.py`/`transactions.py`/`commands.py`, format-family modules, `dispatch.py`, `containers.py`, `jobs.py`, `models.py` and `pyproject.toml:tool.mypy`.
- Status: implementation is complete and verified locally on 2026-10-03. Shared staging/acceptance/publication and command interfaces, family relocation, compatibility exports and core/worker typing are in use. Linux/Windows and actual second-filesystem evidence remain open, so the overall change remains partial. No deployment or archival is asserted.

## Dependencies

- [fix-output-destination-safety](../fix-output-destination-safety/proposal.md)

## Validation

- Test destination-local atomic publication and source preservation on failures across supported filesystems.
- Run import/API compatibility, dry-run, lint/type, and focused codec regressions.

## Approval and rollout

The user authorized roadmap implementation on 2026-10-02. The checked tasks record local evidence; the remaining platform and rollout tasks stay open. Existing public helpers retain their imports/signatures. Linked in-place sources now fail explicitly under the reviewed filesystem policy; distinct outputs remain available.
