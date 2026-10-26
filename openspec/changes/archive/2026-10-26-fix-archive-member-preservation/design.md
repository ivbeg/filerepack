## Context

The review reproduced a ZIP rewrite that discarded a root dotfile and accepted the smaller incomplete archive. Bare-star expansion and signature-only checks do not establish that every intended member survived.

This design covers R01, A1 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Enumerate all members, including hidden paths and empty directories, without shell globbing.
- Goal: Compare intended and candidate member manifests before publication.
- Goal: Handle option-like names, duplicate paths, link types, and archive metadata explicitly.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Use a typed member manifest for identity, entry type, size, and preservation-relevant metadata; content changes authorized by nested packers are recorded in the intended manifest.
2. Use each writer's safe list-file or argument interface; do not assume every tool accepts the same end-of-options marker.
3. Skip containers with duplicate or case-colliding member identities when a writer cannot preserve their distinctions.
4. ZIP and tar source/candidate readers use the standard library and streamed SHA-256/CRC identities. Other tool-backed archives bind listed members to verified extracted bytes and validate the candidate through a second extraction. Only accepted nested packer results may update an existing intended file payload; unreported edits, renamed/missing entries and extra members reject the rebuild.
5. ZIP candidates are streamed into an archive with the original member order, attributes, timestamps, extra fields and comments before final verification. Tar uses original TarInfo/PAX records. The initial supported types are regular files and directories; links, sparse entries, encrypted ZIP members and unsafe/ambiguous paths skip explicitly. This is a member-preservation contract; application-specific package integrity remains update-container-format-policies work.

## Risks / Trade-offs

- Some archive metadata cannot round-trip through generic tools; reject unsupported cases instead of equating a smaller file with success.
- Payload hashing, candidate decoding and ZIP metadata reconstruction add I/O and encoding work. Retain those checks for correctness; measure their cost before optimizing compressed-record reuse.

## Migration Plan

1. Restore intended preservation without changing extension routing or public entry points.
2. Wire this manifest check into the later structural-validator adapter without delaying the regression fix.

## Verification

- Run real available ZIP/7z/tar and Info-ZIP round-trips; missing tools must skip explicitly.
- Assert rejected candidates leave original bytes unchanged.
