# Change: Preserve complete archive member sets

## Why

The review reproduced a ZIP rewrite that discarded a root dotfile and accepted the smaller incomplete archive. Bare-star expansion and signature-only checks do not establish that every intended member survived.

## What Changes

- Enumerate all members, including hidden paths and empty directories, without shell globbing.
- Compare intended and candidate member manifests before publication.
- Handle option-like names, duplicate paths, link types, and archive metadata explicitly.

## Impact

- Priority: **P0**. Roadmap slice: **A1**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R01, A1.
- Affected capabilities: `archive-repacking`.
- Affected code: `filerepack/archive_manifest.py`, `filerepack/repack.py:_expand_globs/_write_archive/_write_infozip/_verify_archive_candidate`, `test/test_archive_preservation.py`, `test/test_repack_integration.py`, archive documentation and changelog.
- Status: implemented and verified locally after the user's implementation authorization on 2026-10-02; deployment and archival remain pending.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Validation

- Run real available ZIP/7z/tar and Info-ZIP round-trips; missing tools must skip explicitly.
- Assert rejected candidates leave original bytes unchanged.

## Approval and rollout

Implementation was authorized by the user's instruction to start applying the roadmap on 2026-10-02. Implementation and local verification are recorded in tasks.md. Public entry points are preserved; canonical baseline integration and deployment confirmation remain prerequisites to archival.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
