# dicom

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

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

### Requirement: Unsafe DICOM Instances Are Skipped

The system SHALL leave a DICOM source unchanged unless bytes 128–131 are DICM; the File Meta Transfer Syntax is Implicit VR LE, Explicit VR LE, Explicit VR BE, or RLE Lossless; valid Pixel Data is present; and Digital Signatures Sequence `(FFFA,FFFA)` is absent throughout the complete dataset and nested sequence items. Inspection SHALL continue after Pixel Data and validate declared lengths under documented nesting/element bounds. Parse failure, truncation, or exceeded bounds SHALL skip without encoding. `--lossy` and JPEG/PNG quality settings SHALL NOT change DICOM encoding.

#### Scenario: Signature after pixels

- **WHEN** a signature sequence occurs after Pixel Data in normal tag order
- **THEN** the source SHALL be skipped without invoking an encoder

#### Scenario: Nested signature

- **WHEN** a signature sequence occurs within a nested sequence item
- **THEN** the source SHALL be skipped without invoking an encoder

#### Scenario: Malformed or ineligible dataset

- **WHEN** DICM is missing, syntax is unsupported/already compressed, pixels are absent/truncated, or parsing exceeds bounds
- **THEN** the source SHALL remain unchanged and the failure/skip reason SHALL identify the gate

#### Scenario: Lossy flag on eligible dataset

- **WHEN** lossy or image quality flags are supplied for an eligible unsigned DICOM
- **THEN** encoding SHALL remain lossless JPEG-LS

### Requirement: DICOM Output Verification

DICOM candidate verification SHALL require nonempty DICM-identified output, a structurally valid complete dataset, the intended lossless JPEG-LS transfer syntax, unchanged frame/image attributes and decoded pixel values, and preservation of required non-pixel attributes. Kind aliases `dcm`, `dicom`, and `dic` SHALL use the same verifier. Failed or unavailable verification SHALL prevent publication and preserve source bytes.

#### Scenario: Valid lossless candidate

- **WHEN** an unsigned candidate parses and decoded pixels/required attributes match the source
- **THEN** it SHALL be eligible for the normal size and savings acceptance rules

#### Scenario: Magic-only or changed pixels

- **WHEN** an output has DICM magic but invalid structure, changed pixels, or changed required attributes
- **THEN** it SHALL be rejected without replacing the source

#### Scenario: Verifier unavailable

- **WHEN** the available backend cannot establish the required candidate guarantees
- **THEN** the system SHALL report unavailable verification rather than publish by magic alone
