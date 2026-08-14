## ADDED Requirements

### Requirement: DICOM Format Identification
The system SHALL treat filenames ending in `.dcm`, `.dicom`, or `.dic` (case-insensitive) as standalone image files. `identify_filename` SHALL return a `FileKind` with `family` `standalone` and packer key `dcm`. These extensions SHALL appear in `STANDALONE_EXTS` and SHALL match `--include-ext` / `--exclude-ext` filters.

#### Scenario: .dcm is a standalone image
- **WHEN** `identify_filename` is called with `scan.dcm`
- **THEN** it returns a kind whose `family` is `standalone` and whose packer key is `dcm`
- **AND** `is_supported_filename('scan.dcm')` is true

#### Scenario: Aliases
- **WHEN** `identify_filename` is called with `study.dicom` or `image.dic`
- **THEN** each returns a standalone `dcm` packer kind

#### Scenario: Extension filter
- **WHEN** bulk is run with `--include-ext dcm`
- **THEN** `scan.dcm` is eligible and `scan.dicom` is also eligible via the shared packer key or listed alias
- **AND** `--exclude-ext dcm` excludes `.dcm` files

#### Scenario: Nested archive member
- **WHEN** an archive contains `inner/slice.dcm` and image packing is enabled
- **THEN** the member is dispatched to the DICOM packer during the existing nested walk

### Requirement: Lossless DICOM Recompression
The system SHALL losslessly recompress eligible DICOM images to JPEG-LS using `gdcmconv` when it is on PATH (or `FILEREPACK_GDCMCONV`), otherwise DCMTK `dcmcjpls` (or `FILEREPACK_DCMCJPLS`). The packer SHALL write a temp file, verify it, and `os.replace` onto the original only when commit rules pass. ImageMagick `convert` / `magick` SHALL NOT be used. The packer SHALL be registered as `_PACKERS['dcm']` with category `image`.

#### Scenario: Uncompressed image with gdcmconv
- **WHEN** `pack_dcm` is given an uncompressed image DICOM and `gdcmconv` is available
- **THEN** it runs `gdcmconv` with JPEG-LS lossless flags to a temp path
- **AND** a smaller valid output is committed over the original

#### Scenario: Fallback to dcmcjpls
- **WHEN** `gdcmconv` is missing and `dcmcjpls` is available
- **THEN** `pack_dcm` uses `dcmcjpls` instead
- **AND** the original is left in place if that command fails

#### Scenario: Tool missing
- **WHEN** neither `gdcmconv` nor `dcmcjpls` is available
- **THEN** `pack_dcm` returns `None`
- **AND** the source file is unchanged

#### Scenario: --no-images
- **WHEN** options have `pack_images=False` (CLI `--no-images`)
- **THEN** `_dispatch_packer` does not call `pack_dcm`

#### Scenario: Commit rules
- **WHEN** the JPEG-LS output is not smaller than the original and `--allow-grow` is not set
- **THEN** the original file is kept
- **AND** `--min-savings` applies the same way as other standalone packers

### Requirement: Unsafe DICOM Instances Are Skipped
The system SHALL leave a DICOM file unchanged unless all of the following hold: bytes 128–131 are `DICM`; File Meta Transfer Syntax UID is one of Implicit VR LE, Explicit VR LE, Explicit VR BE, or RLE Lossless; Pixel Data `(7FE0,0010)` is present; Digital Signatures Sequence `(FFFA,FFFA)` is absent. Parse failure SHALL skip the file. `--lossy`, `--jpeg-quality`, and `--png-quality` SHALL NOT change DICOM encoding.

#### Scenario: Missing DICM preamble
- **WHEN** a `.dcm` file has no `DICM` magic at offset 128
- **THEN** the packer returns `None` without running an encoder
- **AND** the file is unchanged

#### Scenario: Already compressed or video transfer syntax
- **WHEN** Transfer Syntax UID is JPEG, JPEG-LS, JPEG 2000, Deflated, MPEG, or HEVC
- **THEN** the file is skipped

#### Scenario: No pixel data
- **WHEN** the dataset has no Pixel Data element (for example DICOMDIR or a structured report)
- **THEN** the file is skipped

#### Scenario: Digitally signed instance
- **WHEN** Digital Signatures Sequence `(FFFA,FFFA)` is present
- **THEN** the file is skipped

#### Scenario: Unreadable dataset
- **WHEN** File Meta or dataset parsing fails
- **THEN** the file is skipped (fail closed)

#### Scenario: --lossy does not apply
- **WHEN** `filerepack repack scan.dcm --lossy` is run on an eligible file
- **THEN** encoding remains JPEG-LS lossless
- **AND** no lossy JPEG or near-lossless JPEG-LS flags are passed to the tool

### Requirement: DICOM Tool Discovery
The system SHALL register `gdcmconv` and `dcmcjpls` as optional tools in `TOOL_SPECS`. `filerepack doctor` SHALL report their status and OS-specific install commands. A missing DICOM tool SHALL NOT make `doctor` exit 1 (only the required archiver does that).

#### Scenario: Doctor lists DICOM tools
- **WHEN** the user runs `filerepack doctor`
- **THEN** the table includes `gdcmconv` and `dcmcjpls` with purpose text that mentions DICOM
- **AND** a missing tool shows an install command for the current OS when a package mapping exists

#### Scenario: Environment override
- **WHEN** `FILEREPACK_GDCMCONV` or `FILEREPACK_DCMCJPLS` points at a valid binary
- **THEN** `resolve_tool` returns that path

### Requirement: DICOM Output Verification
`verify_output` SHALL accept kind `dcm` (and treat `dicom` / `dic` as the same check): the file is non-empty and bytes 128–131 equal `DICM`. A failed verification SHALL discard the temp output and leave the original file in place.

#### Scenario: Valid DICOM magic
- **WHEN** `verify_output` is called on a file whose offset 128 is `DICM`
- **THEN** it returns true for kind `dcm`

#### Scenario: Reject non-DICOM output
- **WHEN** the encoder writes a file without `DICM` at offset 128
- **THEN** verification fails
- **AND** the original `.dcm` is not replaced
