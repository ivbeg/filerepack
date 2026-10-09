## ADDED Requirements

### Requirement: MAT dialect specific dispatch
The system SHALL identify MAT storage dialect from content and SHALL use separate
Level-5 and v7.3 profiles. It SHALL NOT route every `.mat` file to HDF5. Unsupported
dialects and files without a verified compatible rewrite SHALL remain unchanged.

#### Scenario: Classic MAT is named like an HDF5 input
- **WHEN** a `.mat` file has a valid Level-5 header
- **THEN** the system SHALL use Level-5 traversal and SHALL not invoke the HDF5 writer

#### Scenario: No existing compression is available
- **WHEN** a v4 or supported Level-5 input has no rewritable compressed element
- **THEN** the system SHALL report no compatible recompression and retain the file

### Requirement: Existing compressed element preservation
The Level-5 writer SHALL preserve the header and unaffected element bytes, and
SHALL recompress only existing supported `miCOMPRESSED` elements. The ordered
decoded element streams SHALL be byte-identical, preserving matrix storage types,
dimensions, flags, names, sparse structure and object content without reconstruction.

#### Scenario: Sparse complex matrices are recompressed
- **WHEN** supported compressed elements contain sparse indexes and complex payloads
- **THEN** all decoded element bytes and the variable order SHALL remain identical

### Requirement: Complete MAT framing validation
The system SHALL validate tag sizes, endianness, small-data tags, compression
integrity, padding and complete file consumption under operation budgets. It SHALL
skip unsupported subsystem offsets or object structures rather than guess offsets.

#### Scenario: A header probe succeeds but an element is truncated
- **WHEN** a valid MAT header is followed by an incomplete compressed element
- **THEN** no rewritten file SHALL be published

#### Scenario: A subsystem offset cannot be safely retained
- **WHEN** the source has a nonzero subsystem offset outside the supported profile
- **THEN** the system SHALL report the unsupported structure and leave it unchanged

### Requirement: MATLAB v7.3 graph and user block preservation
The v7.3 writer SHALL be enabled only with HDF5 graph/data validation and native
MATLAB compatibility evidence. It SHALL preserve the MATLAB user block, attributes,
object and region reference targets, alias relationships, array representations and
source reader requirements while changing only verified lossless storage properties.

#### Scenario: Cell arrays use shared referenced objects
- **WHEN** a supported v7.3 input has multiple references to the same object
- **THEN** candidate references SHALL resolve to the same corresponding object and retain MATLAB metadata

#### Scenario: Only a generic HDF5 validator is available
- **WHEN** MATLAB-specific preservation cannot be established
- **THEN** the v7.3 profile SHALL skip without advertising a verified MAT result

### Requirement: Verified MAT acceptance and publication
The system SHALL verify candidates before applying shared size/minimum-savings and
file-publication rules. Errors, resource limits, cancellation or no-benefit results
SHALL preserve the source and any prior destination. Dry-run SHALL not rewrite MAT data.

#### Scenario: Higher zlib effort does not reduce the file
- **WHEN** no verified candidate satisfies default size acceptance
- **THEN** the system SHALL return unchanged without claiming savings

### Requirement: Independent per dialect release evidence
Each MAT writer profile SHALL have trusted native MATLAB read-back evidence and
smaller real-file examples, with provenance, backend/reader versions, all attempted
files, decoded-preservation results and resource cost. Evidence for one dialect
SHALL NOT establish support for another.

#### Scenario: Level-5 experiments pass but v7.3 was not checked
- **WHEN** only the Level-5 profile has completed its compatibility and benefit gates
- **THEN** only that profile SHALL be advertised as a supported MAT writer
