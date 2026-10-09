## ADDED Requirements

### Requirement: System file feasibility and content profiles
The system SHALL classify complete SPSS system-file kind, compression mode and
supported integer/float representations from content. Each writer profile SHALL
require real-file gain and trusted native-reader evidence before registration.
Unsupported representations or ambiguous records SHALL produce a reasoned skip.

#### Scenario: A SAV suffix contains a portable POR file
- **WHEN** content is not a supported system-file profile
- **THEN** the SAV writer SHALL not reinterpret or convert it

### Requirement: Byte identical system file dictionary
The system SHALL retain all supported dictionary records and non-derived header
fields byte-for-byte. It SHALL NOT recreate labels, encodings, missing definitions,
formats, weights or extension records through a dataframe round trip. Unknown
records whose bounds/reference semantics cannot be retained SHALL cause a skip.

#### Scenario: Value labels and multiple response definitions are present
- **WHEN** supported case data is recompressed
- **THEN** all associated dictionary bytes SHALL remain identical

### Requirement: Exact decoded case elements
The system SHALL preserve complete decoded case elements, their types/order and
padding, including exact supported numeric float representations and long-string
segments. Bytecode abbreviations SHALL be used only when they reconstruct identical
case bytes; numeric/string normalization SHALL NOT be permitted.

#### Scenario: Negative zero cannot be represented by a short numeric code
- **WHEN** a numeric literal contains negative-zero bits
- **THEN** the encoder SHALL retain an exact representation rather than normalize it to positive zero

### Requirement: Same kind system file compression
Ordinary repack SHALL preserve `$FL2` or `$FL3` source kind. A proven `$FL2` profile
can change raw data to compatible bytecode while retaining dictionary and header
semantics. Existing `$FL3` recompression SHALL retain the complete inflated bytecode
stream and rebuild only required compression framing. SAV-to-ZSAV conversion SHALL
NOT occur implicitly or through a general effort/growth/lossy option.

#### Scenario: ZSAV would be smaller than a source SAV
- **WHEN** the source has `$FL2` kind
- **THEN** ordinary repack SHALL not emit `$FL3` regardless of that potential saving

### Requirement: Complete bounded system file validation
The system SHALL validate complete dictionary/case framing, counts, bytecode
termination and applicable zlib block indexes, offsets, lengths, integrity and EOF
under shared budgets. It SHALL compare source/candidate dictionary and decoded data
before size acceptance and file publication.

#### Scenario: One ZSAV trailer offset points outside the file
- **WHEN** container traversal discovers the invalid block index
- **THEN** the candidate SHALL fail validation even if the first cases can be read

### Requirement: Safe system file outcomes
Missing verification, unsupported data, limits, cancellation, corruption or a
non-beneficial candidate SHALL preserve source and prior destination. Dry-run SHALL
not encode cases. Reports SHALL distinguish source identification, measured benefit
and actual native-reader coverage.

#### Scenario: SAV tests pass but real ZSAV evidence is absent
- **WHEN** only the SAV profile has completed its release gates
- **THEN** ZSAV SHALL remain experimental and SHALL not inherit the SAV support claim
