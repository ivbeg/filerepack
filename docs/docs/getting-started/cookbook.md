---
title: "Cookbook"
description: "Pick a role and goal, then follow verified filerepack commands"
---
# Cookbook

filerepack covers many formats. This page is a task-oriented index: find the row
that sounds like you, then follow the linked reference sections. If you are
completely new, do the [five-minute quickstart](/getting-started/quick-start) first.

| You are a… | You want to… | Start with |
|------------|--------------|------------|
| [Office user](/use-cases/office-documents) | Shrink Word, Excel, PowerPoint, or ODF files without opening them | `repack document.docx` |
| [Archivist](/use-cases/archives) | Recompress ZIP / 7z / RAR / tar trees and nested members | `repack archive.zip`, `repack photos.tar.gz` |
| [Photo or media librarian](/use-cases/images-and-media) | Lossless (or opt-in lossy) images, video, and audio | `bulk ./photos --include-ext jpg,png,webp` |
| [Records manager](/use-cases/pdfs) | Shrink PDFs losslessly, or downsample scans | `repack scan.pdf`, `--lossy` |
| [Ops / sysadmin](/use-cases/bulk-directories) | Walk a directory tree with jobs, filters, and progress | `bulk ./documents --jobs auto --progress` |
| [Data engineer](/use-cases/data-files) | Recompress Parquet, SQLite, ORC, Avro, HDF5 | `repack data.parquet --ultra` |
| [Application developer](/library/) | Call the same packers from Python | `FileRepacker`, `RepackOptions` |

## Detailed walkthroughs

- [Office documents](/use-cases/office-documents)
- [Archives](/use-cases/archives)
- [Images and media](/use-cases/images-and-media)
- [PDFs](/use-cases/pdfs)
- [Bulk directories](/use-cases/bulk-directories)
- [Data files](/use-cases/data-files)
