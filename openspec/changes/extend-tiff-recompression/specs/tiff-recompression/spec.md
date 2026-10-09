## ADDED Requirements

### Requirement: Complete TIFF graph and image inventory
The system SHALL inspect and preserve the complete supported IFD/SubIFD graph,
page and pyramid relationships, page order, dimensions and sample representation.
It SHALL detect malformed offsets, cycles and unsupported structures before rewriting.

#### Scenario: A pyramid has reduced-resolution SubIFDs
- **WHEN** a supported source contains a main image and reduced-resolution SubIFDs
- **THEN** every image and its relationship SHALL remain present in the accepted output

### Requirement: Exact native TIFF samples
The system SHALL compare all decoded samples in their native dtype and order,
including depth, signedness, planar configuration, extra channels and float bits.
Rendered RGB equality SHALL NOT substitute for native sample equality.

#### Scenario: A high depth image is normalized by a backend
- **WHEN** a writer reduces a 16-bit or floating image to a visually similar representation
- **THEN** the candidate SHALL fail lossless preservation validation

### Requirement: TIFF semantic metadata retention
The system SHALL preserve supported semantic tags and referenced payloads, including
color profiles, orientation, resolution, descriptions, EXIF/XMP/IPTC and supported
geospatial/application metadata. Metadata stripping SHALL NOT be a preserving
candidate. Unknown non-relocatable private tags SHALL cause a skip.

#### Scenario: Smaller output loses an ICC profile
- **WHEN** candidate pixels match but the source ICC tag or profile payload is absent
- **THEN** the candidate SHALL be discarded

#### Scenario: An unknown tag may reference moved data
- **WHEN** the handler cannot establish that a private offset-bearing tag remains valid
- **THEN** it SHALL retain the input and report unsupported metadata

### Requirement: Enumerated reversible storage changes
The system SHALL change only declared lossless codec/predictor and derived offset,
size and framing properties. Default rewriting SHALL retain byte order, strip/tile
geometry, sample interpretation and classic TIFF/BigTIFF kind. Each enabled codec
and predictor SHALL have exact-sample and reader compatibility evidence.

#### Scenario: A floating predictor is unsupported by the installed backend
- **WHEN** its support has not been established for the source sample type
- **THEN** the system SHALL omit that candidate rather than assume reversibility

### Requirement: Verified geospatial and layout profiles
GeoTIFF and COG support SHALL require retention of geospatial semantics and any
advertised layout properties. A recognized COG input SHALL retain validated COG
layout or SHALL be skipped. Generic TIFF sample equality SHALL NOT establish COG support.

#### Scenario: A writer preserves GeoKeys but breaks COG layout
- **WHEN** the candidate no longer passes the source COG profile's layout checks
- **THEN** the COG candidate SHALL not be published

### Requirement: Bounded TIFF validation and publication
The system SHALL perform complete metadata and sample comparison under shared
budgets before size acceptance and transactional publication. Missing validation,
unsupported compression, corruption, cancellation or non-beneficial candidates
SHALL leave source and prior destination intact. Dry-run SHALL not encode TIFF candidates.

#### Scenario: A malformed IFD chain exhausts the node budget
- **WHEN** TIFF traversal exceeds the configured metadata/graph budget
- **THEN** processing SHALL stop without publishing output

### Requirement: TIFF profile evidence
Each advertised TIFF profile SHALL have real-file gain/cost measurements and
independent reader checks covering its tags, sample types and IFD structures.
Commons file/byte totals SHALL NOT be presented as estimated recompression savings.

#### Scenario: A single-page 8-bit fixture passes
- **WHEN** no multipage or floating-point compatibility evidence exists
- **THEN** that fixture SHALL not establish those additional supported profiles
