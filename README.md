# filerepack

Lossless-first recompression for Office documents, archives, images, PDFs, video, and compressed data files. Nested files inside ZIP/7z/RAR/OOXML are walked and optimized, then the container is rewritten.

Python 3.9+ · macOS, Linux, Windows.

## Documentation

The full documentation site (Docusaurus) lives in [`docs/`](docs/) and is published at **[ivbeg.github.io/filerepack](https://ivbeg.github.io/filerepack/)**.

| Section | What it covers |
|---------|----------------|
| [Getting started](https://ivbeg.github.io/filerepack/getting-started/installation) | Install, quick start, positioning |
| [Cookbook](https://ivbeg.github.io/filerepack/getting-started/cookbook) | Task index by role |
| [CLI reference](https://ivbeg.github.io/filerepack/commands/) | `repack`, `bulk`, `doctor` |
| [Formats](https://ivbeg.github.io/filerepack/formats/) | Extension matrix and nested walking |
| [External tools](https://ivbeg.github.io/filerepack/tools/) | Binaries and OS install commands |
| [Python library](https://ivbeg.github.io/filerepack/library/) | `FileRepacker` API |
| [Troubleshooting](https://ivbeg.github.io/filerepack/getting-started/troubleshooting) | Exit codes and common errors |

Source pages: [`docs/docs/`](docs/docs/). Changelog: [`CHANGELOG.md`](CHANGELOG.md). Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Install

```bash
pip install filerepack
pip install 'filerepack[parquet]'    # DuckDB Parquet support
pip install 'filerepack[data]'       # Parquet + ORC/Avro/Feather/Arrow
pip install 'filerepack[fonts]'      # WOFF/WOFF2 via fonttools
pip install 'filerepack[progress]'   # rich progress bars for repack and bulk --progress
pip install 'filerepack[media]'      # mutagen cover-art walking in MP3/FLAC/M4A/Ogg/APE
pip install 'filerepack[pdf]'        # pikepdf lossless PDF image-stream walking
```

External tools are optional per format. See what you have and how to install the rest on this OS:

```bash
filerepack doctor
```

Install commands use Homebrew or MacPorts on macOS, apt/dnf/pacman/zypper/apk on Linux, and Chocolatey/winget/Scoop on Windows. `mp3packer` and `optivorbis` are not packaged; doctor points at GitHub CLI zips. Full notes: [tools](https://ivbeg.github.io/filerepack/tools/). Override paths with `FILEREPACK_7ZZ` (and similar) or `~/.config/filerepack/config.toml`.

## Quick start

```bash
filerepack repack document.docx
filerepack repack document.docx --dryrun
filerepack bulk ./documents --jobs auto --progress
filerepack bulk ./photos --include-ext jpg,png,webp
```

`filerepack repack` shows a progress bar on a TTY (`--no-progress` to hide it). `bulk` needs `--progress`. Install `filerepack[progress]` for a `rich` bar; otherwise progress prints every N files.

JPEG, PNG, and PDF default to **lossless** tools. Opt into lossy codecs with `--lossy`, `--jpeg-quality`, `--png-quality`, or `--pdf-profile`. Lossy PDF uses Ghostscript `/ebook` (150 dpi) so scanned pages actually shrink; `--pdf-profile prepress` restores print-quality Ghostscript. `--jpeg-quality` also re-encodes images inside PDFs. Lossless JPEG/PNG strip metadata unless `--keep-meta`. `--ultra` adds stronger lossless passes (Parquet zstd 22, `zopflipng` for PNG, `mp3packer -z`). Output that is not smaller than the original is discarded unless `--allow-grow`.

```bash
filerepack repack scan.pdf --lossy
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
```

## Formats

| Kind | Extensions |
|------|------------|
| Office / OOXML | docx, xlsx, pptx, odt, ods, odp, ott, oth, otm, sxw, stw, pages, key, kth, vsdx, vssx, … |
| Archives | zip, 7z, rar, tar, tar.gz/tgz, tar.xz, tar.lzo, cab, wim, jar, epub, apk, aab, war, nupkg, oxt, … |
| Compressed | gz, xz, bz2, zst, br, lz4, lz, lzma, lzo, Z |
| Documents | pdf, ai (PDF-based), xml, json, xhtml, kml, gpx, fb2, … |
| Images | jpg, png, gif, webp, svg/svgz, tif, avif, heic, jxl, jp2, exr, dng, ico, cur, icns, bmp, tga, pnm, pcx, psd, dcm |
| Video | mp4, mkv, webm, mov, m4v, wmv, avi, asf, 3gp, ts |
| Audio | flac, m4a/m4b (ALAC), ogg/opus, wv, ape, tta, oga, mp3 |
| Data | parquet, orc, avro, feather/arrow, sqlite, gpkg, mbtiles, hdf5, netcdf |
| Fonts | woff, woff2 |

WMV/AVI/ASF/3GP/MPEG-TS convert to MP4 unless `--no-convert-container`. MKV/WebM/MOV/M4V keep their container. `.tar.gz` and friends are unpacked so nested files can be optimized, then the tarball is rewritten. Signed installers (`deb`, `rpm`, `pkg`, `dmg`) and ISO/CPIO/AR are not rewritten. DICOM (`.dcm` / `.dicom` / `.dic`) is lossless JPEG-LS only; `--lossy` does not apply. Needs `gdcmconv` or `dcmcjpls`. Nested XML/JSON inside ZIP/OOXML/ODF/EPUB is minified (text nodes kept). Cover art inside MP3/FLAC/M4A/Ogg/APE is optimized when `filerepack[media]` is installed. Lossless PDF can walk image streams when `filerepack[pdf]` is installed. Full extension list and per-format tools: [formats](https://ivbeg.github.io/filerepack/formats/).

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
