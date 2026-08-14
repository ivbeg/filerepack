# CLI reference

filerepack has three commands: `repack`, `bulk`, and `doctor`.

```bash
filerepack doctor
filerepack repack <file> [OPTIONS]
filerepack bulk <directory> [OPTIONS]
```

## Shared flags

| Flag | Meaning |
|------|---------|
| `--dryrun` | Measure savings; do not modify files |
| `--quiet` / `--verbose` / `--debug` | Verbosity |
| `--no-images` | Skip image, video, and audio packers |
| `--no-archives` | Skip nested archive rewriting |
| `--deep` / `--no-deep` | Walk inside archives (default: on) |
| `--min-savings PCT` | Keep result only if savings ≥ PCT |
| `--min-size` / `--max-size` | Size filters (`1MB`, `100KB`, …) |
| `--backup` / `--backup-dir` | Copy source before rewriting |
| `--output-dir` | Write results here instead of in place |
| `--compression-level 1-9` | Archive compression (default 9) |
| `--jpeg-quality 1-100` | Implies lossy JPEG; also re-encodes images inside PDFs |
| `--png-quality high\|medium\|low` | Implies lossy PNG (pngquant) |
| `--pdf-profile` | Ghostscript Distiller preset: `screen`, `ebook`, `printer`, `prepress`, `default` (implies lossy PDF) |
| `--lossy` | Ghostscript PDF (`/ebook` unless `--pdf-profile` is set), jpegoptim `-m`, pngquant, lossy AVIF/HEIC |
| `--wmv-lossless` | Video CRF 0 (or VP9 lossless for WebM) |
| `--convert-container` / `--no-convert-container` | WMV/AVI/ASF → MP4 (default: convert) |
| `--allow-grow` | Keep output even if larger |
| `--keep-meta` | Keep JPEG/PNG metadata (default strips EXIF/ICC) |
| `--max-extract-size` | Skip archive extract if uncompressed size exceeds this (`0` disables; default 8GB, also 100× the archive) |
| `--ultra` | Parquet zstd level 22 |
| `--json` / `--csv` | Machine-readable output (mutually exclusive) |
| `--log-file PATH` | Also write CLI messages to a file |
| `--stats` | Extra timing / counts |
| `--progress` | Progress bar (`rich` if installed). `repack` is on for a TTY (`--no-progress` to hide); `bulk` needs `--progress` |
| `--progress-interval N` | Interval when `rich` is not installed (default 10) |

JPEG/PNG/PDF are lossless unless `--lossy`, `--pdf-profile`, or a quality flag is set. Lossy PDF defaults to Ghostscript `/ebook` (150 dpi) because `/prepress` barely shrinks scanned pages. Use `--pdf-profile prepress` for the old print-quality Ghostscript path. DICOM is always lossless JPEG-LS (`gdcmconv` or `dcmcjpls`); `--lossy` does not apply. Results that are not smaller are discarded unless `--allow-grow`. `--ultra` also tries `zopflipng` for PNG when it is installed. `--keep-meta` leaves JPEG/PNG metadata in place.

## bulk-only

| Flag | Meaning |
|------|---------|
| `--skip-zip` / `--no-skip-zip` | Skip top-level `.zip` (default: skip) |
| `--include-ext` / `--exclude-ext` | Comma-separated extension filters |
| `--exclude-dir` | Extra directory names to skip |
| `--jobs N\|auto` | Process pool workers |
| `--continue-on-error` | Do not stop the scan on a failure |

Default skipped directories: `.git`, `.hg`, `.svn`, `.tox`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.mypy_cache`, `.pytest_cache`.

### Exit codes

- `0` — success
- `1` — usage error, missing path, or a failure without `--continue-on-error`
- `2` — some files failed while `--continue-on-error` was set
- `filerepack doctor` exits `1` if `7zz`/`7z` is missing
- `filerepack doctor` prints install commands for the current OS after the tool table when anything is missing

## Examples

```bash
filerepack repack contract.docx
filerepack repack contract.docx --progress
filerepack repack contract.docx --dryrun --stats
filerepack bulk ./documents --min-size 1MB --min-savings 5 --jobs auto
filerepack bulk ./photos --include-ext jpg,png,webp,avif,jxl --progress
filerepack bulk ./dicom --include-ext dcm --progress
filerepack bulk ./video --include-ext mp4,mkv,webm,mov --wmv-lossless
filerepack repack photos.tar.gz
filerepack repack data.sqlite
filerepack repack data.parquet --ultra
filerepack repack scan.pdf --lossy
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
filerepack repack archive.rar          # becomes .7z if `rar` is missing
```

Size arguments accept `1000`, `1KB`, `1.5MB`, `2GB`.
