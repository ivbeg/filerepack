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

## Optional extras

Some formats need extra Python packages. This is the canonical list; feature
sections elsewhere in the docs link back here.

| Extra | Enables |
|-------|---------|
| `parquet` | DuckDB Parquet recompress |
| `data` | Parquet plus ORC / Avro / Feather / Arrow |
| `fonts` | WOFF / WOFF2 via fonttools |
| `progress` | `rich` progress bars for `repack` and `bulk --progress` |
| `media` | mutagen cover-art walking in MP3 / FLAC / M4A / Ogg / APE |
| `pdf` | pikepdf lossless PDF image-stream walking |

```bash
pip install 'filerepack[parquet]'
pip install 'filerepack[data]'
pip install 'filerepack[fonts]'
pip install 'filerepack[progress]'
pip install 'filerepack[media]'
pip install 'filerepack[pdf]'
```

## External tools

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
