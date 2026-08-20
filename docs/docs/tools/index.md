---
title: "External tools"
description: "Binaries filerepack uses, OS install commands, and unpackaged CLIs"
slug: /tools
---

# Installing command-line tools

`filerepack doctor` prints which binaries are on PATH and, for anything missing,
OS-specific install commands (Homebrew / MacPorts on macOS, apt / dnf / pacman /
zypper / apk on Linux, Chocolatey / winget / Scoop on Windows). Only `7zz` or
`7z` is required for archive/OOXML work. Everything else enables extra formats.

Override a tool with an environment variable (`FILEREPACK_7ZZ`,
`FILEREPACK_JPEGOPTIM`, `FILEREPACK_JPEGTRAN`, `FILEREPACK_ZOPFLIPNG`,
`FILEREPACK_OPTIVORBIS`, …) or:

```toml
# ~/.config/filerepack/config.toml
[tools]
szip = "/opt/homebrew/bin/7zz"
qpdf = "/usr/local/bin/qpdf"
```

For other Linux or Windows package managers, run `filerepack doctor` and follow
the printed commands.

## What each tool is for

| Tool | Formats |
|------|---------|
| `7zz` or `7z` | ZIP, 7z, OOXML, nested archives |
| `zip` | Preferred rewrite for OOXML (docx/xlsx/pptx, …) |
| `jpegoptim` | JPEG (lossless strip, or `-m` with `--jpeg-quality`) |
| `jpegtran` | lossless JPEG (`-optimize -progressive`; mozjpeg or libjpeg-turbo). `--keep-meta` uses `-copy all` |
| `oxipng` / `optipng` | lossless PNG |
| `zopflipng` | extra lossless PNG pass when `--ultra` is set |
| `pngquant` | lossy PNG (`--png-quality` / `--lossy`) |
| `qpdf` | lossless PDF (default) |
| `gs` / `gswin64c` | lossy PDF (`--lossy` / `--pdf-profile`; default `/ebook`) |
| `gifsicle` | GIF |
| `dwebp` + `cwebp` | WebP |
| `svgo` or `scour` | SVG (XML minify is the fallback) |
| `magick` / `convert`, `tiffcp` | TIFF, HEIC, JPEG 2000, EXR, ICO, ICNS, DNG (tiffcp), BMP, TGA, PNM, PCX |
| `avifenc` + `avifdec` | AVIF (ImageMagick fallback) |
| `ffmpeg` | MP4, MKV, WebM, MOV, M4V, WMV, AVI, ASF, 3GP, MPEG-TS, ALAC/WavPack |
| `pigz` | faster gzip |
| `xz`, `bzip2`, `zstd`, `brotli`, `lz4`, `lzip`, `lzma`, `lzop`, `compress` | xz / bz2 / zst / br / lz4 / lz / lzma / lzo / .Z |
| `cjxl` + `djxl` | JPEG XL |
| `gdcmconv` / `dcmcjpls` | DICOM JPEG-LS (uncompressed / RLE images) |
| `flac` | FLAC recompress |
| `h5repack`, `nccopy` | HDF5 / NetCDF |
| `mac` | Monkey's Audio (`.ape`) |
| `mp3packer` | lossless MP3 (`FILEREPACK_MP3PACKER`; not in Homebrew — see below) |
| `optivorbis` | Ogg Vorbis/Opus (`FILEREPACK_OPTIVORBIS`; not in Homebrew — see below) |
| `woff2_compress` / `woff2_decompress` | WOFF2 fallback |
| `unrar`, `rar` | RAR extract / rewrite (`rar` missing → 7z) |
| `duckdb` Python package | Parquet (`pip install 'filerepack[parquet]'`) |
| `pyarrow`, `fastavro` | ORC / Feather / Arrow / Avro (`pip install 'filerepack[data]'`) |
| `fonttools` | WOFF / WOFF2 (`pip install 'filerepack[fonts]'`) |
| `mutagen` | Cover art in MP3/FLAC/M4A/Ogg/APE (`pip install 'filerepack[media]'`) |
| `pikepdf` | Lossless PDF image streams (`pip install 'filerepack[pdf]'`; `--lossy` still uses Ghostscript) |

## macOS (Homebrew)

```bash
brew install p7zip zip jpegoptim jpeg pngquant oxipng zopfli
brew install qpdf ghostscript gifsicle webp imagemagick libtiff ffmpeg
brew install pigz xz zstd brotli lz4 lzip lzop jpeg-xl hdf5 netcdf flac gdcm dcmtk
npm install -g svgo   # or: pip install scour
pip install 'filerepack[data]' 'filerepack[fonts]' 'filerepack[progress]' \
  'filerepack[media]' 'filerepack[pdf]'
```

`p7zip` may install `7z` instead of `7zz`. filerepack accepts either.

`mp3packer` and `optivorbis` are not in Homebrew. Install them from the
[mp3packer](#mp3packer-not-packaged) and [optivorbis](#optivorbis-not-packaged)
GitHub releases below.

## Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install zip p7zip-full jpegoptim pngquant optipng
sudo apt-get install qpdf ghostscript gifsicle webp imagemagick libtiff-tools ffmpeg
sudo apt-get install pigz xz-utils bzip2 zstd brotli lz4 lzip lzop ncompress flac unrar
sudo apt-get install libjxl-tools hdf5-tools netcdf-bin libgdcm-tools dcmtk
sudo apt-get install python3-scour   # or: sudo npm install -g svgo
pip install 'filerepack[data]' 'filerepack[fonts]' 'filerepack[progress]' \
  'filerepack[media]' 'filerepack[pdf]'
```

`optivorbis` is not in apt. Use the [GitHub CLI zip](#optivorbis-not-packaged).

## Windows (Chocolatey)

```powershell
choco install 7zip jpegoptim pngquant qpdf ghostscript gifsicle webp imagemagick ffmpeg lz4 xz dcmtk -y
npm install -g svgo
pip install 'filerepack[data]' 'filerepack[fonts]' 'filerepack[progress]' `
  'filerepack[media]' 'filerepack[pdf]'
```

Add `C:\Program Files\7-Zip` to PATH. filerepack looks for `7zz` then `7z`.
`optivorbis` is not in Chocolatey; use the [GitHub CLI zip](#optivorbis-not-packaged).

## mp3packer (not packaged)

`mp3packer` losslessly rearranges MP3 frames. It is not in Homebrew, MacPorts,
apt, or Chocolatey. filerepack needs the original CLI:
`mp3packer [-z] in.mp3 out.mp3`. `--ultra` passes `-z` (Huffman recompression).

Pre-built binaries for macOS, Linux, and Windows:
[Snesnopic/mp3packer releases](https://github.com/Snesnopic/mp3packer/releases).

### macOS

Apple Silicon:

```bash
curl -L -o mp3packer.zip \
  https://github.com/Snesnopic/mp3packer/releases/download/v2.05-fork/mp3packer-macos-arm64.zip
unzip mp3packer.zip
chmod +x mp3packer
sudo mv mp3packer /usr/local/bin/mp3packer
```

Intel Mac: download `mp3packer-macos-x64.zip` instead. If the zip unpacks into a
folder, copy the `mp3packer` binary from inside it. If Gatekeeper blocks it:

```bash
xattr -d com.apple.quarantine /usr/local/bin/mp3packer
```

Point filerepack at a custom path with `FILEREPACK_MP3PACKER` or:

```toml
# ~/.config/filerepack/config.toml
[tools]
mp3packer = "/path/to/mp3packer"
```

Build from source (optional), same fork, `dune-port` branch:

```bash
brew install opam
opam init
eval "$(opam env)"
opam install dune dune-configurator
git clone -b dune-port https://github.com/Snesnopic/mp3packer.git
cd mp3packer
dune build
sudo cp _build/default/mp3packer.exe /usr/local/bin/mp3packer
```

Linux/Windows zips from the same release: `mp3packer-ubuntu-arm64.zip`,
`mp3packer-ubuntu-x64.zip`, `mp3packer-windows-x64.zip`.

## optivorbis (not packaged)

`optivorbis` losslessly remuxes Ogg Vorbis (and Opus in an Ogg container). It is
not in Homebrew, MacPorts, apt, or Chocolatey, and Cargo cannot install it:
crates.io `optivorbis` is a library, and the CLI package is unpublished.

filerepack needs the official CLI: `optivorbis in.ogg out.ogg`. Pre-built
binaries: [OptiVorbis/OptiVorbis releases](https://github.com/OptiVorbis/OptiVorbis/releases).

### macOS

Apple Silicon (puts the binary on the Homebrew PATH):

```bash
curl -L -o optivorbis.zip \
  https://github.com/OptiVorbis/OptiVorbis/releases/download/v0.3.2/OptiVorbis.CLI.aarch64-apple-darwin.zip
unzip optivorbis.zip
chmod +x optivorbis
xattr -d com.apple.quarantine optivorbis 2>/dev/null || true
mv optivorbis "$(brew --prefix)/bin/optivorbis"
```

Intel Mac: download `OptiVorbis.CLI.x86_64-apple-darwin.zip` instead. If `brew`
is missing, move the binary to `/usr/local/bin/optivorbis`. If Gatekeeper still
blocks it:

```bash
xattr -d com.apple.quarantine "$(brew --prefix)/bin/optivorbis"
```

Point filerepack at a custom path with `FILEREPACK_OPTIVORBIS` or:

```toml
# ~/.config/filerepack/config.toml
[tools]
optivorbis = "/path/to/optivorbis"
```

### Linux

```bash
# x86_64; for ARM use OptiVorbis.CLI.aarch64-unknown-linux-musl.zip
curl -L -o optivorbis.zip \
  https://github.com/OptiVorbis/OptiVorbis/releases/download/v0.3.2/OptiVorbis.CLI.x86_64-unknown-linux-musl.zip
unzip optivorbis.zip
chmod +x optivorbis
sudo mv optivorbis /usr/local/bin/optivorbis
```

### Windows

Download `OptiVorbis.CLI.x86_64-pc-windows-gnu.zip` from the same release, unzip
`optivorbis.exe`, and put it on PATH.

## Verify

```bash
filerepack doctor
```
