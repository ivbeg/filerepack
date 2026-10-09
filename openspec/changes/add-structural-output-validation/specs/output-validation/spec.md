## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Lossless Preservation Verification

Candidates advertised as lossless SHALL be compared with source decoded payloads or the format-specific logical preservation contract. Archives SHALL validate intended manifests and unchanged payloads; data/media/document validators SHALL compare their relevant logical content and required metadata under operation limits.

#### Scenario: Different decoded stream

- **WHEN** a structurally valid lossless stream candidate decodes to different bytes
- **THEN** publication SHALL be rejected despite smaller output

#### Scenario: Intended nested changes

- **WHEN** an archive candidate contains recorded accepted member optimizations
- **THEN** validation SHALL compare the intended manifest and preserve all unchanged payloads
