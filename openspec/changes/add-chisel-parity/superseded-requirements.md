# Superseded requirement wording

Preserved from the original delta during the 2026-10-07 baseline audit.
The live requirement is owned by the later change listed in the baseline audit.

## encoder-quality

### Requirement: Keep Metadata Flag
The system SHALL add `RepackOptions.keep_meta` (default false) and CLI `--keep-meta`. When false, lossless JPEG/PNG stripping stays as today (`jpegoptim --strip-all`, oxipng `--strip safe`). When true, JPEG SHALL use jpegtran `-copy all` and jpegoptim without `--strip-all`, and PNG SHALL not pass oxipng `--strip`. Default CLI behavior without the flag SHALL not change.

#### Scenario: default still strips JPEG
- **WHEN** `pack_jpg` runs lossless without `keep_meta`
- **THEN** jpegoptim is invoked with `--strip-all` (when jpegoptim runs)

#### Scenario: --keep-meta
- **WHEN** the user passes `--keep-meta`
- **THEN** JPEG strip-all is not used
- **AND** jpegtran is invoked with `-copy all` when jpegtran runs
- **AND** oxipng is invoked without `--strip`

#### Scenario: library option
- **WHEN** `RepackOptions(keep_meta=True)` is passed to `FileRepacker.repack`
- **THEN** the JPEG/PNG packers receive `keep_meta=True`

## nested-assets

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

## xml-json

### Requirement: JSON Identification and Minification
The system SHALL treat filenames ending in `.json` (case-insensitive) as standalone files. `pack_json` SHALL parse the file as UTF-8 JSON and rewrite it compactly (`separators=(',', ':')`, `ensure_ascii=False`). Invalid JSON SHALL be skipped. Nested `.json` members inside ZIP-based archives SHALL be minified during the existing deep walk when document packing is enabled.

#### Scenario: Pretty-printed JSON shrinks
- **WHEN** `pack_json` is given valid pretty-printed JSON
- **THEN** it writes compact JSON with the same value
- **AND** a smaller file is committed when commit rules pass

#### Scenario: Invalid JSON
- **WHEN** the file is not valid JSON
- **THEN** `pack_json` returns `None`
- **AND** the original file is unchanged

#### Scenario: JSON inside OOXML
- **WHEN** a `.docx` contains a `.json` part and deep walking is on
- **THEN** that part is dispatched to `pack_json`

## xml-json

### Requirement: XML Identification and Minification
The system SHALL treat `.xml`, `.xhtml`, `.kml`, `.gpx`, `.dae`, `.rss`, `.atom`, `.xmp`, `.xsl`, `.xslt`, and `.fb2` as standalone XML files. `pack_xml` SHALL serialize without indentation and SHALL NOT change element text-node character data. Elements with `xml:space="preserve"` SHALL keep surrounding whitespace. Unparseable XML SHALL be skipped. Nested XML inside ZIP/OOXML/ODF/EPUB SHALL be minified during the existing deep walk.

#### Scenario: Pretty-printed XML shrinks
- **WHEN** `pack_xml` is given well-formed pretty-printed XML without `xml:space="preserve"`
- **THEN** ignorable whitespace between elements is removed
- **AND** text-node content is identical

#### Scenario: Preserve xml:space
- **WHEN** an element has `xml:space="preserve"`
- **THEN** that element’s whitespace is not stripped

#### Scenario: OOXML document text survives
- **WHEN** a `.docx` is deep-walked and `word/document.xml` is minified
- **THEN** every `w:t` text node’s character data is unchanged

#### Scenario: Unparseable XML
- **WHEN** the file is not well-formed XML
- **THEN** `pack_xml` returns `None`
- **AND** the original is unchanged
