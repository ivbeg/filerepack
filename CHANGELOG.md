# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-14

### Added

- ZIP-family aliases: `war`, `ear`, `aar`, `nupkg`, `snupkg`, `vsix`, `xpi`, `crx`, `appx`, `msix`, `appxbundle`, `sketch`, `kra`, `ora`, `xd`, `usdz`, `ifczip`, `cbr`/`cb7`/`cbt`, OOXML siblings (`vsdm`, `vstx`, `vstm`, `vssx`, `vssm`, `sldm`, `ots`, `otg`, `odb`), ODF templates (`oth`, `otm`, `otc`, `oti`; `otf` only when the file is a ZIP, not an OpenType font), OpenOffice.org 1.x (`stw`, `stc`, `sti`, `std`, `sxg`, `sxm`), iWork templates (`kth`, `nmbtemplate`, `template`), `oxt`, `aab`, `xapk`/`apks`, `npz`, `fcstd`, `mcworld`/`mcpack`/`mcaddon`, `unitypackage`, `onepkg`, `wgt`, `ibooks`, `air`, `pk3`, `xap`, `ipsw`, `osk`, `oex`, `puz`, `rmskin`, `notebook`, `nbk`
- XML/JSON minify (including nested parts in ZIP/OOXML/ODF/EPUB): `.xml`, `.json`, `.xhtml`, `.kml`, `.gpx`, `.dae`, `.rss`, `.atom`, `.xmp`, `.xsl`, `.xslt`, `.fb2`. SVG falls back to XML minify when svgo/scour are missing; `data:` image URIs are packed
- Cover art in MP3/FLAC/M4A/MP4/Ogg/APE via optional `filerepack[media]` (mutagen)
- Lossless PDF image-stream walking via optional `filerepack[pdf]` (pikepdf); `--lossy` still uses Ghostscript
- `jpegtran` lossless JPEG pass; `zopflipng` on `--ultra` PNG; `--keep-meta` to keep JPEG/PNG metadata
- Images: BMP, TGA, PNM, PCX, APNG, CUR; JPEG aliases `jif`/`jfi`/`thm`
- Ogg Vorbis/Opus via optional `optivorbis`; `.m4b` follows the M4A path; SQLite `.db` alias
- Tarball walk: `tar`, `tar.gz`/`tgz`, `tar.bz2`/`tbz2`, `tar.xz`/`txz`, `tar.zst`/`tzst`, `tar.br`, `tar.lz4`, `tar.lzo`/`tzo`, `tar.lz`/`tlz`, plus `gem`/`crate`. Inner files are optimized, then the archive is rewritten. Compressed streams whose payload is a tar (`.gz`, `.zst`, `.lz4`, …) are detected by peeking the first 512 decompressed bytes
- Stream codecs: `lz4`, `lz` (lzip), `lzma`, `lzo`, Unix `compress` (`.Z`)
- Containers: Microsoft Cabinet (`cab`) and WIM (`wim`)
- Images: JPEG aliases (`jpe`, `jfif`), JPEG XL, JPEG 2000, OpenEXR, DNG, ICO, ICNS, `svgz`
- DICOM (`.dcm` / `.dicom` / `.dic`): lossless JPEG-LS for uncompressed or RLE image instances via `gdcmconv` or `dcmcjpls`. Signed, non-image, and already-compressed files are skipped. `--lossy` does not apply
- Video: `mov`, `m4v` (kept), `3gp`/`ts`/`mts`/`m2ts` (convert to MP4 unless `--no-convert-container`)
- Lossless audio recompress: ALAC in `m4a`, WavPack, TTA, FLAC-in-Ogg; Monkey's Audio when `mac` is installed; MP3 via `mp3packer`
- Photoshop `psd`: recompress ZIP-encoded layer/composite channels (RLE/raw channels are left unchanged)
- Adobe Illustrator `ai` when the file is a PDF wrapper (same path as `pdf`)
- `--pdf-profile screen|ebook|printer|prepress|default` for Ghostscript Distiller presets (implies lossy PDF)
- Data: SQLite `VACUUM` (`sqlite`, `gpkg`, `mbtiles`), ORC/Avro/Feather/Arrow (optional extras), HDF5 (`h5repack`), NetCDF (`nccopy`)
- Fonts: WOFF/WOFF2 via fonttools or `woff2_compress`
- Optional extras: `filerepack[data]`, `filerepack[fonts]`, `filerepack[media]`, `filerepack[pdf]`
- `filerepack doctor` prints OS-specific install commands (Homebrew, apt, dnf, pacman, Chocolatey, winget, …) for missing tools. `mp3packer` and `optivorbis` are not packaged; doctor points at their GitHub releases with macOS/Linux/Windows binaries, and `docs/tools.md` has install steps
- `filerepack repack --progress` shows a progress bar (on by default on a TTY). Archives report extract / inner-file / rewrite stages

### Changed

- File type detection uses compound suffixes (`archive.tar.gz`) instead of only the last extension
- `--include-ext tar.gz` matches compound names; `--include-ext gz` still matches them too
- `--lossy` PDF uses Ghostscript `/ebook` (150 dpi) instead of `/prepress`, which actually downsamples scanned pages. `--pdf-profile prepress` restores the previous print-quality path. `--jpeg-quality` now also sets Distiller QFactor for images inside PDFs
- `optivorbis` install hints point at GitHub CLI zips. Cargo cannot install the CLI (`optivorbis` on crates.io is a library; `cargo install` has no `--package`)

### Fixed

- `--dryrun` on archives now includes inner-file savings in the predicted size. Previously inner packs were measured but not applied in the temp extract dir, so the rewritten archive looked larger than a real run

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
