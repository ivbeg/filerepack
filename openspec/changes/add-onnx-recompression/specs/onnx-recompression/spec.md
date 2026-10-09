## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Feasibility-gated ONNX writer registration
The system SHALL advertise each ONNX writer profile only after complete real
files or bundles demonstrate savings accepted by shared size policy and
qualified ONNX readers accept the output. Self-contained and external-data
profiles SHALL be qualified separately. Profiles that fail SHALL remain
inspection-only and unchanged.

#### Scenario: An external-data bundle lacks reader evidence
- **WHEN** bundle-level preservation or native-reader validation has not passed
- **THEN** the external-data bundle SHALL remain unchanged and no bundle writer SHALL be registered

### Requirement: Exact ONNX model and tensor preservation
Any accepted rewrite SHALL preserve graph semantics and structure, opsets,
functions, known and unknown protobuf fields, metadata, tensor names/types/shapes,
and every tensor payload byte. If unknown fields cannot be retained, the model
SHALL remain unchanged. The system SHALL NOT optimize the graph, alter
operators, change tensor types, quantize, or wrap the model in another format.

#### Scenario: A candidate changes an initializer payload
- **WHEN** verification detects changed tensor bytes or model structure
- **THEN** the candidate SHALL be rejected and SHALL NOT be published

### Requirement: Atomic verified model publication
The system SHALL validate the complete staged model or external-data bundle and
its qualified reader result before publication. Failures, unsafe references,
resource exhaustion, cancellation, or publication errors SHALL preserve the
source and any prior destination.

#### Scenario: One sidecar fails bundle verification
- **WHEN** a referenced external-data file is missing or fails validation
- **THEN** no part of the candidate bundle SHALL be published
