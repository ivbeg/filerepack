# Change: Recompress Apple Unified Log tracev3 files

## Why

The repository can already recompress several container formats, while Apple Unified Log `.tracev3` chunksets contain LZ4 blocks that can often be encoded more compactly without changing their decoded contents. A format-aware operation can reduce archival copies while preserving the original log data.

## What Changes

- Add optional `.tracev3` recompression that rewrites eligible LZ4 blocks inside chunksets and retains the existing block whenever a new encoding is not smaller.
- Preserve all non-chunkset bytes and verify decoded chunkset payloads and file structure before publishing a candidate.
- Fail closed on malformed, unsupported, or resource-limited inputs; do not modify an active macOS Unified Log store in place.
- Expose the feature as an optional `filerepack[tracev3]` extra and document its supported profile and limits.

## Impact

- Affected specs: `tracev3-recompression`
- Affected code: format worker and validation, packer dispatch, format detection, optional dependencies, CLI safety checks, and format documentation.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
