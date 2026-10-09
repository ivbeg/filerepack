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
| `serialization` | Passive RDS/RDA/RData, PT/PTH checkpoint and SAV/experimental ZSAV handlers with worker isolation |
| `scientific` | NumPy, h5py, netCDF4, tifffile and imagecodecs for preserving HDF5/NetCDF/TIFF and experimental MAT profiles; HDF5 also needs `h5repack` |
| `zarr` | Zarr 2.18–2.x, NumPy and compatible numcodecs for complete offline local v2 stores via `repack-store` |
| `onnx` | Bounded ONNX inspection and checker; no recompression writer |
| `tracev3` | LZ4 and worker isolation for archived Apple Unified Log chunk streams |
| `dicom` | pydicom, NumPy and pyjpegls for DICOM parsing and decoded-pixel verification |
| `fits` | Astropy/CFITSIO lossless FITS tiled-image compression and verification |
| `blend` | Zstandard compression/decompression for Blender projects; gzip uses the standard library |
| `duckdb` | DuckDB 1.4.2+ and PyArrow 19+ for verified offline database compaction |
| `tgs` | Zopfli for stronger Telegram TGS compression; standard-library gzip is the fallback |
| `dev` | Build, pytest/coverage, lint/type checks and selected integration readers for repository development |

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
pip install 'filerepack[serialization]'
pip install 'filerepack[scientific]'
pip install 'filerepack[zarr]'
pip install 'filerepack[onnx]'
pip install 'filerepack[tracev3]'
pip install 'filerepack[dicom]'
pip install 'filerepack[fits]'
pip install 'filerepack[blend]'
pip install 'filerepack[duckdb]'
pip install 'filerepack[tgs]'
```

Extras can be combined, for example `pip install 'filerepack[data,pdf,validation]'`.
With uv or pipx, install the extras into the tool's own environment:
`uv tool install 'filerepack[data,pdf,validation]'` or
`pipx install 'filerepack[data,pdf,validation]'`. Installing them with a separate
system `pip` does not add them to an isolated tool environment.

## External tools

Install `filerepack[scientific]` for HDF5/NetCDF readers and native writers.
HDF5 also requires `h5repack`; NetCDF uses the Python netCDF4 writer and does
not require `nccopy`. Unsupported or missing decoders leave candidates unpublished.

Most formats also need command-line binaries (`7zz`, `jpegoptim`, `qpdf`,
`ffmpeg`, …). `7zz` or `7z` is required for ZIP/OOXML and generic archive work;
native CPIO and WARC do not require it. `doctor` still exits `1` when the
archiver is missing. Other tools enable their corresponding formats.

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
