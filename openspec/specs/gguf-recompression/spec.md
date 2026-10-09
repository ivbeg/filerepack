# gguf-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Bounded content-based GGUF inspection
The system SHALL classify GGUF using its validated content and SHALL inspect
supported headers, metadata, tensor descriptors, offsets, and alignment within
shared resource limits. Unknown, malformed, or ambiguous versions SHALL remain
unchanged.

#### Scenario: A GGUF descriptor points beyond end of file
- **WHEN** validated tensor bounds exceed the file or violate required alignment
- **THEN** the file SHALL be rejected without changing the source
