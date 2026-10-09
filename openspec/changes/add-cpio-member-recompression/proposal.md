# Change: Add verified CPIO member recompression

## Why
Outer bzip2 recompression preserves CPIO bytes but cannot optimize compressible
files inside the archive. CPIO is a common install-image format whose member
headers, link entries and order must survive inner optimization.

## What Changes
- Detect raw `.cpio`, `.cpbz2` and `.cpio.bz2` archives. For a generically named
  `.bz2`, classify it as CPIO only when its decoded header declares supported CPIO.
- Extend the pending CPBZ2 stream-recompression behavior so valid members can
  also be optimized without changing protected CPIO data.
- Read, extract, update and write validated old-binary, odc, newc and CRC-newc
  records while retaining format, order, paths, metadata, links, unsupported
  members and archive padding.
- Apply existing file packers to safe, regular, single-link CPIO members when
  deep walking is enabled. Preserve verified member updates only; rebuild the
  bzip2 wrapper for the compressed aliases.
- Enforce decoded-byte, extraction-ratio, member-count, path-collision and scratch
  limits. Skip inner rewriting safely for malformed or unsupported profiles.
- Verify every member's original order/type/metadata, exact bytes for untouched
  payloads and the declared preservation contract for optimized payloads before
  publishing through shared size, dry-run and transaction policies.
- Document the supported profiles and conservative treatment of links, special
  files and unsupported CPIO records.

## Impact
- New capability: `cpio-member-recompression`.
- Affected code: CPIO stream/container identification, bounded CPIO parser and
  writer, archive orchestration, structural/preservation verification, tests,
  documentation and changelog. No new runtime dependency or CLI flag.
- The user's explicit request authorizes implementation of CPIO member
  optimization, extending the existing outer-stream `.cpbz2` support.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
