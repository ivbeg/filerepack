## MODIFIED Requirements

### Requirement: Audited Word table-style and display-property coverage
The system SHALL admit audited offset-free Word formatting operands and
conditional table-style operands only with complete framing and permitted nested
property validation. Conditional operands SHALL occur only in table styles,
contain a qualified condition and contain no picture/OLE identity, Data offset,
unknown operand or further conditional operand. Exceptional tab-stop lengths
SHALL be computed from bounded array counts. Word-specific scalar protection and
shape flags and the shape-owned scalar tertiary dhgt property SHALL be preserved
exactly. Only empty complex fillBlip/lineFillBlip defaults SHALL be admitted by
this additional property profile. Other hosts SHALL retain their existing
qualification scope. Publication SHALL require independent whole-document
preservation and physical savings against strict compaction; unreferenced
pictures, history, formatting and unrelated streams SHALL remain byte-identical.

#### Scenario: Formatted inline Word pictures are recompressible
- **WHEN** a DOC contains qualified pictures with the admitted formatting and drawing properties
- **THEN** lossless image recompression SHALL be eligible through ole_recompress
- **AND** every unrelated stream, formatting byte and reference identity SHALL be preserved.

#### Scenario: Conditional formatting hides a reference or has invalid framing
- **WHEN** a conditional operand contains a forbidden nested property, invalid condition, unqualified owner or truncated operand
- **THEN** content recompression SHALL be rejected before publication
- **AND** independently verified strict compaction SHALL remain available.

#### Scenario: Newly admitted immutable bytes change
- **WHEN** a candidate changes a conditional style, scalar drawing property or unreferenced picture
- **THEN** independent intended-content verification SHALL reject that candidate.
