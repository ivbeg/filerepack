# Change: Add lossless DICOM (.dcm) recompression

## Why
Medical imaging archives often store uncompressed or RLE DICOM instances. filerepack already recompresses related pixel codecs (JPEG, JPEG 2000, TIFF) but ignores `.dcm` / `.dicom` / `.dic`, so bulk runs skip those files. A lossless, metadata-preserving rewrite would shrink many studies without changing diagnostic pixels.

## What Changes
- Treat `.dcm`, `.dicom`, and `.dic` as standalone image files in `STANDALONE_EXTS` and `_PACKERS`
- Add `pack_dcm()` that losslessly recompresses **uncompressed or RLE** image DICOM to JPEG-LS via optional `gdcmconv` (preferred) or DCMTK `dcmcjpls`
- Skip anything that is not a safe candidate: missing `DICM` preamble, no pixel data, digital signatures, video/lossy transfer syntaxes, or instances already on JPEG-LS / JPEG 2000 lossless
- `--lossy` and JPEG/PNG quality flags MUST NOT apply to DICOM
- Register the tools in `filerepack doctor` / install hints; leave the source file untouched when no tool is present
- Do **not** use ImageMagick/`convert` on DICOM

## Impact
- Affected specs: `dicom` (new)
- Affected code: `filerepack/consts.py`, `filerepack/codecs.py`, `filerepack/repack.py`, `filerepack/tools.py`, `filerepack/install_hints.py`, `filerepack/utils.py`, docs, tests
- No CLI flag changes; `--no-images` already skips the `image` packer category
- Not breaking: new optional format; missing tools behave like JPEG XL / DNG today
