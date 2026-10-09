# Change: Rebuild compressed tar archives with exactly one tar payload

## Why

The installed 7zz reproduced a tar.gz rewrite containing `bundle.tar` instead of the original `document.txt`. Extraction currently decodes a wrapper into a tar file and then re-tars that file.

## What Changes

- Represent decode, tar extraction, member optimization, tar rebuild, and stream encoding as explicit stages.
- Preserve tar member layout in both deep modes.
- Audit compound suffixes and aliases against their actual wrapper structure.

## Impact

- Priority: **P0**. Roadmap slice: **A2**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R02, A2.
- Affected capabilities: `archive-repacking`.
- Affected code: `filerepack/formats.py:SPECIAL_FAMILY`, `filerepack/archive_manifest.py`, `filerepack/repack.py:_decode_tar_payload/_extract_7z/_write_tar_bundle`, `test/test_archive_preservation.py`, archive documentation and changelog.
- Status: implemented and verified locally after the user's implementation authorization on 2026-10-02; deployment and archival remain pending.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Validation

- Compare decoded member names, types, links, and preserved payloads before and after each wrapper.
- Explicitly skip optional-codec tests when tools are absent.

## Approval and rollout

Implementation was authorized by the user's instruction to start applying the roadmap on 2026-10-02. Implementation and local verification are recorded in tasks.md. Public entry points are preserved; canonical baseline integration and deployment confirmation remain prerequisites to archival.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
