## ADDED Requirements

### Requirement: Virtual Nested Asset Containers
The system SHALL extract nested assets from host files that are not ZIP/7z/tar archives (audio tags, XML data URIs, PDF streams) into a temporary directory using the asset’s real extension, dispatch existing packers on those files, and reinsert any strictly smaller valid output into a rebuilt host file. If no nested asset shrinks, or the extra/library required to extract is missing, the host file SHALL be left unchanged (codec-only packers may still run). Temp directories SHALL be removed after success or failure.

#### Scenario: Nested image is packed with existing JPEG packer
- **WHEN** a container yields `cover.jpg` and jpegoptim/jpegtran is available
- **THEN** the file is dispatched through the existing JPEG packer
- **AND** a smaller JPEG is reinserted into the host

#### Scenario: Nothing smaller
- **WHEN** every extracted asset is unchanged or larger
- **THEN** the host file is not replaced by the container rebuild

#### Scenario: Missing extra
- **WHEN** the Python extra required to parse the host is not installed
- **THEN** extraction is skipped
- **AND** the host file is unchanged by this step

### Requirement: Audio Cover Art Extraction
The system SHALL, when `mutagen` is importable (`filerepack[media]`), extract attached pictures from MP3, FLAC, Ogg, M4A/MP4, and APE, optimize them with image packers, and write the pictures back into the same tag slot. Other audio metadata frames SHALL be preserved. `--no-images` SHALL skip cover-art extraction. Codec packers (mp3packer, flac, alac, mac) SHALL still run according to existing rules. A single commit SHALL replace the original file.

#### Scenario: MP3 cover shrinks
- **WHEN** `pack_mp3` is given an MP3 with an APIC JPEG and mutagen plus a JPEG tool are available
- **THEN** the cover is optimized
- **AND** the rebuilt MP3 still contains the other ID3 frames
- **AND** a smaller file is committed

#### Scenario: mutagen missing
- **WHEN** mutagen cannot be imported
- **THEN** cover extraction is skipped
- **AND** mp3packer/flac/alac still run if their tools exist

#### Scenario: --no-images skips covers
- **WHEN** `pack_images` is false
- **THEN** cover pictures are not extracted or rewritten

### Requirement: XML Data URI Extraction
The system SHALL extract `data:` URI images from XML/SVG into temporary files, pack them, and write compact data URIs back. Invalid or non-image data URIs SHALL be left as-is.

#### Scenario: SVG with embedded PNG
- **WHEN** an SVG contains a `data:image/png;base64,...` image and a PNG packer is available
- **THEN** the decoded PNG is packed
- **AND** the SVG is rewritten with a smaller data URI when the PNG shrank

#### Scenario: Unknown data URI
- **WHEN** a data URI is not a supported image type
- **THEN** it is not modified

### Requirement: Lossless PDF Stream Walking
When pikepdf is importable (`filerepack[pdf]`) and the PDF path is lossless (no `--lossy`, `--pdf-profile`, or `--jpeg-quality`), the system SHALL extract image streams (JPEG DCT, JPEG 2000, and Flate-decoded PNG-like images), pack them with existing image packers, replace the streams, then run the existing qpdf linearize/compress step. Encrypted or digitally signed PDFs SHALL be skipped for stream replacement. The Ghostscript lossy path SHALL remain unchanged. Missing pikepdf SHALL leave lossless PDF as qpdf-only.

#### Scenario: Lossless PDF with embedded JPEG
- **WHEN** pikepdf and jpegoptim are available and `pack_pdf` runs without lossy flags
- **THEN** embedded DCT streams are packed
- **AND** qpdf is still applied to the rebuilt file
- **AND** a smaller valid PDF is committed when commit rules pass

#### Scenario: Lossy flags skip stream walking
- **WHEN** `--lossy`, `--pdf-profile`, or `--jpeg-quality` selects Ghostscript
- **THEN** pikepdf stream walking is not used

#### Scenario: Signed or encrypted PDF
- **WHEN** the PDF is encrypted or has a signature dictionary
- **THEN** stream replacement is skipped
- **AND** lossless qpdf may still run

#### Scenario: pikepdf missing
- **WHEN** pikepdf cannot be imported
- **THEN** lossless `pack_pdf` uses qpdf only as today
