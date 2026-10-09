---
title: "Installation"
description: "Install filerepack with pip, extras, and optional system tools"
---
# Installation

Python 3.9+ on macOS, Linux, or Windows.

### Using pip

```bash
pip install filerepack
```

### Using uv or pipx

```bash
uv tool install filerepack
# or
pipx install filerepack
```

### From source

```bash
git clone https://github.com/ivbeg/filerepack.git
cd filerepack
pip install -e ".[dev]"
```

Source releases include test fixtures/helpers and pytest configuration; runtime
wheels include the application package. Builds require setuptools 77.0.3+ for
`BSD-3-Clause` SPDX metadata; PEP 517 installs it in an isolated build environment.
For development/release checks, the `dev` extra also includes `build`:

```bash
python dev/validate_distribution.py
```

This builds and installs both artifacts in temporary virtual environments and
checks the extracted tests against the installed runtime, CLI and license metadata.
Optional integrations remain explicit test skips when their dependencies are absent.

## Optional extras

Some formats need extra Python packages. This is the canonical list; feature
sections elsewhere in the docs link back here.

| Extra | Enables |
|-------|---------|
| `parquet` | PyArrow 19+ Parquet recompress with preservation checks |
| `data` | Parquet plus ORC / Avro / Feather / Arrow |
| `fonts` | WOFF / WOFF2 via fonttools |
| `progress` | `rich` progress bars for `repack` and `bulk --progress` |
| `media` | mutagen cover-art walking in MP3 / FLAC / M4A / Ogg / APE |
| `pdf` | pikepdf image walking plus Pillow image decoding; lossless comparison needs qpdf 11+ |
| `validation` | Pillow raster verification and pikepdf protection-inspection fallback |
| `ole` | olefile 0.47 for legacy DOC/XLS/PPT compaction; also requires the separately built native writer |
| `ole-recompress` | olefile and psutil for opt-in OLE EMF/WMF and PPT embedded-object recompression; Zopfli 0.4.3 on Python 3.10+, zlib on Python 3.9; native writer 0.4.0+ |
| `dicom` | pydicom, NumPy and pyjpegls for DICOM parsing and decoded-pixel verification |
| `fits` | Astropy/CFITSIO lossless FITS tiled-image compression and verification |
| `blend` | Zstandard compression/decompression for Blender projects; gzip uses the standard library |
| `duckdb` | DuckDB 1.4.2+ and PyArrow 19+ for verified offline database compaction |
| `tgs` | Zopfli for stronger Telegram TGS compression; standard-library gzip is the fallback |

```bash
pip install 'filerepack[parquet]'
pip install 'filerepack[data]'
pip install 'filerepack[fonts]'
pip install 'filerepack[progress]'
pip install 'filerepack[media]'
pip install 'filerepack[pdf]'
pip install 'filerepack[validation]'
pip install 'filerepack[ole]'
pip install 'filerepack[ole-recompress]'
pip install 'filerepack[dicom]'
pip install 'filerepack[fits]'
pip install 'filerepack[blend]'
pip install 'filerepack[duckdb]'
pip install 'filerepack[tgs]'
```

## External tools

HDF5/NetCDF structural validation additionally requires `pip install h5py netCDF4`
alongside the `h5repack`/`nccopy` tools. Unsupported or missing decoders leave
candidates unpublished.

Most formats also need command-line binaries (`7zz`, `jpegoptim`, `qpdf`,
`ffmpeg`, …). Only `7zz` or `7z` is required for archive and OOXML work.
Everything else enables extra formats.

See what you have and how to install the rest on this OS:

```bash
filerepack doctor
```

Install commands use Homebrew or MacPorts on macOS, apt / dnf / pacman / zypper
/ apk on Linux, and Chocolatey / winget / Scoop on Windows. `mp3packer` and
`optivorbis` are not packaged; doctor points at GitHub CLI zips.

Full notes: [External tools](/tools/). Override paths with `FILEREPACK_7ZZ`
(and similar) or `~/.config/filerepack/config.toml`.

## Next steps

- [Quick start](/getting-started/quick-start)
- [Cookbook](/getting-started/cookbook)
- [When to use filerepack](/getting-started/when-to-use)
