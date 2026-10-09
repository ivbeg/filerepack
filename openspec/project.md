# Project Context

## Purpose
filerepack is a Python CLI tool and library for lossless and lossy re-compression of files. It optimizes Office/OOXML documents, ZIP/7z/RAR/tar archives, stream codecs, PDFs, images, video, lossless audio, and data files (Parquet, SQLite, ORC, …).

## Tech Stack
- Python 3.9+
- Typer (CLI framework)
- PyArrow 19+ (optional, for Parquet preservation and other data formats)
- DICOM verification extras (pydicom, NumPy and pyjpegls)
- External system tools: 7zz, zip, jpegoptim, pngquant, gs, ffmpeg, etc.

## Project Conventions

### Code Style
- Max line length: 100 characters
- 4-space indentation
- UTF-8 encoding, LF line endings
- Trailing whitespace trimmed

### Architecture Patterns
- `FileRepacker` in `repack.py` coordinates standalone and container processing
- Individual `pack_*()` functions for each file format
- CLI entry point in `__main__.py` using Typer
- Utility functions isolated in `utils.py`
- Constants and tool paths in `consts.py`
- Archive manifests, destinations, package policies and Parquet/DICOM verification have dedicated modules
- `candidates.py`/`transactions.py` own typed staging, verification/acceptance, source scopes and destination-local publication; `xattrs.py` and `commands.py` provide filesystem-attribute and argv execution adapters
- Standalone packers live in stream/image/media/document/data/medical/markup modules; archive work lives in `archives.py`; `repack.py`/`codecs.py` preserve helper imports and `dispatch.py` retains routing
- Worker request/results and progress callbacks are typed; heterogeneous legacy options remain validated API mappings

### Testing Strategy
- pytest tests live in `test/`, with shared fixtures/helpers and coverage via `.coveragerc`
- Preservation regressions use real format bytes and controlled faults; available external tools are exercised with explicit skips for missing integrations
- Source releases include the complete test package; runtime wheels exclude test/development support
- `python dev/validate_distribution.py` builds and installs sdist/wheel artifacts in fresh environments, checks import provenance/exports/CLI/license metadata and runs extracted tests against the installed runtime
- CI retains Ubuntu Python 3.9–3.13 and separate 3.9/3.13 artifact checks, with Linux/macOS/Windows process/filesystem, optional-reader, scientific-native and OLE-native lanes. These lanes are configured; remote results are not asserted. Newer Python versions need core/artifact/native-reader qualification before being described as tested.

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
- Python packages: `typer>=0.9.0`; format-specific extras are declared in `pyproject.toml`
- Builds: setuptools 77.0.3+ and wheel (isolated PEP 517); `build` is included in the development extra

## Verified specification baseline

The reconciliation updated on 2026-10-09 contains 189 verified current requirements in 48
capabilities, with unique live delta ownership. `baseline-audit.json` records
all 290 reviewed active/historical source blocks, narrowed historical wording
and pending broader writer/corpus/resource claims. Run
`python dev/check_spec_ownership.py` and strict OpenSpec validation.
Current implementation evidence and remaining gates are recorded in
`dev/quality/completion-2026-10-07.md`; no release/deployment or archive is implied
by a checked task or a local test result.
