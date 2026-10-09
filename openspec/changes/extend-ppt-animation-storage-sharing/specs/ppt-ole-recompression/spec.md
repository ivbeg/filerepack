## MODIFIED Requirements

### Requirement: Preserve independent PPT objects when storage sharing fails qualification
The system SHALL retain separate compressed storage records for distinct PPT
persist IDs when independent reader/editing qualification fails. Complete
byte-identical wrappers SHALL NOT alone authorize aliasing physical persist
offsets, merging object IDs, or changing nested storage bytes. The existing
strict unique-target index and exact immutable-storage contracts SHALL remain in
force. After successful Pictures qualification the system SHALL report the number
and complete encoded-byte size of duplicate wrappers, and explain that sharing
was skipped, without claiming these bytes as realized savings. No nested CFB
color exception or new runtime sharing writer SHALL be enabled by this change.

#### Scenario: Identical storages belong to distinct objects
- **WHEN** a qualified presentation contains complete byte-identical storage wrappers
- **THEN** each object, persist ID, consumer and storage record SHALL remain separate and exact
- **AND** verbose output and the report SHALL explain the skipped sharing.

#### Scenario: Several persist IDs alias one physical storage
- **WHEN** an input or candidate aliases persist offsets
- **THEN** the existing qualified content inspector SHALL reject the ambiguous targets
- **AND** no new equality exemption SHALL authorize publication.

#### Scenario: Independent reader loses logical object resolution
- **WHEN** a development sharing experiment retains IDs but a qualified reader resolves fewer objects
- **THEN** that experiment SHALL remain excluded from runtime publication
- **AND** the verified image/compaction candidate SHALL remain eligible.
