## MODIFIED Requirements

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

### Requirement: DICOM Tool Discovery
The system SHALL register `gdcmconv` and `dcmcjpls` as optional tools in `TOOL_SPECS`. `filerepack doctor` SHALL report their status and OS-specific install commands. A missing DICOM tool SHALL NOT make `doctor` exit 1 (only the required archiver does that).

#### Scenario: Doctor lists DICOM tools
- **WHEN** the user runs `filerepack doctor`
- **THEN** the table includes `gdcmconv` and `dcmcjpls` with purpose text that mentions DICOM
- **AND** a missing tool shows an install command for the current OS when a package mapping exists

#### Scenario: Environment override
- **WHEN** `FILEREPACK_GDCMCONV` or `FILEREPACK_DCMCJPLS` points at a valid binary
- **THEN** `resolve_tool` returns that path
