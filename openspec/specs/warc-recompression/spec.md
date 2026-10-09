# warc-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

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
