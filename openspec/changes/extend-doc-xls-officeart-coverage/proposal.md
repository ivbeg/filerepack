# Change: Extend OfficeArt discovery and relocation for ordinary DOC/XLS files

## Why

The initial runtime optimizes a narrow inline Word profile and image-only BIFF8
worksheets. Ordinary workbooks with cells, formulas or populated string/row
indexes and many Word formatting/picture layouts fall back to strict compaction,
even when their pictures contain eligible compressed content.

## What Changes

- Add qualified populated BIFF8 profiles with cells, formulas, SST/CONTINUE,
  ExtSST, Index and DBCell, preserving their data and original encodings.
- Extend Word reference discovery through piece PRMs, inherited formatting,
  floating drawing stores and mixed Data regions where every affected pointer
  and boundary can be resolved.
- Build a typed relocation ledger for every changed length/reference. Keep
  unknown records opaque only when their lack of affected offsets is established.
- Retain existing macro/protection gates, strict compaction fallback, opt-in
  ole_recompress behavior and independent intended-change verification.
- Measure newly eligible real documents separately from compression ratios.

## Impact

- Affected capability: officeart-recompression; additive requirements only.
- Affected code: ole_word_art.py, ole_xls_art.py, ole_art_layout.py,
  ole_officeart.py, ole_recompress.py and production verifier/fixture support.
- Priority: P1; first delivery in the [OLE plan](../../OLE-OPTIMIZATION-PLAN.md).
- Prerequisites: [initial OfficeArt](../add-officeart-payload-recompression/proposal.md)
  and [strict compaction](../add-ole-container-compaction/proposal.md).
- PNG/JPEG rewriting, cell/text re-encoding, BIFF5, charts/pivots/controls and
  unqualified Word/private record families are outside this delivery.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

Use real populated workbooks and Word files with the newly qualified layouts,
plus corruption/stale-pointer tests. Compare formula tokens/results, string
encodings, formatting, unaffected bytes, full CFB metadata and normalized
reference targets. Supplement with pinned application opening/rendering and
publish the remaining unsupported families and unavailable platform checks.
