## MODIFIED Requirements

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
