## 1. Identification and verification
- [x] 1.1 Add `dcm`, `dicom`, and `dic` to `STANDALONE_EXTS`
- [x] 1.2 Map all three keys in `_PACKERS` to `pack_dcm` with category `image`
- [x] 1.3 Add `verify_output` kind `dcm` that checks `DICM` at offset 128 (do not rely on the 16-byte peek)
- [x] 1.4 Unit tests: `identify_filename` / `is_supported_filename` / `filename_exts` for the three aliases; `verify_output` accept/reject

## 2. Safety gate
- [x] 2.1 Add a small DICOM reader: require `DICM` preamble, parse File Meta Transfer Syntax UID, walk the dataset for Pixel Data and Digital Signatures Sequence
- [x] 2.2 Skip unless transfer syntax is uncompressed (IVRLE / EVRLE / EVRBE) or RLE lossless
- [x] 2.3 Skip on missing pixel data, signatures present, or parse failure
- [x] 2.4 Unit tests with crafted headers/datasets for each skip path (no encoder required)

## 3. Packer and tools
- [x] 3.1 Register optional `ToolSpec`s for `gdcmconv` and `dcmcjpls` with `FILEREPACK_GDCMCONV` / `FILEREPACK_DCMCJPLS`
- [x] 3.2 Add install-hint packages (`gdcm` / `libgdcm-tools`, `dcmtk`) for brew, apt, dnf, pacman, and choco where they exist
- [x] 3.3 Implement `pack_dcm` in `codecs.py`: safety gate, then `gdcmconv --jpegls`, else `dcmcjpls`; temp file + `_commit_output(..., verify='dcm')`
- [x] 3.4 Do not pass `--lossy` or quality flags into the encoder; do not call ImageMagick
- [x] 3.5 Tests: missing tools → `None`; `--no-images` dispatch skip; mocked successful/failed encoder; `--lossy` still lossless

## 4. Docs
- [x] 4.1 README formats table: DICOM (`dcm`, `dicom`, `dic`), lossless JPEG-LS, optional DCMTK/GDCM
- [x] 4.2 `docs/tools.md` and `docs/cli.md` examples; note that `--lossy` does not apply
- [x] 4.3 CHANGELOG Added entry

## 5. Validation
- [x] 5.1 `make test` and `make lint`
- [x] 5.2 Optional integration: if `gdcmconv` or `dcmcjpls` is installed, recompress a tiny uncompressed fixture and assert a still-valid `DICM` file
- [x] 5.3 `filerepack doctor` shows the new tools without changing the exit-1 rule
