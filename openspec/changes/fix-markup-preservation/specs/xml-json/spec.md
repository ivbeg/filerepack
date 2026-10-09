## MODIFIED Requirements

### Requirement: JSON Identification and Minification

The system SHALL identify case-insensitive `.json` files and minify valid supported JSON by removing only insignificant whitespace outside tokens. It SHALL preserve string contents, numeric lexemes, object-member order, and duplicate members without parse-and-reserialize rounding or collapse. Valid scalar roots SHALL be supported. Invalid input, non-standard non-finite literals, and unsupported encodings SHALL be left unchanged. Nested JSON SHALL obey the same contract during document-enabled deep walking.

#### Scenario: High precision and duplicate keys

- **WHEN** JSON contains `1.234567890123456789` and repeated object keys
- **THEN** the candidate SHALL retain the exact number token and every object member in order

#### Scenario: Scalar root

- **WHEN** a supported JSON file contains a valid scalar root surrounded by whitespace
- **THEN** the scalar token SHALL be preserved and only insignificant whitespace SHALL be removed

#### Scenario: Invalid or non-standard input

- **WHEN** JSON is malformed or contains a non-standard non-finite literal
- **THEN** the source SHALL remain unchanged and validation SHALL report the reason

#### Scenario: JSON inside OOXML

- **WHEN** OOXML contains JSON and document-enabled deep walking is active
- **THEN** the part SHALL satisfy the same lexical preservation contract

### Requirement: XML Identification and Minification

The system SHALL identify `.xml`, `.xhtml`, `.kml`, `.gpx`, `.dae`, `.rss`, `.atom`, `.xmp`, `.xsl`, `.xslt`, and `.fb2` as XML inputs. Minification SHALL preserve element text and tail character data, inherited `xml:space`, CDATA, entities, namespaces, comments, processing instructions, and declaration/encoding consistency. Whitespace SHALL be removed only where its insignificance is established for the supported context; unknown contexts SHALL remain preserved. Unparseable or unsupported input SHALL be left unchanged. Nested XML in ZIP/OOXML/ODF/EPUB SHALL satisfy the same contract.

#### Scenario: Inherited preservation

- **WHEN** an ancestor declares `xml:space="preserve"` around child elements
- **THEN** text and tail whitespace in the subtree SHALL remain unchanged

#### Scenario: CDATA and mixed content

- **WHEN** a file contains CDATA `hello>\n<world` or mixed text and child elements
- **THEN** text content and protected lexical regions SHALL remain unchanged

#### Scenario: Known insignificant indentation

- **WHEN** a supported vocabulary establishes element-only indentation as insignificant
- **THEN** only that established indentation SHALL be removed

#### Scenario: OOXML text and invalid input

- **WHEN** OOXML text is optimized or XML fails parsing/encoding validation
- **THEN** accepted parts SHALL preserve all text-node content and invalid parts SHALL remain unchanged
