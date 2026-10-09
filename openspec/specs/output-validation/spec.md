# output-validation

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Declared Structural Candidate Validation

Every publishable writer SHALL declare an appropriate structural validator. Signature recognition alone SHALL NOT permit replacement. Unknown validator kinds, unavailable required validators, corrupt/truncated output, and unsuccessful structural tests SHALL prevent publication and provide a reason.

#### Scenario: Magic-valid corrupt output

- **WHEN** an encoder produces JPEG/PDF magic or a large MP4-like file with invalid structure
- **THEN** the candidate SHALL be rejected while the source remains unchanged

#### Scenario: Unknown or missing validator

- **WHEN** a writer requests an unknown validator or cannot run its required verifier
- **THEN** the operation SHALL report verification unavailable/failed and SHALL NOT publish

### Requirement: Smallest Valid PDF Candidate Selection

Unprotected PDF optimization SHALL retain and evaluate eligible original, image-walk, and qpdf candidates against validation and acceptance policy. Linearization SHALL be a separate documented constraint and SHALL NOT silently force discarding a smaller eligible non-linearized candidate.

#### Scenario: qpdf increases walked size

- **WHEN** an image-walk candidate is valid and smaller than the subsequent qpdf result
- **THEN** the smaller eligible valid candidate SHALL be selected unless an explicit linearization constraint excludes it
