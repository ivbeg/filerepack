## ADDED Requirements

### Requirement: Lossless PDF Uses qpdf
The system SHALL recompress PDF files with qpdf (`--linearize --object-streams=generate --compress-streams=y`) when no lossy PDF option is set. Ghostscript SHALL NOT run on that default path.

#### Scenario: Default PDF pack
- **WHEN** `pack_pdf` is called without `lossy`, `pdf_profile`, or `jpeg_quality`
- **THEN** the qpdf command is used
- **AND** Ghostscript is not invoked

### Requirement: Lossy PDF Uses Ghostscript Profiles
The system SHALL use Ghostscript `pdfwrite` when `lossy` is true, `pdf_profile` is set, or `jpeg_quality` is set. The Distiller preset SHALL be `-dPDFSETTINGS=/<profile>`. An unset profile SHALL default to `ebook`. Allowed profiles are `screen`, `ebook`, `printer`, `prepress`, and `default`. `--pdf-profile` and `--jpeg-quality` SHALL imply this Ghostscript path even when `--lossy` is absent. If Ghostscript is missing, the packer SHALL fall back to qpdf.

#### Scenario: --lossy defaults to ebook
- **WHEN** `pack_pdf` is called with `lossy=True` and no `pdf_profile`
- **THEN** Ghostscript is invoked with `-dPDFSETTINGS=/ebook`

#### Scenario: Explicit print-quality profile
- **WHEN** `pdf_profile` is `prepress`
- **THEN** Ghostscript is invoked with `-dPDFSETTINGS=/prepress`

#### Scenario: Profile implies lossy
- **WHEN** `filerepack repack file.pdf --pdf-profile screen` is run
- **THEN** Ghostscript is used even without `--lossy`

#### Scenario: Ghostscript missing
- **WHEN** lossy PDF is requested and `gs` is not available but `qpdf` is
- **THEN** the packer falls back to qpdf

#### Scenario: Unknown profile
- **WHEN** `--pdf-profile` is not one of the allowed names
- **THEN** the CLI exits with code 1 before packing
- **AND** `pack_pdf` with an unknown `pdf_profile` returns `None` without running a tool

### Requirement: JPEG Quality Applies to PDF Images
When `jpeg_quality` is set, the Ghostscript command SHALL disable auto image filters, force `/DCTEncode` for color and gray images, and set Distiller `QFactor` from that quality (100 maps to 0.15, 1 maps to 2.4). The selected `--pdf-profile` (or `ebook`) SHALL still control downsample DPI.

#### Scenario: jpeg-quality sets QFactor
- **WHEN** `pack_pdf` is called with `jpeg_quality=75`
- **THEN** the Ghostscript command includes `setdistillerparams` and a QFactor derived from 75
- **AND** `-dColorImageFilter=/DCTEncode` is present

#### Scenario: jpeg-quality implies Ghostscript
- **WHEN** `pack_pdf` is called with `jpeg_quality=85` and `lossy=False`
- **THEN** Ghostscript is invoked with `-dPDFSETTINGS=/ebook`

### Requirement: Illustrator PDF Wrappers Follow PDF Options
PDF-wrapped `.ai` files SHALL receive the same `lossy`, `pdf_profile`, and `jpeg_quality` arguments as `pack_pdf`.

#### Scenario: Dispatch forwards PDF options
- **WHEN** `_dispatch_packer` runs for extension `ai` or `pdf` with `pdf_profile` and `jpeg_quality` in options
- **THEN** those values are passed into the packer function
