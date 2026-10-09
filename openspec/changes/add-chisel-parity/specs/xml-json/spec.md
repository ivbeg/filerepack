## MODIFIED Requirements

### Requirement: SVG Packer Fallback
The system SHALL keep `svgo` or `scour` as the preferred SVG packer. When both are missing, SVG SHALL be processed by `pack_xml` (minify + data-URI extraction). When svgo/scour runs, data-URI extraction MAY still run on the result.

#### Scenario: svgo present
- **WHEN** `svgo` is on PATH
- **THEN** `pack_svg` uses svgo as today

#### Scenario: no SVG CLI tools
- **WHEN** svgo and scour are missing
- **THEN** SVG is minified via `pack_xml` if it is well-formed
