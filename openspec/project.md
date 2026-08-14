# Project Context

## Purpose
filerepack is a Python CLI tool and library for lossless and lossy re-compression of files. It optimizes Office/OOXML documents, ZIP/7z/RAR/tar archives, stream codecs, PDFs, images, video, lossless audio, and data files (Parquet, SQLite, ORC, …).

## Tech Stack
- Python 3.9+
- Typer (CLI framework)
- duckdb (optional, for Parquet support)
- External system tools: 7zz, zip, jpegoptim, pngquant, gs, ffmpeg, etc.

## Project Conventions

### Code Style
- Max line length: 100 characters
- 4-space indentation
- UTF-8 encoding, LF line endings
- Trailing whitespace trimmed

### Architecture Patterns
- Single `FileRepacker` class in `repack.py` (~2156 lines) containing all compression logic
- Individual `pack_*()` functions for each file format
- CLI entry point in `__main__.py` using Typer
- Utility functions isolated in `utils.py`
- Constants and tool paths in `consts.py`

### Testing Strategy
- Currently no tests exist
- Tests should be added incrementally starting with `utils.py` (pure functions)
- Integration tests should use sample files for each format
- Target: pytest with coverage via `.coveragerc`

### Git Workflow
- Single `master` branch
- Commits follow semantic prefixes
- Author: Ivan Begtin

## Domain Context
- File compression tools require careful handling of binary data
- External tool availability varies by platform (macOS, Linux, Windows)
- Shell command construction from user input is a primary security concern
- Cross-platform path handling is essential

## Important Constraints
- Must support macOS, Linux, and Windows
- External tool paths may differ across platforms
- Some tools are optional (Ghostscript, ffmpeg) — code must handle their absence gracefully
- Backward compatibility with existing CLI flags must be maintained

## External Dependencies
- System tools: `7zz`, `zip`, `unrar`, `rar`, `jpegoptim`, `pngquant`, `gs`/`gswin64c`, `qpdf`, `gifsicle`, `dwebp`/`cwebp`, `svgo`/`scour`, `convert`/`magick` (ImageMagick), `tiffcp`, `ffmpeg`, `pigz`
- Python packages: `typer>=0.9.0`, `duckdb>=0.9.0` (optional)
