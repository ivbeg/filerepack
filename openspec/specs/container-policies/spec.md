# container-policies

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Specialized Package Structure

ODF and EPUB rewrites SHALL retain mimetype as the first ZIP entry, stored uncompressed with no local-header extra field, and SHALL preserve applicable package manifests and required members. Other specialized aliases SHALL be rewritten only under a validated policy for their headers, ordering, compression, and structural constraints.

#### Scenario: ODF or EPUB rebuild

- **WHEN** a valid package is rebuilt with or without nested walking
- **THEN** mimetype SHALL remain first, stored, without an extra field, and package requirements SHALL validate

#### Scenario: Unsupported wrapper or layout

- **WHEN** an alias has wrapper/header/compression rules the chosen writer cannot preserve
- **THEN** it SHALL be reported unsupported without publication

### Requirement: Integrity Protected Package Handling

Packages with signatures SHALL be left unchanged by default. Checksummed packages SHALL permit member changes only if a supported policy can update required manifests and verify the resulting integrity. Unknown protection/manifest semantics SHALL prevent publication.

#### Scenario: Signed package

- **WHEN** an integrity-protected signed JAR/APK/MSIX or equivalent is discovered
- **THEN** nested content and container bytes SHALL remain unchanged and protection SHALL be reported

#### Scenario: Checksummed member changes

- **WHEN** a supported checksummed package accepts a member optimization
- **THEN** required integrity records SHALL be updated and verified before publication
