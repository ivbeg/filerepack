# Change: Preserve specialized package structure and protected container integrity

## Why

An ODT rewrite moved mimetype away from the first entry. Broad ZIP aliases and the attempted CAB writer are not evidence of complete container preservation.

## What Changes

- Add ODF/EPUB entry-order, compression, and header policies.
- Separate generic ZIP routing from wrappers, integrity manifests, and signatures.
- Gate each advertised container writer on proven round-trip capability.
- **BREAKING**: Aliases whose format-specific rules or integrity cannot be preserved will be reported unsupported/protected instead of being rewritten as generic ZIP containers.

## Impact

- Priority: **P1**. Roadmap slice: **A6, B2, C1**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R09, R14, A6, B2, C1.
- Affected capabilities: `container-policies`.
- Affected code: `filerepack/consts.py`, `filerepack/formats.py`, `filerepack/repack.py:_write_archive/_write_infozip`, `filerepack/tools.py`, `docs/docs/formats/index.md`.
- Status: early A6 partially implemented and verified locally on 2026-10-03 (ODF/EPUB layout, control-file preservation and package-reference validation); remaining scope is open. No deployment or archival is asserted.

## Dependencies

- [fix-archive-member-preservation](../fix-archive-member-preservation/proposal.md)
- [fix-compressed-tar-roundtrip](../fix-compressed-tar-roundtrip/proposal.md)

## Validation

- Verify ODF/EPUB requirements with package-level assertions and representative application fixtures.
- Probe actual available writer commands; a backend E_NOTIMPL must never be called successful repacking.

## Approval and rollout

The user authorized implementation on 2026-10-02. The early A6 tasks are tracked separately from the remaining scope in `tasks.md`. Integration and deployment remain separate work. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
