# safetensors-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Bounded content-based Safetensors inspection
The system SHALL identify Safetensors by validated content rather than extension
alone. Inspection SHALL parse the header and tensor ranges without loading tensor
objects, and SHALL enforce shared resource limits on header size, counts,
dimensions, offsets, and arithmetic.

#### Scenario: A file has a `.safetensors` suffix but an invalid range
- **WHEN** a tensor range exceeds the file bounds or conflicts with the declared shape and dtype
- **THEN** the file SHALL be reported unsupported or invalid and SHALL remain unchanged
