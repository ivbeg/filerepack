## MODIFIED Requirements

### Requirement: Opt-in qualified HWP stream selection
The system SHALL use ole_recompress for separately qualified HWP 5 content
profiles only. It SHALL resolve DocInfo, BodyText sections and eligible BinData
through validated header/document metadata and retain every original compression
declaration. Uncompressed, protected/distribution/script-bearing or otherwise
unqualified content profiles SHALL NOT be rewritten by this capability.

#### Scenario: Compressed HWP with multiple sections
- **WHEN** an enabled HWP profile and ole_recompress resolve multiple already-compressed document sections
- **THEN** only the exact qualified stream set is considered for recompression.

#### Scenario: Uncompressed HWP input
- **WHEN** the document's compression mode is disabled
- **THEN** this capability leaves its stream representations and header flag unchanged.

### Requirement: Exact HWP raw-DEFLATE content preservation
For each selected stream, the system SHALL qualify its raw-DEFLATE framing,
enforce complete termination and bounds, and preserve every decoded record/binary
byte. It SHALL NOT reserialize records, convert images, add an RFC1950 wrapper or
accept unexplained trailing/concatenated data.

#### Scenario: Stronger encoding of identical section bytes
- **WHEN** a smaller raw-DEFLATE representation decodes to the exact original bytes
- **THEN** it can enter independent host/CFB verification with unchanged section IDs and compression flags.

#### Scenario: Candidate changes one record byte or uses a zlib wrapper
- **WHEN** an encoder changes decoded content or framing outside the qualified raw representation
- **THEN** verification rejects the candidate before publication.

### Requirement: Qualified BinData compression identity
The system SHALL recompress BinData only after resolving its object ID, stream
identity, link/embedding kind and effective per-object/header compression policy.
Every decoded binary byte and its describing metadata SHALL remain identical.
Unresolved or unsupported binary objects SHALL remain encoded byte-identically.

#### Scenario: Binary data overrides the document compression default
- **WHEN** a qualified object's own metadata declares a supported compression policy
- **THEN** the exact effective policy is honored without changing metadata or guessing from the stream suffix.

#### Scenario: Linked or ambiguously mapped binary object
- **WHEN** BinData identity or compression state cannot be completely resolved
- **THEN** the stream is retained unchanged and a specific skip reason is reported.

### Requirement: Independent HWP intended-change manifest
The system SHALL independently compare selected decoded streams, unchanged
encoded streams, FileHeader/document metadata, section/BinData identity and full
CFB logical metadata. Only declared encoded-stream replacements SHALL be allowed.
Strict OLE stream equality SHALL remain unchanged.

#### Scenario: A valid section is removed or a flag changes
- **WHEN** a smaller candidate decodes remaining streams correctly but loses a section or changes header metadata
- **THEN** independent verification rejects it.

#### Scenario: Native writer rewrites an unrelated preview
- **WHEN** preview/script/property bytes change outside the selected stream set
- **THEN** the candidate is rejected regardless of rendered equality.

### Requirement: Shared bounded HWP execution and physical selection
The system SHALL share root limits across selected streams, repeated decoding,
verification and native processes, retain original/strict compaction alternatives
and apply existing transaction/physical-savings policies. It SHALL report encoder
availability, selected/recompressed counts, stream/file savings and qualification
limits for real fixtures separately from synthetic controls.

#### Scenario: Many sections exceed the aggregate decoded limit
- **WHEN** cumulative selected-stream work exhausts the root budget
- **THEN** publication stops, owned work is cleaned and the source remains unchanged.

#### Scenario: Compression gains fit existing sectors
- **WHEN** recompressed streams do not produce a smaller verified file
- **THEN** the strict baseline is retained and no extra physical saving is claimed.
