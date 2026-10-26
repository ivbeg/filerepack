# Change: Refilter qualified DOC PNGs without changing samples or metadata

## Why
Qualified DOC PNGs currently retain their original row filters, while DOCX image
optimization can choose better filters. This leaves avoidable image bytes in
documents such as the supplied gov.doc.

## What Changes
- Enable the existing bounded, independently verified PNG refiltering codec for
  qualified inline and floating DOC pictures.
- Preserve all non-IDAT chunks, exact samples (including invisible RGB), Word
  formatting/references and unselected picture bytes.
- Keep the existing DOC aggregate bound, root reservations and optional-encoder
  fallback; measure supplied files and compare complete page renders.

## Impact
- Affected spec: officeart-recompression.
- Affected code: ole_art_layout.py, ole_officeart.py, ole_raster.py.
- No CLI changes or new dependency; XLS qualification stays unchanged.

## Authorization
On 2026-10-08 the user explicitly instructed implementation ("Сделай это")
after reviewing the proposed DOC PNG filter selection and preservation checks.
That instruction approves this scoped implementation.
