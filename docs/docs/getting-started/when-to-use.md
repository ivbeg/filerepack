---
title: "When to use filerepack"
description: "filerepack vs zip, jpegoptim, oxipng, qpdf, Ghostscript, and ffmpeg"
---
# When to use filerepack vs zip vs jpegoptim vs qpdf

Evaluators often ask which tool to reach for. Short answer: **filerepack is a
lossless-first orchestrator** that walks nested files inside Office documents
and archives, then rewrites the container. Use a single specialized tool when
you already know the format and want its flags directly.

| Need | Prefer |
|------|--------|
| Shrink a `.docx` / `.xlsx` / `.pptx` including embedded images and XML | **filerepack** |
| Walk ZIP / 7z / RAR / tar and optimize members, then rewrite | **filerepack** |
| One JPEG, with exact jpegoptim / jpegtran flags | **jpegoptim** / **jpegtran** |
| One PNG, with oxipng / zopflipng / pngquant flags | **oxipng** / **pngquant** |
| Lossless PDF rewrite only | **qpdf** |
| Lossy PDF Distiller presets | **Ghostscript** (`gs`) — also available via `filerepack --lossy` |
| Re-encode one video | **ffmpeg** |
| Recursively process a mixed directory of documents, photos, and archives | **filerepack bulk** |

## filerepack strengths

- Nested walking: Office/OOXML, ZIP, 7z, RAR, tarballs, EPUB, JAR, APK, …
- One CLI for images, PDFs, video, lossless audio, Parquet, SQLite, fonts
- Safety: write to a temp file, verify, then `os.replace`; discard output that did not shrink
- `filerepack doctor` prints OS-specific install commands for missing binaries

## When another tool wins

- **jpegoptim / oxipng / qpdf / ffmpeg**: you want that tool's full flag surface on a single file
- **7-Zip / Info-ZIP**: you are creating a new archive, not recompressing an existing tree
- **ImageMagick alone**: you are converting formats, not shrinking in place

## Related docs

- [Quick start](/getting-started/quick-start)
- [Format support](/formats/)
- [External tools](/tools/)
