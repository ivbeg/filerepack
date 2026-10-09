## MODIFIED Requirements

### Requirement: Bounded content-based GGUF inspection
The system SHALL classify GGUF using its validated content and SHALL inspect
supported headers, metadata, tensor descriptors, offsets, and alignment within
shared resource limits. Unknown, malformed, or ambiguous versions SHALL remain
unchanged.

#### Scenario: A GGUF descriptor points beyond end of file
- **WHEN** validated tensor bounds exceed the file or violate required alignment
- **THEN** the file SHALL be rejected without changing the source

## ADDED Requirements

### Requirement: Feasibility-gated GGUF writer registration
The system SHALL register a GGUF writer profile only after complete real-file
tests demonstrate accepted same-format savings and qualified native readers
accept the output, including required mmap behavior. If no profile passes, the
system SHALL NOT advertise a writer.

#### Scenario: No tested rewrite clears minimum savings
- **WHEN** all candidates are unchanged or fail shared size acceptance
- **THEN** the source SHALL remain unchanged and GGUF SHALL remain inspection-only

### Requirement: Exact GGUF tensor and model preservation
Any accepted rewrite SHALL preserve tensor payload bytes, tensor descriptors,
metadata values, format version, byte order, and the qualified alignment and
shard contract. The system SHALL NOT quantize, requantize, convert, or wrap the
model in another format.

#### Scenario: A candidate changes one quantized tensor byte
- **WHEN** verification detects a tensor payload difference
- **THEN** the candidate SHALL be rejected and SHALL NOT be published

### Requirement: Complete model-set qualification
A writer handling a sharded GGUF model SHALL qualify and publish the complete
model set as one logical operation. It SHALL preserve shard identity and SHALL
not route individual shards through a generic file or archive writer.

#### Scenario: One shard is missing from the input set
- **WHEN** a sharded model cannot be resolved as a complete qualified set
- **THEN** the set SHALL remain unchanged

### Requirement: Verified transactional GGUF publication
The system SHALL structurally validate and reader-check staged results before
publication. Failures, resource exhaustion, cancellation, or destination errors
SHALL preserve the source set and any prior destination.

#### Scenario: The native reader rejects a staged model
- **WHEN** a required reader or mmap check fails
- **THEN** no member of the staged output set SHALL be published
