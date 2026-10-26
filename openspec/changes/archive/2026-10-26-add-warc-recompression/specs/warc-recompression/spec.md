## MODIFIED Requirements

### Requirement: Preserving record compression
The system SHALL encode supported WARC 1.0/1.1 records into separate level-9 gzip
members, preserving all decoded bytes and ordered record boundaries.

#### Scenario: Existing record-compressed archive
- **WHEN** a supported `.warc.gz` contains multiple gzip members
- **THEN** each output member contains exactly one unchanged WARC record.

#### Scenario: Whole-file gzip input
- **WHEN** one source gzip member contains multiple valid WARC records
- **THEN** a qualifying candidate has one gzip member per record and identical decoded bytes.

#### Scenario: Opaque payload and metadata
- **WHEN** a record contains HTTP encoding, unknown fields or a revisit reference
- **THEN** all payload and header bytes, including existing digests, remain exact.

### Requirement: WARC-aware routing and conversion
The system SHALL route `.warc.gz` and WARC-bearing `.gz` through the WARC handler
before generic gzip. Standalone plain `.warc` SHALL convert to `.warc.gz` using
collision-safe destination planning when conversion is enabled.

#### Scenario: Plain standalone archive
- **WHEN** a supported plain `.warc` produces a qualifying smaller candidate
- **THEN** the candidate is published at the planned `.warc.gz` destination.

#### Scenario: Conversion disabled or nested
- **WHEN** a plain WARC is nested in another container or conversion is disabled
- **THEN** the original member name, extension and bytes remain unchanged.

#### Scenario: Extension filtering
- **WHEN** bulk uses `--include-ext warc`
- **THEN** both `.warc` and `.warc.gz` names qualify.

### Requirement: Independent verification and safe publication
The system SHALL refuse malformed framing, gzip corruption, unsupported versions,
candidate content differences and candidates without one record per member. It
SHALL apply shared dry-run, savings, backup, source snapshot and output policies,
and bounded parsing, scratch, time, record-count and cancellation checks.

#### Scenario: Corrupt input or candidate
- **WHEN** a record is truncated, has an invalid length or a gzip trailer fails
- **THEN** no candidate is published and scratch files are cleaned.

#### Scenario: Policy rejection
- **WHEN** dry-run is enabled, savings are insufficient or a budget is exhausted
- **THEN** the source is retained and the result explains the outcome.

### Requirement: Index awareness
The system SHALL skip replacement of a WARC with detected adjacent CDX/CDXJ
indexes and SHALL document that other indexes require rebuilding after rewriting.

#### Scenario: Indexed source
- **WHEN** an in-place request finds a neighbouring index
- **THEN** the archive and index remain unchanged with an explanatory result.

#### Scenario: Distinct output
- **WHEN** an indexed source is written to a distinct unindexed destination
- **THEN** the source and its indexes remain intact and the output uses new offsets.
