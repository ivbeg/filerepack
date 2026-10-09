# Change: Deduplicate byte-identical images in qualified OfficeArt stores

## Why

Repeated insertion can store the same image multiple times. Recompressing each
copy leaves this duplication intact. Removing a copy changes store indices,
reference counts and possibly delay offsets, so it needs a complete reference
graph and an independent contract beyond payload-only recompression.

## What Changes

- Add default-false ole_deduplicate_images / --ole-deduplicate-images.
- Deduplicate only byte-identical complete BLIPs with compatible identity and
  store metadata in qualified shared OfficeArt stores.
- Resolve every picture/fill/line/print reference, repair store indices/counts
  and preserve each consuming shape's display/editing properties.
- Add independent normalized graph verification; keep existing recompression
  modes and strict OLE verification unchanged.
- Measure fully allocated file savings and report removed entries/repaired refs.

## Impact

- New capability: officeart-deduplication.
- Affected code: OfficeArt and host graph parsers, reference inventory,
  independent verification, candidate selection and CLI/library/worker options.
- Priority: P2, after [expanded host coverage](../extend-doc-xls-officeart-coverage/proposal.md).
- Raster rewriting is not a prerequisite for byte-identical deduplication;
  composition with it needs its delivered contract and union verification.
- Inline-only DOC PICFs without a qualified shared store, pixel-similar images,
  different metadata/UIDs, orphan/history pruning and controls remain excluded.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

Use real duplicate-image stores, including different crop/anchor/fill consumers,
and negative cases with one differing image/metadata byte or a hidden reference.
Verify every normalized target and drawing property; test wrong indices that are
still in bounds, count mismatches and physical no-gain outcomes.
