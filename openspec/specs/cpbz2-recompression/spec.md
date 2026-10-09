# cpbz2-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: CPBZ2 Stream Identification
The system SHALL identify `.cpbz2` case-insensitively as a bzip2-wrapped CPIO
container and SHALL match it using `cpbz2`, `cpio` or `bz2` extension filters.
It SHALL retain the input filename and extension during recompression.

#### Scenario: CLI and bulk discovery
- **WHEN** a `.CPBZ2` file is supplied to `repack` or discovered by `bulk`
- **THEN** the file SHALL use the CPIO container handler
- **AND** `--include-ext cpbz2`, `--include-ext cpio` and `--include-ext bz2`
  SHALL match it

### Requirement: Exact CPIO Payload Preservation
The system SHALL preserve CPIO record order, paths, encoded metadata, links,
special entries, padding and every untouched member payload. It MAY replace the
payload and size of an eligible regular single-link member only when an existing
inner packer returns a verified preserving result. It SHALL validate the
complete CPIO and bzip2 candidate before publication. With deep walking disabled
or when no member is eligible, the decoded CPIO bytes SHALL remain exact.

#### Scenario: Verified member optimization
- **WHEN** a safe regular single-link member has a smaller preserving candidate
- **THEN** the candidate MAY contain that member's optimized bytes
- **AND** all other CPIO records and payloads SHALL remain unchanged

#### Scenario: No inner edit
- **WHEN** deep walking is disabled or no member is eligible for optimization
- **THEN** decoding an accepted bzip2 candidate SHALL yield the exact source CPIO
  bytes

### Requirement: Shared Publication Policies
Raw `.cpio`, `.cpbz2` and `.cpio.bz2` SHALL use the existing dry-run, size
savings, minimum-savings, destination and filesystem metadata policies. Raw CPIO
archives SHALL be eligible for safe member optimization.

#### Scenario: No improvement or dry-run
- **WHEN** a candidate does not meet the requested savings policy or dry-run is enabled
- **THEN** the source file SHALL remain byte-identical

#### Scenario: Distinct output
- **WHEN** a valid smaller candidate is requested at a different output path
- **THEN** the source SHALL remain unchanged and the verified candidate SHALL be
  published only to the requested output

### Requirement: CPBZ2 Legacy Extension Filter Compatibility
The system SHALL retain case-insensitive `cpbz2` and `bz2` extension filters for bzip2-wrapped CPIO inputs after introducing the preserving CPIO container writer.

#### Scenario: Legacy discovery filter
- **WHEN** `.CPBZ2` is discovered with either `--include-ext cpbz2` or `--include-ext bz2`
- **THEN** the input SHALL remain eligible under the current preserving CPIO policy
