# onnx-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Bounded passive ONNX inspection
The system SHALL identify supported ONNX models by content, enforce shared
limits on parsing and tensor metadata, and SHALL NOT execute model operators
during inspection or verification.

#### Scenario: A model exceeds inspection limits
- **WHEN** parsing exceeds a configured byte, recursion, count, memory, or time budget
- **THEN** the model SHALL remain unchanged and the result SHALL report a resource-limited outcome

### Requirement: Safe external-data resolution
The system SHALL distinguish inline tensor data from external-data references.
Before reading or writing a referenced file, it SHALL validate containment,
relative paths, offsets, lengths, and link components and SHALL reject traversal
or unresolved references.

#### Scenario: An external-data location escapes the model directory
- **WHEN** a location is absolute, traverses outside the model directory, or resolves through an escaping link
- **THEN** the bundle SHALL be rejected without reading or publishing the referenced target
