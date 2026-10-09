# cpio-member-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: CPIO Container Recognition
The system SHALL recognize raw `.cpio`, bzip2-wrapped `.cpbz2` and `.cpio.bz2`
as CPIO archive containers. A generically named `.bz2` SHALL be recognized as
CPIO only when its bounded decoded prefix matches a supported CPIO record magic.

#### Scenario: Named compressed archive
- **WHEN** the user processes `backup.cpbz2` or `backup.cpio.bz2`
- **THEN** the system SHALL deep-walk members and preserve the CPIO archive name
  and bzip2 wrapper

#### Scenario: Generic bzip2 input
- **WHEN** a `.bz2` file decodes to a supported CPIO format
- **THEN** it SHALL be processed as bzip2-wrapped CPIO
- **WHEN** its decoded prefix is not CPIO
- **THEN** it SHALL retain generic bzip2-stream behavior

### Requirement: Bounded CPIO Profile Parsing
The system SHALL validate and preserve old-binary, odc, newc and CRC-newc CPIO
record boundaries, member order, encoded metadata and trailer/padding bytes.
It SHALL enforce extraction byte, ratio, member-count and scratch bounds before
publishing any rewritten archive.

#### Scenario: Valid CPIO profile
- **WHEN** a complete archive uses one of the supported CPIO profiles
- **THEN** every record SHALL be read and validated through its trailer
- **AND** one unsupported profile or malformed record SHALL skip member edits

### Requirement: Safe CPIO Member Optimization
When deep walking is enabled, the system SHALL apply existing file packers only
to eligible regular single-link members with safe, unambiguous relative paths.
It SHALL preserve paths, order, modes, IDs, times, device numbers, directory,
symlink and hard-link records, and unrelated payload bytes. Symlinks SHALL NOT
be followed, and hard-link groups and device/FIFO records SHALL NOT be edited.

#### Scenario: Regular supported member
- **WHEN** a validated CPIO has a safe regular member supported by an existing
  packer and that packer returns a verified smaller candidate
- **THEN** that member payload SHALL be updated without changing its path, order
  or non-size metadata

#### Scenario: Symlink, hard link or special file
- **WHEN** a CPIO contains symlink, hard-link or special-file entries
- **THEN** those entries SHALL not be materialized or optimized, and all entries
  SHALL retain their original encoded metadata and target/link relationships

#### Scenario: Unsafe or ambiguous paths
- **WHEN** member names escape the staging root, collide across supported
  path-normalization rules or conflict with another member's path type
- **THEN** member extraction and inner rewriting SHALL be skipped safely

### Requirement: Independently Verified CPIO Publication
Before publication, the system SHALL reparse the encoded output, compare every
source and candidate member in order, require byte-identical metadata for each
entry and exact payload equality for untouched members, and restrict differing
payloads to paths with accepted verified inner packer results. Bzip2-wrapped
archives SHALL additionally pass full stream integrity validation. The system
SHALL obey existing dry-run, size, minimum-savings, destination and filesystem
metadata policies.

#### Scenario: Candidate changes an unrelated member
- **WHEN** any member metadata or untouched payload differs
- **THEN** the candidate SHALL be rejected and the source SHALL remain unchanged

#### Scenario: No safe edits or unsupported archive
- **WHEN** no member is eligible or a CPIO profile is unsupported
- **THEN** member bytes SHALL remain unchanged and the existing outer bzip2
  recompression route MAY still run for compressed CPIO

#### Scenario: Dry run or insufficient savings
- **WHEN** dry-run is enabled or the rewritten candidate fails shared size rules
- **THEN** the source archive SHALL remain unchanged
