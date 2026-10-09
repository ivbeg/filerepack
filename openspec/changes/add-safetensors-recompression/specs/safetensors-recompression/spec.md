## MODIFIED Requirements

### Requirement: Bounded content-based Safetensors inspection
The system SHALL identify Safetensors by validated content rather than extension
alone. Inspection SHALL parse the header and tensor ranges without loading tensor
objects, and SHALL enforce shared resource limits on header size, counts,
dimensions, offsets, and arithmetic.

#### Scenario: A file has a `.safetensors` suffix but an invalid range
- **WHEN** a tensor range exceeds the file bounds or conflicts with the declared shape and dtype
- **THEN** the file SHALL be reported unsupported or invalid and SHALL remain unchanged

## ADDED Requirements

### Requirement: Feasibility-gated writer registration
The system SHALL advertise a Safetensors writer profile only after complete real
files demonstrate savings accepted by the shared minimum-savings policy and
independent native readers accept the output. If no profile passes, the system
SHALL provide inspection-only results and SHALL NOT advertise recompression.

#### Scenario: Header rewriting produces no accepted saving
- **WHEN** every eligible candidate is unchanged or fails the minimum-savings policy
- **THEN** the source SHALL remain unchanged and no writer capability SHALL be registered

### Requirement: Exact tensor representation preservation
Any accepted rewrite SHALL preserve every tensor payload byte, tensor name, dtype,
shape, and metadata value. The system SHALL NOT quantize, cast, prune, reorder
tensor contents, or wrap the result in another file format.

#### Scenario: A candidate changes tensor payload bytes
- **WHEN** full range comparison finds any changed tensor byte
- **THEN** the candidate SHALL be rejected and SHALL NOT be published

### Requirement: Verified transactional publication
The system SHALL fully validate an eligible output with structural checks and the
qualified reader matrix before publication. Parse errors, reader failures, budget
exhaustion, cancellation, or publication failures SHALL preserve the source and
any prior destination.

#### Scenario: A reader rejects a staged output
- **WHEN** a required native-reader check fails
- **THEN** the staged candidate SHALL be discarded and the destination SHALL remain intact
