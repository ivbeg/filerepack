# Installing command-line tools

`filerepack doctor` prints which binaries are on PATH. Only `7zz` or `7z` is required for archive/OOXML work. Everything else enables extra formats.

Override a tool with an environment variable (`FILEREPACK_7ZZ`, `FILEREPACK_JPEGOPTIM`, …) or:

```toml
# ~/.config/filerepack/config.toml
[tools]
szip = "/opt/homebrew/bin/7zz"
qpdf = "/usr/local/bin/qpdf"
```

## What each tool is for

| Tool | Formats |
|------|---------|
| `7zz` or `7z` | ZIP, 7z, OOXML, nested archives |
| `zip` | Preferred rewrite for OOXML (docx/xlsx/pptx, …) |
| `jpegoptim` | JPEG (lossless strip, or `-m` with `--jpeg-quality`) |
| `oxipng` / `optipng` | lossless PNG |
| `pngquant` | lossy PNG (`--png-quality` / `--lossy`) |
| `qpdf` | lossless PDF (default) |
| `gs` / `gswin64c` | lossy PDF (`--lossy`) |
| `gifsicle` | GIF |
| `dwebp` + `cwebp` | WebP |
| `svgo` or `scour` | SVG |
| `magick` / `convert`, `tiffcp` | TIFF, HEIC |
| `avifenc` + `avifdec` | AVIF (ImageMagick fallback) |
| `ffmpeg` | MP4, MKV, WebM, WMV, AVI, ASF |
| `pigz` | faster gzip |
| `xz`, `bzip2`, `zstd`, `brotli` | xz / bz2 / zst / br |
| `flac` | FLAC recompress |
| `unrar`, `rar` | RAR extract / rewrite (`rar` missing → 7z) |
| `duckdb` Python package | Parquet (`pip install 'filerepack[parquet]'`) |

## macOS (Homebrew)

```bash
brew install p7zip zip jpegoptim pngquant oxipng
brew install qpdf ghostscript gifsicle webp imagemagick libtiff ffmpeg
brew install pigz xz zstd brotli flac
npm install -g svgo   # or: pip install scour
pip install 'filerepack[parquet]'
```

`p7zip` may install `7z` instead of `7zz`. filerepack accepts either.

## Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install zip p7zip-full jpegoptim pngquant optipng
sudo apt-get install qpdf ghostscript gifsicle webp imagemagick libtiff-tools ffmpeg
sudo apt-get install pigz xz-utils bzip2 zstd brotli flac unrar
sudo apt-get install python3-scour   # or: sudo npm install -g svgo
pip install 'filerepack[parquet]'
```

## Windows (Chocolatey)

```powershell
choco install 7zip jpegoptim pngquant qpdf ghostscript gifsicle webp imagemagick ffmpeg -y
npm install -g svgo
pip install 'filerepack[parquet]'
```

Add `C:\Program Files\7-Zip` to PATH. filerepack looks for `7zz` then `7z`.

## Verify

```bash
filerepack doctor
```
