# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-14

### Security

- Replaced all `os.system()` calls with `subprocess.run()` using argument lists
- External tools now use `subprocess.run(cwd=...)` instead of process-global `os.chdir()`

### Fixed

- **Data loss:** archive rewrite no longer unlinks the original before 7zz/rar succeeds. New archives are written to a temp file, verified, then `os.replace`d
- **Data loss:** WMV/AVI/ASF conversion no longer deletes the compressed output while renaming
- `--min-savings` no longer mutates a file and then reports it as skipped
- `filerepack bulk` now includes standalone JPEG and PNG files
- JPEG/PNG packers return failure when jpegoptim/pngquant/oxipng are missing
- Parquet compression uses the DuckDB Python API (`pip install duckdb`) instead of a `duckdb` CLI binary
- `bulk --csv` accepts dict result rows
- `--jobs auto` is parsed as a string (`auto` or an integer)
- `--json` and `--csv` are mutually exclusive
- `--log-file` now records CLI messages
- Glob expansion only expands a bare `*` (archive contents), not filenames containing `*`
- Failed archive extraction leaves the original file untouched

### Changed

- JPEG/PNG/PDF default to lossless tools. Use `--jpeg-quality`, `--png-quality`, or `--lossy` for lossy codecs
- Results that are not smaller than the original are discarded unless `--allow-grow` is set
- `FileRepacker.repack_zip_file` returns `RepackSummary` (still supports `summary['final']` dict access)
- gzip/xz/bz2 stream through temp files instead of loading the whole payload into memory
- 7-Zip is resolved as `7zz` or `7z` (env `FILEREPACK_7ZZ`, optional `~/.config/filerepack/config.toml`)

### Added

- `filerepack doctor` — report which external tools are on PATH
- `--jobs N|auto` parallel bulk processing via `ProcessPoolExecutor`
- `--exclude-dir` plus default skips for `.git`, `node_modules`, `__pycache__`, venvs
- `--lossy`, `--allow-grow`, `--convert-container/--no-convert-container`
- `--max-extract-size` (default 8GB / 100×) to skip zip-bomb-sized archive extracts
- Zstandard (`.zst`), Brotli (`.br`), AVIF, HEIC/HEIF, FLAC, MKV, WebM
- Integrity checks (magic bytes / `zipfile.is_zipfile`) before replacing originals
- OOXML rewrite prefers Info-ZIP `zip` when available (7zz extra fields can break Office)
- `RepackOptions` dataclass and `FileRepacker.repack()` for the library API
- Optional `rich` progress bars (`pip install 'filerepack[progress]'`)
- pytest suite covering atomic replace, CLI, and packer failure paths
- GitHub Actions CI for Python 3.9–3.13 with p7zip installed
- Split docs: `docs/cli.md`, `docs/tools.md`, `docs/library.md`
- ruff instead of flake8

### Removed

- Redundant `bin/filerepack.py`, outdated `README.rst`, deprecated `.travis.yml`
- Unused `pack_jpg_re` / `EXT_IMAGE_MAP` / shell quiet-redirection suffix

## [0.1.4] - 2025-11-12

### Changed

- Added `long_description_content_type` to `setup.py` for proper Markdown rendering on PyPI

## [0.1.3] - 2025-11-12

### Changed

- Updated `requirements.txt` with typer and optional duckdb dependency
- Added `extras_require` to `setup.py` for optional parquet support (duckdb)

## [0.1.2] - 2025-11-12

### Changed

- Converted HISTORY.rst to HISTORY.md
- Updated `setup.py` to use Markdown format

## [0.1.1] - 2025-11-12

### Fixed

- Fixed issue repacking .pub and .xmind files
- Fixed issue jpeg repacking with jpeg-recompress

## [0.1.0] - 2018-01-14

### Added

- First public release on PyPI and GitHub
