## Context

The completed parity proposal already promised Flate-decoded PNG-like PDF images, while the current walker handles only direct-page DCT/JPX streams. Completing that gap and walking nested forms can improve more existing PDFs, provided decoded image semantics, shared references, and whole-file protection remain intact.

This design covers N06 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Complete eligible Flate/PNG-like image handling and recursively discover images in nested form resources.
- Goal: Deduplicate shared image objects and avoid resource cycles under root decode/depth/deadline budgets.
- Goal: Preserve decoded pixels, masks, color spaces, filter/decode parameters and PDF structure; report unsupported streams explicitly.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Apply the extended walker only on the existing lossless PDF path with pikepdf available. Whole-file protection/uncertainty gates run before any rewriting, and final candidate selection uses `add-structural-output-validation`; lossy Ghostscript behavior remains separately governed.
2. Traverse page resources and Form XObject resources using a visited object graph keyed by indirect object/generation identifiers and a bounded identity fallback for direct objects. Detect resource cycles and optimize a shared image stream once per document while preserving every reference.
3. Start with strictly supported single-Flate images and PNG predictor cases whose dimensions, bit depth, component count, Decode/DecodeParms and color space are understood. Recompress raw decoded sample bytes through PDF-compatible lossless filters; do not insert complete PNG file bytes as a PDF image stream.
4. Preserve `/Width`, `/Height`, `/BitsPerComponent`, `/ColorSpace` including ICC/indexed attributes, `/Decode`, masks/SMask, image-mask semantics and matching filter/decode parameters. Any unsupported chain, predictor or ambiguous semantic feature is skipped explicitly.
5. Validate per-image decoded sample equality and the rebuilt PDF's page/object/resource structure. Use deterministic fixed-renderer page comparisons for representative fixtures including masks/transparency/color; decoded equality remains the primary image oracle.
6. Only smaller valid image-stream candidates enter a rebuild, and only a final candidate satisfying whole-document minimum-savings/fidelity rules is published. Shared logical image IDs appear once for work accounting with all host references recorded, avoiding double-counting.

## Risks / Trade-offs

- Flate bytes are raw samples rather than a PNG file; incorrect predictors or filter parameters can create a parseable but visually broken PDF.
- Recursive form resources and shared objects can create cycles or duplicate work; use bounded graph traversal and identity caching.
- Different renderers can disagree on rasterization; pin rendering configuration and compare before/after with the same renderer alongside exact sample assertions.

## Migration Plan

1. Record the existing missing Flate promise during canonical baseline reconciliation; do not mark it implemented because the earlier tasks are checked.
2. Extend discovery and deduplication first, then add narrowly supported Flate cases with decoded/presentation fixtures.
3. Keep unsupported image/filter cases unchanged, document supported cases/limits, and update the requirement baseline only after actual validated implementation.

## Verification

- Verify exact decoded image samples, masks, color/decode semantics, dimensions and bit depth for accepted Flate/DCT/JPX candidates.
- Render real before/after pages with a pinned renderer/settings and compare pixels for nested forms, transparency and color fixtures.
- Verify shared streams encode once, references remain intact and resource cycles/deep graphs stay within limits.
- Test protected/uncertain PDFs, missing pikepdf, lossy selection, unsupported filter chains and larger rebuilt candidates; originals stay intact when ineligible.
- Check per-object work accounting versus whole-file savings and rerun the original completed parity PDF scenarios under the updated protection contract.
