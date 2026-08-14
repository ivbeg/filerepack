# Change: Improve lossy PDF compression for scanned documents

## Why
Lossless qpdf only recompresses PDF object streams, so already-encoded scan images do not shrink. `--lossy` used Ghostscript `/prepress` (300 dpi, high JPEG quality), which also leaves typical 300 dpi scans almost unchanged.

## What Changes
- Keep qpdf as the lossless default
- `--lossy` PDF uses Ghostscript `/ebook` (150 dpi) instead of `/prepress`
- Add `--pdf-profile screen|ebook|printer|prepress|default` (implies lossy PDF)
- `--jpeg-quality` applies to embedded PDF images via Ghostscript Distiller QFactor
- Illustrator PDF-wrapped `.ai` files follow the same path
- **Behavior change:** existing `--lossy` PDF runs become more aggressive (`/ebook` vs `/prepress`). Restore the old quality with `--pdf-profile prepress`

## Impact
- Affected specs: `pdf` (new)
- Affected code: `filerepack/repack.py`, `filerepack/codecs.py`, `filerepack/__main__.py`, `filerepack/models.py`, `filerepack/jobs.py`, `filerepack/consts.py`, docs, tests
- Not breaking for the lossless default; `--lossy` PDF output quality changes
