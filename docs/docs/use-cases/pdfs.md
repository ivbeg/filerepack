---
title: "PDFs"
description: "Lossless PDF stream walking and opt-in Ghostscript lossy profiles"
---
# PDFs

JPEG, PNG, and PDF default to **lossless** tools.

## Lossless

Install `filerepack[pdf]` so pikepdf can walk embedded JPEG / JPEG 2000 / Flate
image streams, then qpdf rewrites the file. Without pikepdf, only qpdf runs.

```bash
pip install 'filerepack[pdf]'
filerepack repack report.pdf
```

Encrypted or digitally signed PDFs skip stream replacement; lossless qpdf may
still run.

Adobe Illustrator `.ai` uses the same path when the file is a PDF wrapper.

## Lossy (scans)

`--lossy` uses Ghostscript `/ebook` (150 dpi) so scanned pages actually shrink.
`--pdf-profile prepress` restores print-quality Ghostscript. `--jpeg-quality`
sets Distiller QFactor for images inside PDFs.

```bash
filerepack repack scan.pdf --lossy
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
filerepack repack scan.pdf --pdf-profile prepress
```

`--lossy` / `--pdf-profile` / `--jpeg-quality` skip pikepdf and use Ghostscript
instead.

Ghostscript Distiller presets: `screen`, `ebook`, `printer`, `prepress`,
`default`.

## Related docs

- [`repack`](/commands/repack)
- [Formats](/formats/)
- [External tools](/tools/)
