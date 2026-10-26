## MODIFIED Requirements

### Requirement: Per-record gzip candidate selection
The system SHALL compare eligible source gzip members and newly encoded gzip
members independently for each WARC record, choose the smallest fully verified
candidate, and preserve exact decoded record bytes, order and one-record-per-member
output framing.

#### Scenario: Source member is smaller
- **WHEN** one complete, valid source gzip member contains exactly one WARC record
  and is smaller than the zlib-9 candidate
- **THEN** the output reuses that member and validates its decoded bytes against
  the source record.

#### Scenario: Source member contains multiple records or a partial record
- **WHEN** an input gzip member is not exactly one complete WARC record
- **THEN** that member is not reused and output candidates are encoded per record.

#### Scenario: Records have mixed winners
- **WHEN** source, zlib-9 and optional high-effort candidates have different sizes
  across records
- **THEN** the system selects each record's smallest verified gzip member and
  retains record order and boundaries.

#### Scenario: Candidates tie in size
- **WHEN** two valid candidates for a record have the same compressed size
- **THEN** the existing source member is preferred; otherwise zlib-9 is preferred.

### Requirement: Bounded ultra WARC compression
When the existing `ultra` option is enabled, the system SHALL pass it to the WARC
encoder and MAY add a qualified optional Zopfli-15 gzip candidate for eligible
records. An unavailable, interrupted, out-of-cap or larger trial SHALL retain the
smallest fully verified candidate already available. All shared operation limits
and archive-level acceptance policies SHALL continue to apply.

#### Scenario: Qualified optional encoder is available
- **WHEN** ultra is enabled and Zopfli is available for a record within the
  qualified size cap
- **THEN** its independently checked result participates in per-record size
  selection.

#### Scenario: Optional encoder is unavailable or record exceeds the cap
- **WHEN** ultra is enabled but Zopfli is unavailable or the record is outside
  the qualified size range
- **THEN** the best verified source or zlib-9 candidate is retained.

#### Scenario: High-effort result is larger
- **WHEN** the Zopfli member is larger than the source or zlib-9 member
- **THEN** the smaller prior candidate remains selected.

#### Scenario: Shared budget expires
- **WHEN** cancellation or a shared operation limit is reached during an
  optional compression trial
- **THEN** current transaction failure/source-retention rules apply and no
  partially verified output is published.
