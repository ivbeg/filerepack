---
title: "Supported formats"
description: "Format coverage, nested walking, and per-format tools"
slug: /formats
---

# Supported formats

filerepack identifies files by extension (including compound names such as
`archive.tar.gz`). Nested members inside archives are walked with the same
rules. Missing optional tools or Python extras leave the file unchanged.

JPEG, PNG, and PDF default to **lossless** tools. Use `--lossy`,
`--jpeg-quality`, `--png-quality`, or `--pdf-profile` for lossy codecs. Output
that is not smaller than the original is discarded unless `--allow-grow`.

CLI: [CLI reference](/commands/). Tools: [External tools](/tools/). Library:
[Python API](/library/).

## Nested walking

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten:

1. **ZIP family** (OOXML, ODF, EPUB, JAR, APK, …) — extract, pack members, rewrite as ZIP. OOXML-like files prefer Info-ZIP `zip` when it is on PATH so extra 7-Zip fields do not break Word/Excel.
2. **7z / RAR / CAB / WIM** — same walk; RAR is rewritten as 7z when `rar` is missing.
3. **Tarballs** (`tar`, `tar.gz` / `tgz`, `tar.bz2`, `tar.xz`, `tar.zst`, `tar.br`, `tar.lz4`, `tar.lzo`, `tar.lz`, `tar.lzma`, plus `gem` / `crate` / `unitypackage`) — unpack, pack members, rewrite the tarball. A compressed stream whose payload is a tar (`.gz`, `.zst`, …) is detected by peeking the first 512 decompressed bytes.
4. **Nested XML / JSON** inside those containers is minified (see [Markup](#markup-xml-json-svg)).
5. **`--no-archives`** skips nested archive rewriting. **`--no-images`** skips image, video, and audio packers (including cover art), not XML/JSON or PDF.

`--include-ext tar.gz` matches `foo.tar.gz`. `--include-ext gz` matches it too.
`--include-ext jpg` matches `.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.jif`, `.jfi`,
and `.thm`.

## Nested assets (not ZIP)

These run on the host file even when it is not an archive:

| Host | Extra / tool | What is packed |
|------|----------------|----------------|
| MP3, FLAC, M4A/M4B/MP4, Ogg, APE | `filerepack[media]` (mutagen) | Attached cover pictures, then the usual codec packer |
| XML / SVG | none | `data:image/…;base64` URIs decoded, packed, written back compact |
| PDF (lossless) | `filerepack[pdf]` (pikepdf) | Embedded JPEG / JPEG 2000 / Flate image streams, then qpdf |

If the extra is missing, or nothing shrinks, the host is left unchanged
(codec-only packers may still run). Encrypted or digitally signed PDFs skip
stream replacement; lossless qpdf may still run. `--lossy` / `--pdf-profile` /
`--jpeg-quality` skip pikepdf and use Ghostscript instead.

## Office and ZIP-family archives

Needs `7zz` or `7z`. OOXML also benefits from `zip`.

| Group | Extensions |
|-------|------------|
| Microsoft OOXML | `docx`, `docm`, `dotx`, `dotm`, `xlsx`, `xlsm`, `xltx`, `xltm`, `xlsb`, `xlam`, `pptx`, `pptm`, `ppsx`, `ppsm`, `potx`, `potm`, `ppam`, `sldx`, `sldm`, `thmx`, `vsdx`, `vsdm`, `vstx`, `vstm`, `vssx`, `vssm`, `accdt`, `crtx`, `gcsx`, `glox`, `gqsx`, `vdw`, `zipx`, `xps`, `oxps`, `dwfx` |
| OpenDocument / OpenOffice | `odt`, `ods`, `odp`, `odg`, `odf`, `odb`, `odc`, `odi`, `odm`, `ott`, `ots`, `otp`, `otg`, `oth`, `otm`, `otc`, `oti`, `sxw`, `sxc`, `sxi`, `sxd`, `sxg`, `sxm`, `stw`, `stc`, `sti`, `std` |
| Apple iWork | `pages`, `key`, `numbers`, `kth`, `nmbtemplate`, `template` |
| E-books / packages | `epub`, `lpf`, `ibooks`, `oxt` |
| App / language packages | `jar`, `egg`, `whl`, `war`, `ear`, `aar`, `apk`, `aab`, `xapk`, `apks`, `ipa`, `appx`, `msix`, `appxbundle`, `nupkg`, `snupkg`, `vsix`, `xpi`, `crx`, `npz` |
| Design / comics / other ZIP | `zip`, `xmind`, `idml`, `sketch`, `kra`, `ora`, `xd`, `afpub`, `afphoto`, `afdesign`, `scrivx`, `cbz`, `kmz`, `3mf`, `usdz`, `ifczip`, `fcstd`, `mxl`, `rtb`, `onepkg`, `wgt`, `air`, `pk3`, `xap`, `ipsw`, `osk`, `oex`, `puz`, `rmskin`, `notebook`, `nbk`, `mcworld`, `mcpack`, `mcaddon` |

`.otf` is packed as ODF only when the file is a ZIP (OpenType fonts are skipped).

Other archive families:

| Family | Extensions | Notes |
|--------|------------|--------|
| 7z | `7z`, `cb7` | |
| RAR | `rar`, `cbr` | Rewritten as `.7z` if `rar` is missing |
| CAB / WIM | `cab`, `wim` | 7-Zip writable containers |
| Tar | `tar`, `cbt`, `tgz`, `taz`, `tbz`, `tbz2`, `txz`, `tzst`, `tlz`, `tzo`, `gem`, `crate`, `unitypackage` | Inner files packed, then the tarball rewritten |

## Markup (XML, JSON, SVG)

| Kind | Extensions | Behaviour |
|------|------------|-----------|
| JSON | `json` | Compact UTF-8 (`separators=(',', ':')`). Invalid JSON is skipped |
| XML | `xml`, `xhtml`, `kml`, `gpx`, `dae`, `rss`, `atom`, `xmp`, `xsl`, `xslt`, `fb2` | Minify ignorable whitespace; text nodes unchanged; `xml:space="preserve"` kept. Unparseable XML is skipped |
| SVG | `svg` | `svgo` or `scour` first; XML minify if both are missing. `data:` images are packed |
| SVGZ | `svgz` | Decompress, pack as SVG, recompress |

These are **document** packers: `--no-images` does not skip them. Nested
`word/*.xml` inside a `.docx` is minified during the ZIP walk.

## Images

`--no-images` skips this category. Lossless JPEG/PNG strip EXIF/ICC unless
`--keep-meta`.

| Kind | Extensions | Tools |
|------|------------|-------|
| JPEG | `jpg`, `jpeg`, `jpe`, `jfif`, `jif`, `jfi`, `thm` | Lossless: `jpegtran` then `jpegoptim`. Lossy: jpegoptim `-m` (`--jpeg-quality` / `--lossy`) |
| PNG / APNG | `png`, `apng` | `oxipng` / `optipng`; `--ultra` also tries `zopflipng`. Lossy: `pngquant` |
| GIF | `gif` | `gifsicle` |
| WebP | `webp` | `dwebp` + `cwebp` |
| TIFF | `tif`, `tiff` | ImageMagick or `tiffcp` |
| AVIF | `avif` | `avifenc`/`avifdec` (ImageMagick fallback). `--lossy` selects a lossy encode |
| HEIC | `heic`, `heif` | ImageMagick. `--lossy` selects a lossy encode |
| JPEG XL | `jxl` | `cjxl` + `djxl` |
| JPEG 2000 | `jp2`, `j2k`, `jpf`, `jpx` | ImageMagick |
| OpenEXR / DNG | `exr`, `dng` | ImageMagick; DNG also `tiffcp` |
| ICO / CUR / ICNS | `ico`, `cur`, `icns` | ImageMagick |
| BMP / TGA / PNM / PCX | `bmp`, `dib`, `tga`, `targa`, `pnm`, `ppm`, `pgm`, `pbm`, `pcx`, `dcx` | ImageMagick lossless |
| Photoshop | `psd` | Recompress ZIP-encoded layer/composite channels (RLE/raw left unchanged) |
| DICOM | `dcm`, `dicom`, `dic` | Lossless JPEG-LS via `gdcmconv` or `dcmcjpls`. Signed, non-image, and already-compressed instances are skipped. `--lossy` does not apply |

## Documents (PDF)

| Kind | Extensions | Lossless | Lossy |
|------|------------|----------|-------|
| PDF | `pdf` | pikepdf stream walk (`filerepack[pdf]`) then `qpdf`. Without pikepdf: qpdf only | Ghostscript `--lossy` (`/ebook` unless `--pdf-profile`) or `--pdf-profile`. `--jpeg-quality` sets Distiller QFactor |
| Illustrator | `ai` | Same as PDF when the file is a PDF wrapper | Same Ghostscript path |

## Video and audio

`--no-images` skips these. WMV/AVI/ASF/3GP/MPEG-TS convert to MP4 unless
`--no-convert-container`. MKV/WebM/MOV/M4V keep their container.

| Kind | Extensions | Tools |
|------|------------|-------|
| Video | `mp4`, `mkv`, `webm`, `mov`, `m4v`, `wmv`, `avi`, `asf`, `3gp`, `ts`, `mts`, `m2ts` | `ffmpeg`. `--wmv-lossless` is CRF 0 (VP9 lossless for WebM) |
| FLAC | `flac` | `flac` recompress; covers with `filerepack[media]` |
| ALAC / M4A | `m4a`, `m4b` | ffmpeg ALAC when applicable; covers with mutagen |
| Ogg / Opus | `ogg`, `opus`; `oga` | `optivorbis` for Vorbis/Opus. FLAC-in-Ogg `.oga` stays on ffmpeg |
| WavPack / TTA | `wv`, `tta` | ffmpeg |
| Monkey's Audio | `ape` | `mac` when installed; covers with mutagen |
| MP3 | `mp3` | `mp3packer` (lossless frame packing). `--ultra` passes `-z`. Covers with mutagen |

`optivorbis` and `mp3packer` are not in Homebrew/apt; see [External tools](/tools/).

## Compressed streams and data

| Kind | Extensions | Tools / extra |
|------|------------|----------------|
| gzip / xz / bzip2 / zstd / brotli | `gz`, `xz`, `bz2`, `zst`, `br` | `pigz`/`gzip`, `xz`, `bzip2`, `zstd`, `brotli` |
| lz4 / lzip / lzma / lzo / compress | `lz4`, `lz`, `lzma`, `lzo`, `z` | `lz4`, `lzip`, `lzma`, `lzop`, `compress` |
| SQLite | `sqlite`, `sqlite3`, `db`, `gpkg`, `mbtiles` | `VACUUM`. `.db` still requires the `SQLite format 3` header |
| Parquet | `parquet` | `filerepack[parquet]` or `[data]` (DuckDB). `--ultra` is zstd level 22 |
| ORC / Avro / Feather / Arrow | `orc`, `avro`, `feather`, `arrow`, `ipc` | `filerepack[data]` |
| HDF5 / NetCDF | `h5`, `hdf5`, `hdf`, `nc`, `nc4` | `h5repack`, `nccopy` |
| WOFF / WOFF2 | `woff`, `woff2` | `filerepack[fonts]` (fonttools) or `woff2_compress` / `woff2_decompress` |

## Not supported

These stay untouched (no extract + rewrite):

- Signed installers: `deb`, `rpm`, `pkg`, `dmg`
- Disc/library archives 7-Zip cannot create: `iso`, `cpio`, `ar` / `a` / `lib`
- OpenType `.otf` fonts (ZIP ODF templates with that extension are packed)

## Python extras

```bash
pip install 'filerepack[parquet]'   # DuckDB Parquet
pip install 'filerepack[data]'      # Parquet + ORC/Avro/Feather/Arrow
pip install 'filerepack[fonts]'     # WOFF/WOFF2 via fonttools
pip install 'filerepack[progress]'  # rich progress bars
pip install 'filerepack[media]'     # mutagen cover-art walking
pip install 'filerepack[pdf]'       # pikepdf lossless PDF streams
```
