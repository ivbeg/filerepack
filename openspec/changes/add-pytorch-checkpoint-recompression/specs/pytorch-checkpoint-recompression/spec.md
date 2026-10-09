## ADDED Requirements

### Requirement: Native reader feasibility before checkpoint writers
The system SHALL enable a checkpoint writer profile only after native framework
tests establish accepted ZIP methods, layout and load behavior, and smaller
real-file examples demonstrate benefit. Failed combinations SHALL be excluded.
If no profile passes the feasibility gate, the system SHALL provide classification/
inspection only and SHALL NOT advertise checkpoint compression.

#### Scenario: A generic ZIP reader succeeds but torch.load rejects DEFLATE
- **WHEN** native reader tests reject a compressed checkpoint record class
- **THEN** that method SHALL not be generated for the profile

### Requirement: Passive checkpoint content classification
The system SHALL identify supported modern checkpoint layout/version through
complete container inspection, independent of `.pt`/`.pth` suffixes. It SHALL
reject ambiguous, encrypted, signed, duplicate-record, legacy or unsupported
TorchScript/distributed layouts without deserializing pickle or executing globals.

#### Scenario: A checkpoint contains an executable pickle reducer
- **WHEN** its ZIP members are inspected or verified
- **THEN** the pickle payload SHALL be treated as bytes and SHALL never be invoked

### Requirement: Exact checkpoint record preservation
The system SHALL preserve every decoded pickle/storage/metadata record byte,
required member name/order and supported layout attributes. It SHALL NOT trim,
clone, quantize or reconstruct tensor storage. Candidate verification SHALL check
complete decoded-member equality and container integrity under shared budgets.

#### Scenario: Smaller storage would remove unused shared values
- **WHEN** a tensor view references part of a larger saved storage
- **THEN** all source storage bytes SHALL remain and storage trimming SHALL not be attempted

### Requirement: Mmap preserving default compatibility
The default `checkpoint_compatibility=preserve-mmap` SHALL retain STORED tensor
payloads and tested alignment/layout properties with native mmap compatibility.
Metadata compression SHALL occur only for proven compatible methods. A profile
with no beneficial eligible candidate SHALL return unchanged.

#### Scenario: Compressing storage would save most of the file
- **WHEN** ordinary repack uses default checkpoint options
- **THEN** the handler SHALL retain STORED storage and SHALL not sacrifice mmap for that saving

### Requirement: Explicit load only compatibility
A proven `checkpoint_compatibility=load-only` profile SHALL require explicit user
selection and SHALL disclose the changed mmap behavior and target-reader requirements.
It SHALL retain exact data and object representations. General effort, growth or
lossy flags SHALL NOT implicitly select this profile.

#### Scenario: High effort is requested without checkpoint selection
- **WHEN** a user increases general compression effort
- **THEN** checkpoint processing SHALL still use the mmap-preserving default

### Requirement: Protected nested checkpoint routing
Recognized checkpoints and recognized unsupported checkpoint variants SHALL be
handled by checkpoint policy before generic ZIP recompression, including inside
ordinary archive recursion. Unsupported checkpoint members SHALL be copied unchanged.

#### Scenario: A PT file is nested in a ZIP archive
- **WHEN** archive-member optimization encounters recognized checkpoint content
- **THEN** it SHALL honor checkpoint compatibility policy or retain that member unchanged

### Requirement: Verified transactional checkpoint results
Every accepted candidate SHALL satisfy complete passive preservation checks and
shared size/publication rules. Missing required validation, limits, corruption,
cancellation or publication errors SHALL leave source and prior destination intact.
Reports SHALL distinguish verified byte preservation from the fixture-tested native reader matrix.

#### Scenario: A new framework version has no compatibility evidence
- **WHEN** reporting an accepted file under a previously tested profile
- **THEN** the result SHALL not claim validation against that untested framework version
