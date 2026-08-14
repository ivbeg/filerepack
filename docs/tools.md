# Installing command-line tools

`filerepack doctor` prints which binaries are on PATH and, for anything missing, OS-specific install commands (Homebrew / MacPorts on macOS, apt / dnf / pacman / zypper / apk on Linux, Chocolatey / winget / Scoop on Windows). Only `7zz` or `7z` is required for archive/OOXML work. Everything else enables extra formats.

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
| `gs` / `gswin64c` | lossy PDF (`--lossy` / `--pdf-profile`; default `/ebook`) |
| `gifsicle` | GIF |
| `dwebp` + `cwebp` | WebP |
| `svgo` or `scour` | SVG |
| `magick` / `convert`, `tiffcp` | TIFF, HEIC, JPEG 2000, EXR, ICO, ICNS, DNG (tiffcp) |
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
| `woff2_compress` / `woff2_decompress` | WOFF2 fallback |
| `unrar`, `rar` | RAR extract / rewrite (`rar` missing → 7z) |
| `duckdb` Python package | Parquet (`pip install 'filerepack[parquet]'`) |
| `pyarrow`, `fastavro` | ORC / Feather / Arrow / Avro (`pip install 'filerepack[data]'`) |
| `fonttools` | WOFF / WOFF2 (`pip install 'filerepack[fonts]'`) |

## macOS (Homebrew)

```bash
brew install p7zip zip jpegoptim pngquant oxipng
brew install qpdf ghostscript gifsicle webp imagemagick libtiff ffmpeg
brew install pigz xz zstd brotli lz4 lzip lzop jpeg-xl hdf5 netcdf flac gdcm dcmtk
npm install -g svgo   # or: pip install scour
pip install 'filerepack[data]' 'filerepack[fonts]' 'filerepack[progress]'
```

`p7zip` may install `7z` instead of `7zz`. filerepack accepts either.

`mp3packer` is not in Homebrew. Install it from the [GitHub release](#mp3packer-not-packaged) below.

## Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install zip p7zip-full jpegoptim pngquant optipng
sudo apt-get install qpdf ghostscript gifsicle webp imagemagick libtiff-tools ffmpeg
sudo apt-get install pigz xz-utils bzip2 zstd brotli lz4 lzip lzop ncompress flac unrar
sudo apt-get install libjxl-tools hdf5-tools netcdf-bin libgdcm-tools dcmtk
sudo apt-get install python3-scour   # or: sudo npm install -g svgo
pip install 'filerepack[data]' 'filerepack[fonts]' 'filerepack[progress]'
```

## Windows (Chocolatey)

```powershell
choco install 7zip jpegoptim pngquant qpdf ghostscript gifsicle webp imagemagick ffmpeg lz4 xz dcmtk -y
npm install -g svgo
pip install 'filerepack[data]' 'filerepack[fonts]' 'filerepack[progress]'
```

Add `C:\Program Files\7-Zip` to PATH. filerepack looks for `7zz` then `7z`.

## mp3packer (not packaged)

`mp3packer` losslessly rearranges MP3 frames. It is not in Homebrew, MacPorts, apt, or Chocolatey. filerepack needs the original CLI: `mp3packer [-z] in.mp3 out.mp3`. `--ultra` passes `-z` (Huffman recompression).

Pre-built binaries for macOS, Linux, and Windows: [Snesnopic/mp3packer releases](https://github.com/Snesnopic/mp3packer/releases).

### macOS

Apple Silicon:

```bash
curl -L -o mp3packer.zip \
  https://github.com/Snesnopic/mp3packer/releases/download/v2.05-fork/mp3packer-macos-arm64.zip
unzip mp3packer.zip
chmod +x mp3packer
sudo mv mp3packer /usr/local/bin/mp3packer
```

Intel Mac: download `mp3packer-macos-x64.zip` instead. If the zip unpacks into a folder, copy the `mp3packer` binary from inside it. If Gatekeeper blocks it:

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

Linux/Windows zips from the same release: `mp3packer-ubuntu-arm64.zip`, `mp3packer-ubuntu-x64.zip`, `mp3packer-windows-x64.zip`.

## Verify

```bash
filerepack doctor
```
