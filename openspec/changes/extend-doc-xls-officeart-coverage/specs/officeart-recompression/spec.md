## ADDED Requirements

### Requirement: Populated BIFF8 OfficeArt host qualification
The system SHALL support separately qualified BIFF8 profiles containing cells,
formulas, populated SST/CONTINUE, ExtSST and Index/DBCell row blocks. It SHALL
preserve all non-drawing record bytes except exhaustively classified relocation
fields, including formula tokens/results, numeric encodings and string metadata.
It SHALL reject unqualified reference-bearing record families.

#### Scenario: Workbook contains formulas and shared strings
- **WHEN** an enabled BIFF8 profile contains eligible drawings alongside cells, formulas and populated string/row indexes
- **THEN** OfficeArt recompression is attempted through ole_recompress
- **AND** cell/formula/string bytes and logical values remain identical.

#### Scenario: Unqualified workbook family
- **WHEN** an affected workbook contains an unqualified chart, pivot, control or future record family
- **THEN** content recompression falls back to independently verified strict compaction with a specific reason.

#### Scenario: Scalar tertiary worksheet fill state
- **WHEN** a worksheet contains an OfficeArtTertiaryFOPT record with version 3, exactly one non-complex non-BLIP Fill Style Boolean property 0x01BF and no additional bytes
- **THEN** OfficeArt payload recompression may proceed while the complete worksheet drawing and fill-state bytes remain exact
- **AND** other tertiary properties, versions, counts and flag combinations remain unqualified.

### Requirement: Complete BIFF8 offset relocation
The system SHALL resolve every affected absolute and relative reference by target
identity, including BoundSheet, Index, DBCell and ExtSST fields. It SHALL preserve
SST continuation boundaries and correctly distinguish record offsets from
interior string offsets and relative row-block offsets.

#### Scenario: Drawing shrink moves worksheet and string records
- **WHEN** refragmenting a drawing group moves records addressed by multiple pointer families
- **THEN** every pointer resolves to the same source target after relocation
- **AND** an unchanged numeric value alone is insufficient evidence of correctness.

#### Scenario: Valid offset points to the wrong row block
- **WHEN** a candidate has an in-bounds reference to a different valid record
- **THEN** independent verification rejects the candidate before publication.

#### Scenario: First drawing-group continuation uses MsoDrawingGroup
- **WHEN** the single global drawing group uses a second immediately adjacent MsoDrawingGroup in place of its first Continue and any remaining fragments are Continue records
- **THEN** the fragments are parsed as one complete OfficeArt root and all affected host pointers are relocated by target identity
- **AND** a third or nonadjacent MsoDrawingGroup is rejected.

### Requirement: Expanded Word picture reference qualification
The system SHALL qualify additional Word profiles by resolving piece PRMs,
style/FKP inheritance, shared operand consumers and floating drawing references.
It SHALL distinguish pictures from binary data and OLE identifiers, and preserve
text, formatting, anchors, geometry and all unrelated bytes.
It SHALL reject style definitions containing picture/OLE identity or other
qualified properties forbidden in UpxChpx; picture locations SHALL retain
direct-character or piece-PRM provenance.

#### Scenario: Picture uses inherited character formatting
- **WHEN** a picture with a qualified direct or piece-owned location uses inherited character formatting
- **THEN** every consumer retains its original picture identity and formatting
- **AND** only the proven location/length fields are patched.

#### Scenario: Style claims a forbidden picture identity
- **WHEN** a style definition contains sprmCPicLocation, sprmCFSpec or another qualified property forbidden in UpxChpx
- **THEN** inline picture recompression is rejected with the property code and strict compaction remains available.

#### Scenario: Floating picture in a drawing store
- **WHEN** an enabled Word profile fully resolves a floating picture and its affected FIB/table references
- **THEN** its eligible payload can be recompressed while anchor and display properties remain identical.

### Requirement: Mixed Word Data preservation
The system SHALL rewrite qualified pictures in mixed Data only after resolving
all affected region boundaries and consumers. It SHALL retain opaque regions,
padding and history exactly, admit aliases only with complete consumer mapping,
and reject overlapping or ambiguous interpretations.

#### Scenario: Picture beside binary Data and an embedded object identifier
- **WHEN** an enabled mixed Data profile contains a resizable picture and unrelated binary/OLE content
- **THEN** the unrelated content is byte-identical and its references retain their identities.

#### Scenario: Unresolved shared location
- **WHEN** a moved region has an unresolved consumer or ambiguous overlap
- **THEN** content recompression is skipped with a diagnostic and no unchecked rewrite occurs.

### Requirement: Coverage evidence and compatible fallback
The system SHALL retain the existing opt-in, protection/macro, root-budget,
transaction, effective category selection and strict OLE contracts. Each newly
enabled profile SHALL have real
fixture provenance, independent byte/graph evidence and reported coverage,
physical savings and application/platform qualification limits.

#### Scenario: Newly supported layout provides no physical gain
- **WHEN** additional discovery finds recompressible pictures but sector allocation yields no smaller verified file
- **THEN** the compaction baseline is retained and diagnostics distinguish coverage from physical savings.

#### Scenario: Disabled recompression
- **WHEN** ole_recompress is false for a newly qualified document
- **THEN** only the existing strict container compaction behavior applies.
