## Context
Scanned PDFs store most of their bytes in already-compressed page images (JPEG / CCITT / JBIG2). qpdf `--compress-streams=y` cannot re-encode those images. Ghostscript `pdfwrite` can downsample and re-JPEG them, but `/prepress` targets print and barely touches 300 dpi scans.

## Goals / Non-Goals
- Goals: make `--lossy` shrink scanned PDFs; expose Ghostscript Distiller presets; let `--jpeg-quality` tune embedded JPEG QFactor
- Non-Goals: JBIG2 / ocrmypdf / pikepdf image walking; MRC; changing the lossless qpdf default

## Decisions
- Decision: `--lossy` PDF profile is `/ebook` (150 dpi color/gray). That is the smallest Ghostscript change that actually helps scans.
- Decision: `--pdf-profile` and `--jpeg-quality` imply Ghostscript even without `--lossy`, matching how `--jpeg-quality` already implies lossy JPEG.
- Decision: map JPEG quality 1–100 to Distiller QFactor with `0.15 + (100 - q) * 2.25 / 99` (100 → 0.15, 1 → 2.4). Profile still controls downsample DPI.
- Alternatives considered:
  - Keep `/prepress` for `--lossy` and only add `--pdf-profile` — users would still see no savings unless they discover the flag
  - ocrmypdf / jbig2enc — better for bitonal scans, extra heavy tools; later change
  - pikepdf in-place image rewrite — preserves vectors better, new Python dependency; later change

## Risks / Trade-offs
- Ghostscript rewrites the PDF (forms, optional content, signatures can break) → same as today's `--lossy` path; lossless still uses qpdf
- `--jpeg-quality` on a mixed bulk run now also lossy-compresses PDFs → documented; use `--pdf-profile prepress` or omit the flag for PDFs
- `/ebook` is softer than `/prepress` → `--pdf-profile prepress` restores prior `--lossy` quality

## Migration Plan
- Lossless runs unchanged
- `--lossy` PDF: opt into `/ebook`; document `--pdf-profile prepress` for the old behavior
- No rollback beyond passing `--pdf-profile prepress`

## Open Questions
- None for this change
