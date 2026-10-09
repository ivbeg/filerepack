# Change: Add preserving Apple CAR recompression

## Why
Apple compiled asset catalogs use a BOMStore container and can contain DEFLATE
image payloads, unused allocation ranges and oversized block-index capacity.
Filerepack currently skips `.car` files.

## What Changes
- Add dependency-free `.car` routing for qualified BOMStore v1/CoreUI catalogs.
- Recompress recognized MLEC/CELM ZIP payloads (single zlib/gzip streams and
  KCBC gzip/zlib bands) with DEFLATE level 9 without changing their decoded bytes
  or compression envelope metadata.
- Compact physical allocations and trailing unused index capacity while keeping
  live block IDs, physical order, address alignment residues, complete tree pages,
  named-variable order, rendition keys, CSI/TLV metadata and opaque blocks.
- Preserve LZFSE/LZVN, Deepmap, palette, ASTC, raw resources and unknown codecs
  byte-for-byte. Do not thin catalogs, decode images or rebuild source xcassets.
- Validate bounds, allocations, named trees and rendition framing and compare
  logical source/candidate fingerprints before the existing publication policy.
- Add adversarial, transaction, CLI/bulk/archive and native Apple-reader tests.

## Impact
- New capability: `car-recompression`.
- Extension/dispatch/export integration and an independent validation route.
- No required dependency or new CLI flag. The user's explicit request to add
  support authorizes implementation of this preserving profile.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
