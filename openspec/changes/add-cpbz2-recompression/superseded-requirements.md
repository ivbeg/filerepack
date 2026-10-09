# Superseded requirement wording

Preserved from the original delta during the 2026-10-07 baseline audit.
The live requirement is owned by the later change listed in the baseline audit.

## cpbz2-recompression

### Requirement: CPBZ2 Stream Identification
The system SHALL identify `.cpbz2` case-insensitively as a standalone bzip2
stream and SHALL match it using either `cpbz2` or `bz2` extension filters.
It SHALL retain the input filename and extension during recompression.

#### Scenario: CLI and bulk discovery
- **WHEN** a `.CPBZ2` file is supplied to `repack` or discovered by `bulk`
- **THEN** the file SHALL use the bzip2 stream recompressor
- **AND** `--include-ext cpbz2` and `--include-ext bz2` SHALL both match it

## cpbz2-recompression

### Requirement: Exact CPIO Payload Preservation
The system SHALL recompress only the external bzip2 stream at level 9 using the
existing external-tool or standard-library encoder. It SHALL validate the
complete candidate stream and compare SHA-256 of the fully decoded source and
candidate before publication. It SHALL keep CPIO member headers, order, links,
metadata, payloads and padding byte-identical, without extracting or rewriting
members even when deep walking is enabled.

#### Scenario: Lossless recompression without external tools
- **WHEN** a valid `.cpbz2` is processed and the bzip2 executable is unavailable
- **THEN** the standard-library encoder SHALL produce a level-9 bzip2 candidate
- **AND** decoding an accepted candidate SHALL yield the exact source CPIO bytes

#### Scenario: Nested CPBZ2
- **WHEN** a supported parent archive contains a `.cpbz2` member
- **THEN** the member SHALL be eligible for outer-stream recompression
- **AND** its member path and decoded CPIO bytes SHALL remain unchanged

#### Scenario: Candidate failure
- **WHEN** decoding fails, candidate validation is unavailable, or decoded
  candidate content differs from the source
- **THEN** the original `.cpbz2` SHALL remain unchanged

## cpbz2-recompression

### Requirement: Shared Publication Policies
CPBZ2 recompression SHALL obey the existing dry-run, size savings, minimum
savings, destination and filesystem metadata policies. Raw `.cpio` archives
SHALL remain unsupported for extraction and rewriting.

#### Scenario: No improvement or dry-run
- **WHEN** a candidate does not meet the requested savings policy or dry-run is enabled
- **THEN** the source file SHALL remain byte-identical

#### Scenario: Distinct output
- **WHEN** a valid smaller candidate is requested at a different output path
- **THEN** the source SHALL remain unchanged and the verified candidate SHALL be
  published only to the requested output
