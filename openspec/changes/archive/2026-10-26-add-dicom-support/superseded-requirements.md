# Superseded requirement wording

Preserved from the original delta during the 2026-10-07 baseline audit.
The live requirement is owned by the later change listed in the baseline audit.

## dicom

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

## dicom

### Requirement: DICOM Output Verification
`verify_output` SHALL accept kind `dcm` (and treat `dicom` / `dic` as the same check): the file is non-empty and bytes 128–131 equal `DICM`. A failed verification SHALL discard the temp output and leave the original file in place.

#### Scenario: Valid DICOM magic
- **WHEN** `verify_output` is called on a file whose offset 128 is `DICM`
- **THEN** it returns true for kind `dcm`

#### Scenario: Reject non-DICOM output
- **WHEN** the encoder writes a file without `DICM` at offset 128
- **THEN** verification fails
- **AND** the original `.dcm` is not replaced
