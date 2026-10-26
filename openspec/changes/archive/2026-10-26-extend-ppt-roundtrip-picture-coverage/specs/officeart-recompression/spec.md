## MODIFIED Requirements

### Requirement: Audited additional PPT round-trip Pictures forms
The system SHALL extend Pictures-only qualification to independently audited
RoundTripContentMasterId12Atom slide records, additional content-layout package
instances, drawing-group color-MRU records, multi-property OfficeArtTertiaryFOPT
tables and the observed shape-owned PPT9 extension forms. It SHALL additionally
resolve audited composite masters/slides to one live original master, require
unique non-overlapping layout instances and match each slide's legacy master.
Shape-owned PPT9 text runs SHALL be bounded and fully framed; only the observed
zero or null-picture-bullet/numbering PF9 forms and zero CF9/SI masks SHALL be
admitted. Non-null bullet-picture targets SHALL remain outside this profile.
It SHALL validate their
standard versions, instances, lengths, owners and relevant reference semantics
before selecting image payloads. It SHALL retain every byte of these records and
tags, complete property-table reference accounting, existing notes/host validation,
PNG sample/metadata preservation, unselected-image preservation and resource bounds.
Only the existing exact FBSE size/delay fields and selected Pictures encodings MAY
change. Unknown or malformed forms SHALL remain outside this extended profile.

#### Scenario: Audited round-trip presentation contains compressible Pictures
- **WHEN** a single-edit PPT contains only qualified round-trip forms and its complete host and Pictures references pass validation
- **THEN** existing bounded PNG encoders SHALL be eligible under the ole_recompress option
- **AND** every round-trip record, package, tag and logical identifier SHALL remain byte-identical
- **AND** acceptance SHALL require independent whole-host preservation and physical size improvement over verified compaction.

#### Scenario: Added extension form has invalid structure or references
- **WHEN** a proposed form has an unqualified header, owner, tag name, property bound or relevant reference
- **THEN** Pictures recompression SHALL be rejected before publication
- **AND** any compaction fallback SHALL retain its separate strict preservation contract.

#### Scenario: Candidate changes an admitted immutable extension byte
- **WHEN** a candidate changes an admitted round-trip record, complex property package or programmable tag outside the existing FBSE write mask
- **THEN** independent preservation verification SHALL reject the candidate.

#### Scenario: Composite layout and null-bullet text runs are qualified
- **WHEN** composite master/slide identities resolve consistently and every PPT9 text run has an audited mask and null picture-bullet reference
- **THEN** the existing Pictures operation SHALL be eligible under the same exact immutable-byte contract
- **AND** missing original masters, conflicting slide references, duplicate layouts and unqualified text properties SHALL be rejected.
