## MODIFIED Requirements

### Requirement: Lossless tracev3 recompression

The system SHALL offer opt-in recompression for supported standalone `.tracev3` files by rewriting LZ4 blocks within recognized chunksets. It SHALL preserve decoded chunkset payloads, chunk order, and all bytes outside rewritten chunkset encodings. It SHALL retain an existing block encoding when a replacement is not strictly smaller and SHALL publish a candidate only when the complete result is smaller and passes structural and lossless validation.

#### Scenario: Smaller lossless candidate
- **WHEN** a supported `.tracev3` file contains LZ4 blocks that can be encoded smaller within the requested compression level
- **THEN** the system publishes a structurally valid file whose decoded chunkset payloads and non-target bytes match the source

#### Scenario: No compression benefit
- **WHEN** recompression does not produce a smaller complete file
- **THEN** the source remains unchanged and the operation reports no size reduction

### Requirement: Fail closed on unsupported or unsafe tracev3 inputs

The system SHALL leave the source unchanged when parsing, decoding, dependency loading, validation, or resource-bounded processing fails. It SHALL reject in-place rewriting when the source or destination is within macOS's active Unified Log store.

#### Scenario: Unsupported structure or corrupt block
- **WHEN** a `.tracev3` input contains malformed lengths, an unknown block marker, corrupt LZ4 data, or a layout outside the supported profile
- **THEN** the system does not publish a rewritten candidate and reports that the input was unsupported or invalid

#### Scenario: Active log store in-place operation
- **WHEN** a requested operation would write a `.tracev3` result inside the active macOS Unified Log store or replace its source in place
- **THEN** the system refuses the operation without modifying the log file

#### Scenario: Resource budget exceeded
- **WHEN** processing exceeds configured memory, decoded-byte, scratch, node, or time limits
- **THEN** the worker is stopped and the original file remains unchanged
