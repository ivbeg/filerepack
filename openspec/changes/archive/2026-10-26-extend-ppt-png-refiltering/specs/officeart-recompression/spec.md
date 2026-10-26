## MODIFIED Requirements

### Requirement: Qualified PPT PNG refiltering
The system SHALL independently qualify static, noninterlaced 8-bit PPT PNGs for
refiltering through exact unfiltered sample identity. It SHALL preserve complete
IHDR, sample depth/color mode, palette/index/alpha samples, all non-IDAT chunks and
their order, BLIP/FBSE identities and the complete immutable host graph. Other
PNG layouts SHALL retain the exact-filtered contract. It SHALL run only through
the existing ole_recompress opt-in, with optional qualified oxipng and verified
original/zlib/Zopfli alternatives. A final independent host verifier SHALL
account for every changed payload, length and permitted delay-store field.

#### Scenario: Smaller refiltered image with exact samples
- **WHEN** a qualified PPT PNG changes filters but every unfiltered sample is exact
- **THEN** its IDAT candidate MAY be selected after restoring exact source chunks
- **AND** the native result SHALL pass independent whole-host verification.

#### Scenario: Encoder changes depth, metadata or an invisible color sample
- **WHEN** a trial changes IHDR, a palette entry, alpha or any unfiltered sample
- **THEN** that trial SHALL be rejected
- **AND** source non-IDAT chunks SHALL never be replaced by encoder metadata.

#### Scenario: Qualified optional encoder is unavailable
- **WHEN** the qualified oxipng version is missing or an ordinary encoder trial fails
- **THEN** verified original/zlib/Zopfli alternatives SHALL remain usable
- **AND** diagnostics SHALL explain the unavailable refiltering trial.

#### Scenario: Local optional encoder ceiling is reached
- **WHEN** an optional trial reaches its local time ceiling while the root remains available
- **THEN** its owned process SHALL be stopped and partial output accounted and removed
- **AND** verified prior encodings SHALL remain usable
- **AND** actual root exhaustion or cancellation SHALL NOT be masked as a fallback.

### Requirement: Sequential PPT PNG root reservation
The system SHALL inspect and encode PPT PNGs sequentially with compact identities.
It SHALL derive a deterministic sample selection allowance from conservative
root decode reservations while retaining individual PNG and record-count bounds.
Every actual decode and process SHALL remain charged to the same root resource
limits. It SHALL NOT increase default root memory/decode/scratch/deadline limits.
Completed independent whole-host verification MAY be reused only when bound to
exact source and candidate digests and file snapshots. Publication SHALL retain
all source, candidate, metadata and destination conflict guards.
Embedded Photoshop storages and their independent object identities SHALL remain
byte-identical; storage sharing SHALL NOT be inferred from matching bytes.

#### Scenario: Image workload exceeds the old retained-sample allowance
- **WHEN** sequential processing can fit a larger qualified PNG workload in the root reservation
- **THEN** more images MAY be selected without retaining all expanded samples
- **AND** unselected images SHALL remain byte-identical.

#### Scenario: Actual root budget or cancellation is reached
- **WHEN** parsing, decoding, encoding or validation exhausts a root limit or is cancelled
- **THEN** no candidate SHALL be published and owned work SHALL be cleaned up.

#### Scenario: Files change after independent worker verification
- **WHEN** the source or candidate differs from the completed verification binding
- **THEN** acceptance SHALL refuse publication and retain the current source.
