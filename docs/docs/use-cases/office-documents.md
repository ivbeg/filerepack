---
title: "Office documents"
description: "Shrink Word, Excel, PowerPoint, ODF, and iWork files"
---
# Office documents

Office files are ZIP containers. filerepack extracts them, packs nested images
and minifies XML, then rewrites the archive. OOXML-like files prefer Info-ZIP
`zip` when it is on PATH so extra 7-Zip fields do not break Word/Excel.

## Word, Excel, PowerPoint

```bash
filerepack repack contract.docx
filerepack repack workbook.xlsx --dryrun --stats
filerepack repack slides.pptx --progress
```

Needs `7zz` or `7z`. Install `zip` as well for OOXML.

## OpenDocument and iWork

```bash
filerepack repack report.odt
filerepack repack sheet.ods
filerepack repack deck.odp
filerepack repack notes.pages
```

`.otf` is packed as ODF only when the file is a ZIP (OpenType fonts are skipped).

## Bulk a documents folder

```bash
filerepack bulk ./documents --include-ext docx,xlsx,pptx,odt,ods,odp --jobs auto --progress
```

See the [format matrix](/formats/) for the full OOXML / ODF / iWork extension list.

## Related docs

- [Archives](/use-cases/archives) — the same ZIP walk
- [`repack`](/commands/repack)
- [External tools](/tools/)
