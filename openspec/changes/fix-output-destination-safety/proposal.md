# Change: Protect destinations and honor standalone library output paths

## Why

The CLI overwrites outputs before rejecting invalid options; conversions can overwrite unrelated targets, and the standalone library ignores `outfile` and modifies its source.

## What Changes

- Validate and normalize options and identities before backups, copies, or encoding.
- Centralize CLI/library output and conversion destinations with default collision refusal.
- Reserve backup/output paths; requested-backup failure prevents destructive work.
- Define outfile, unchanged-copy, and dry-run behavior.
- **BREAKING**: Existing different destinations and backups will no longer be overwritten implicitly; overwrite requires an explicit policy. Invalid options will be rejected before writes.

## Impact

- Priority: **P0**. Roadmap slice: **A4**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R04, R07, R15, A4.
- Affected capabilities: `publish-destinations`.
- Affected code: `filerepack/__main__.py:repack/bulk`, `filerepack/jobs.py`, `filerepack/repack.py:repack_zip_file/_pack_video/_repack_rar`, `filerepack/utils.py:parse_size/create_backup`.
- Status: implemented and verified locally on 2026-10-03; canonical integration and deployment remain open.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Validation

- Verify hashes on invalid options, collisions, and backup failure.
- Exercise JSON/stream/archive outfile directly and through the CLI.

## Approval and rollout

The user authorized roadmap implementation on 2026-10-02 and continued it on 2026-10-03. Implementation and local verification tasks are complete. CLI and library now require explicit `overwrite` for an existing distinct output; required backups remain protected. Distinct `outfile` processing preserves the source, including when the result is an unchanged copy. These compatibility changes are documented. Canonical integration, deployment and archival remain the separate unchecked rollout task.

Local verification: 561 tests passed, 1 skipped, including 116 new output-safety cases. Ruff, mypy, strict OpenSpec validation, the documentation build, wheel build and wheel import/output smoke check passed.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
