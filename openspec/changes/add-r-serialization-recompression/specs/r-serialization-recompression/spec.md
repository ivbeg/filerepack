## ADDED Requirements

### Requirement: Content identified R serialization profiles
The system SHALL identify the compression envelope, RDS or workspace kind, and
serialization version from content before dispatch. It SHALL validate complete
supported XDR v2/v3 framing without instantiating objects and SHALL skip unknown
serialization records or unsupported representations with an explicit reason.

#### Scenario: Extension does not identify an R stream
- **WHEN** a `.rds` file contains a different format or an invalid supported stream
- **THEN** the system SHALL reject the R candidate and leave the source unchanged

#### Scenario: Workspace and object streams remain distinct
- **WHEN** a valid compressed RDX3 workspace is named `.rda`
- **THEN** the system SHALL retain workspace kind and its header rather than resave it as RDS

### Requirement: Exact serialization preservation
The system SHALL change only the supported compression envelope and SHALL compare
the complete decoded source and candidate byte streams before acceptance. Packing
and verification SHALL NOT deserialize user objects or execute package hooks.

#### Scenario: Reference and float representations survive
- **WHEN** a supported stream contains shared references, attributes and distinct NaN payloads
- **THEN** every decoded serialization byte SHALL match in the accepted candidate

#### Scenario: Decoded comparison fails
- **WHEN** a candidate decodes to a different byte or length
- **THEN** the candidate SHALL be discarded without replacing any existing file

### Requirement: Explicit wrapper compatibility policy
The default `r_compression=preserve` SHALL retain the source compression codec.
Only an explicit gzip, bzip2, or XZ selection SHALL permit a wrapper change, and
the result SHALL report the codec and documented reader requirements. Serialization
version and embedded reader-version fields SHALL remain unchanged. Meaningful
envelope metadata SHALL be retained or the operation SHALL skip.

#### Scenario: Default gzip source stays gzip
- **WHEN** a gzip-wrapped RDS is repacked with default options
- **THEN** an accepted candidate SHALL remain gzip-wrapped and retain understood header metadata

#### Scenario: Explicit XZ cannot erase a gzip comment
- **WHEN** XZ is selected for an input with meaningful gzip metadata that has no supported mapping
- **THEN** the system SHALL report that metadata cannot be preserved and retain the source

### Requirement: Complete bounded envelope verification
The system SHALL verify envelope integrity, EOF and supported framing under shared
decoded-byte, memory, scratch-space and time budgets. An exceeded budget, invalid
checksum, unsupported extra envelope or trailing data SHALL prevent publication.

#### Scenario: A small file expands beyond the operation limit
- **WHEN** source or candidate decompression exceeds the configured decoded-byte budget
- **THEN** the operation SHALL stop, clean staging and report a resource-limited outcome

### Requirement: Verified size based publication
The system SHALL publish only fully verified candidates accepted by the shared
size/minimum-savings policy through the file transaction contract. Dry-run SHALL
not write candidates. Failed, cancelled or non-beneficial operations SHALL preserve
the source and any prior destination.

#### Scenario: A verified candidate is larger
- **WHEN** no verified candidate meets default size acceptance
- **THEN** the system SHALL return unchanged and SHALL not claim positive savings

### Requirement: Native reader and corpus release evidence
An R profile SHALL be advertised as supported only after trusted native R reader
tests, complete framing tests and smaller real-file examples establish its declared
compatibility. Evidence SHALL record provenance, R/encoder versions, all attempted
files including skips, input/output bytes and resource limits.

#### Scenario: Only the pilot byte comparison exists
- **WHEN** native R compatibility evidence has not been obtained for a profile
- **THEN** the profile SHALL remain experimental and SHALL not be advertised as a verified writer
