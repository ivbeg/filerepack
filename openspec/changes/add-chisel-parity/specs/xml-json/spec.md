## ADDED Requirements

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

### Requirement: SVG Packer Fallback
The system SHALL keep `svgo` or `scour` as the preferred SVG packer. When both are missing, SVG SHALL be processed by `pack_xml` (minify + data-URI extraction). When svgo/scour runs, data-URI extraction MAY still run on the result.

#### Scenario: svgo present
- **WHEN** `svgo` is on PATH
- **THEN** `pack_svg` uses svgo as today

#### Scenario: no SVG CLI tools
- **WHEN** svgo and scour are missing
- **THEN** SVG is minified via `pack_xml` if it is well-formed
