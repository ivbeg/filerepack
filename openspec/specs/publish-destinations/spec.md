# publish-destinations

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Validation Before Filesystem Mutation

CLI and library operations SHALL validate options, source/destination identities, and destination policy before backups, output copies, or mutating work. Numeric settings SHALL be finite and within documented ranges; size suffixes SHALL be parsed consistently. Invalid requests SHALL produce a clear error and zero writes.

#### Scenario: Invalid PDF profile with existing output

- **WHEN** a request names an existing output and an invalid PDF profile
- **THEN** it SHALL fail without changing source, output, or backups

#### Scenario: Invalid range or size

- **WHEN** a request uses quality 500, compression 99, negative size, or a non-finite threshold
- **THEN** it SHALL fail before writes

#### Scenario: Size suffix without B

- **WHEN** a size option contains `1G`
- **THEN** it SHALL mean 1073741824 bytes rather than one byte

### Requirement: Collision Safe Output Publication

Distinct output, conversion, and backup paths SHALL be normalized and reserved before mutation. An existing different destination SHALL NOT be replaced without an explicit overwrite policy. Required backups SHALL NOT be overwritten, and backup failure SHALL prevent destructive processing.

#### Scenario: Conversion collision

- **WHEN** video or RAR conversion would create a path belonging to an existing different file
- **THEN** the operation SHALL report a conflict and preserve both files

#### Scenario: Competing jobs or backup failure

- **WHEN** jobs compete for one target or a requested backup cannot be created
- **THEN** only one reservation SHALL succeed and unprotected destructive work SHALL not proceed

### Requirement: Consistent Library Output Destinations

A distinct `outfile` SHALL preserve source bytes for standalone and archive inputs and publish at the requested effective destination. If no improved candidate is accepted, a verified unchanged copy SHALL be published there. Converted extensions SHALL be reflected in the reported destination. Dry-run SHALL create no source, destination, or backup artifacts.

#### Scenario: Standalone distinct outfile

- **WHEN** the library repacks JSON or a stream with a distinct outfile
- **THEN** the source SHALL be unchanged and the effective output SHALL be produced

#### Scenario: No accepted improvement

- **WHEN** a distinct-output request has no accepted smaller candidate
- **THEN** the destination SHALL contain a verified unchanged copy when publication policy permits it

#### Scenario: Dry-run distinct outfile

- **WHEN** a request with outfile and backup is a dry-run
- **THEN** no source, destination, or backup artifact SHALL be changed or created
