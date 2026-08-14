# filerepack

Lossless-first recompression for Office documents, archives, images, PDFs, video, and compressed data files. Nested files inside ZIP/7z/RAR/OOXML are walked and optimized, then the container is rewritten.

Python 3.9+ · macOS, Linux, Windows.

## Install

```bash
pip install filerepack
pip install 'filerepack[parquet]'    # DuckDB Parquet support
pip install 'filerepack[progress]'   # rich progress bars for bulk --progress
```

External tools are optional per format. See what you have:

```bash
filerepack doctor
```

Install system tools with [docs/tools.md](docs/tools.md). Override paths with `FILEREPACK_7ZZ` (and similar) or `~/.config/filerepack/config.toml`.

## Quick start

```bash
filerepack repack document.docx
filerepack repack document.docx --dryrun
filerepack bulk ./documents --jobs auto --progress
filerepack bulk ./photos --include-ext jpg,png,webp
```

JPEG, PNG, and PDF default to **lossless** tools. Opt into lossy codecs with `--lossy`, `--jpeg-quality`, or `--png-quality`. Output that is not smaller than the original is discarded unless `--allow-grow`.

Full CLI: [docs/cli.md](docs/cli.md). Library API: [docs/library.md](docs/library.md).

## Formats

| Kind | Extensions |
|------|------------|
| Office / OOXML | docx, xlsx, pptx, odt, ods, odp, pages, key, … |
| Archives | zip, 7z, rar, jar, epub, apk, … |
| Compressed | gz, xz, bz2, zst, br |
| Documents | pdf |
| Images | jpg, png, gif, webp, svg, tif, avif, heic |
| Video | mp4, mkv, webm, wmv, avi, asf |
| Audio | flac (recompress, same format) |
| Data | parquet |

WMV/AVI/ASF convert to MP4 unless `--no-convert-container`. MKV/WebM keep their container.

## Safety

Rewrites go to a temp file, are verified, then `os.replace`d onto the original. A missing `7zz`/`7z` leaves the source archive untouched. `filerepack doctor` exits 1 if the required archiver is missing.

## Library

```python
from filerepack import FileRepacker, RepackOptions

rp = FileRepacker()
summary = rp.repack("slides.pptx", options=RepackOptions(dryrun=True))
print(summary.total_insize, summary.total_outsize, summary.total_savings_pct)
```

## License

BSD. See [CHANGELOG.md](CHANGELOG.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
