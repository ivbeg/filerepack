# Change: Close Chisel parity gaps (nested assets, formats, encoders)

## Why
[Chisel](https://github.com/Snesnopic/chisel) losslessly walks nested assets that filerepack never opens (cover art, PDF streams, XML/JSON inside Office ZIPs) and supports several formats we skip. Those gaps leave savings on the table for music libraries, scanned PDFs, and OOXML/ODF/EPUB without changing filerepack’s Python + optional-CLI model.

## What Changes
- Treat XML and JSON as first-class standalone packers so nested `word/*.xml` / `.json` inside ZIP-based documents are minified during the existing deep walk
- Extract and reinsert **embedded assets**: audio/video cover art, `data:` images in XML/SVG, and (later) PDF streams, then run the existing image packers on them
- Prefer stronger lossless encoders when present (`jpegtran` from mozjpeg, `zopflipng`) without dropping current fallbacks
- Add `--keep-meta` so lossless JPEG/PNG can keep EXIF/ICC (today JPEG always uses `jpegoptim --strip-all`)
- Register cheap aliases and raster/archive formats that 7-Zip or ImageMagick can already round-trip
- Add Ogg Vorbis/Opus via optional `optivorbis` (same “optional binary” pattern as `mp3packer`)

Deferred on purpose (see design.md): PE resources, OLE/CFBF, SWF, STL, Lua, miniSEED, Kanzi, GFT, RDB, stdin/stdout, regex include/exclude, encoder pipe/parallel mode, semantic `--verify-checksums`.

## Impact
- Affected specs: `nested-assets` (new), `xml-json` (new), `encoder-quality` (new), `formats` (new)
- Affected code: `filerepack/consts.py`, `formats.py`, `repack.py`, `codecs.py`, `tools.py`, `install_hints.py`, `models.py`, `__main__.py`, `pyproject.toml`, docs, tests
- New optional extras: `filerepack[media]` (mutagen), `filerepack[pdf]` (pikepdf)
- New optional tools: `jpegtran`, `zopflipng`, `optivorbis`
- **Not breaking:** lossless JPEG still strips metadata unless `--keep-meta`; missing extras/tools leave files unchanged
- Does not conflict with `add-dicom-support` or `improve-lossy-pdf-compression` (PDF stream walking is the lossless pikepdf path those changes deferred)
