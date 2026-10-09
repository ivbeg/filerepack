## ADDED Requirements

### Requirement: Explicit complete local Zarr v2 roots
The system SHALL accept Zarr through an explicit whole-store entry point for a
complete offline filesystem root or stable snapshot. It SHALL identify v2 from
metadata content rather than a suffix and SHALL reject unsupported v3, remote,
object-dtype, filtered or unknown-codec stores under the initial profile.

#### Scenario: A directory suffix hides a different format
- **WHEN** a directory named `.zarr` has no valid supported array/group metadata
- **THEN** the store writer SHALL not process it as Zarr

#### Scenario: A partial survey listing is supplied
- **WHEN** only a partial API listing is available without a complete local store
- **THEN** it SHALL not be treated as complete-store compression evidence

### Requirement: Safe codec compatibility policy
The system SHALL use only allowlisted tested codecs without dynamic class loading.
Default rewriting SHALL retain the source codec family/algorithm and SHALL retain
uncompressed arrays. Algorithm upgrades SHALL require explicit compatible-upgrade
selection and declared target-reader compatibility. Filters SHALL remain unchanged.

#### Scenario: Metadata names an arbitrary codec class
- **WHEN** an array compressor is outside the installed tested allowlist
- **THEN** the system SHALL skip the store without importing or executing that class

### Requirement: Exact chunk and array semantics
The system SHALL preserve every stored chunk's complete decoded bytes, dtype,
byte order, shape, chunk geometry, order, missing-chunk set and fill semantics.
Attributes and auxiliary payloads SHALL remain byte-identical. Rechunking and
logical-value reconstruction SHALL NOT occur during ordinary store repack.

#### Scenario: Edge chunk padding differs despite equal visible values
- **WHEN** a candidate changes bytes outside an edge chunk's visible array extent
- **THEN** exact decoded-chunk validation SHALL reject the candidate

#### Scenario: An implicit fill chunk is absent
- **WHEN** a source chunk is intentionally missing
- **THEN** it SHALL remain missing in the accepted store

### Requirement: One consistent compressor per array
The system SHALL generate and verify all stored chunks of a rewritten array under
one compressor declaration or retain that entire array. It SHALL NOT select
incompatible per-chunk encodings based on individual size. Total array and store
acceptance SHALL include metadata and copied unchanged content.

#### Scenario: Only some chunks benefit from a codec change
- **WHEN** the new compressor makes several chunks larger but reduces others
- **THEN** selection SHALL use the complete consistent array candidate and its total bytes

### Requirement: Consistent consolidated metadata
The system SHALL preserve consolidation presence and all non-compressor metadata
fields, validate source cache consistency, and update matching `.zarray` and
existing `.zmetadata` compressor declarations together. Ordinary and consolidated
reads SHALL agree after rewrite.

#### Scenario: Consolidated metadata describes an obsolete compressor
- **WHEN** source `.zmetadata` conflicts with an array's `.zarray`
- **THEN** the system SHALL reject the store candidate rather than guess the intended encoding

### Requirement: Verified store acceptance and reporting
The system SHALL perform complete bounded store validation before total-size
acceptance and directory publication. Reports SHALL include logical source/output
bytes, array/chunk counts, codec decisions and verification coverage. Skips, limits
and unchanged stores SHALL not be represented as measured positive savings.

#### Scenario: One chunk fails after other arrays were rewritten
- **WHEN** any required chunk or metadata check fails
- **THEN** the whole staging store SHALL be rejected without publishing a partial result

### Requirement: Complete store release evidence
Each advertised Zarr profile SHALL have complete real-store gain measurements,
exact chunk comparison fixtures and ordinary/consolidated reader compatibility
checks. Partial-tree metadata, isolated compressed chunks or extension frequency
SHALL NOT establish a supported whole-store writer.

#### Scenario: Only the surveyed metadata has been checked
- **WHEN** no complete store has passed recompression and native read-back
- **THEN** the profile SHALL remain experimental
