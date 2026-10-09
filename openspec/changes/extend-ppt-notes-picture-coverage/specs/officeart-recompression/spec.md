## MODIFIED Requirements

### Requirement: Independent notes-bearing PPT Pictures qualification

The system SHALL qualify Pictures recompression separately from embedded DOC/XLS
record recompression for audited notes-bearing PPT hosts. It SHALL bind every
untouched external-object wrapper and consumer to the same logical host object,
preserve them byte-identically, and account for every selected delay-store BLIP.
It SHALL permit audited shared FBSE entries while preserving BStore indexes,
sharing counts, UIDs and all shape properties. A bounded deterministic PNG
selection SHALL retain unselected BLIPs byte-identically without increasing the
existing operation limits. Verification SHALL compare the qualified exact PNG
sample identity (filtered or independently unfiltered) and non-IDAT chunks,
every unchanged record and all outer CFB metadata/streams;
only selected BLIP encodings and their enumerated FBSE size/delay fields may
change. Acceptance SHALL use verified final-file savings over ordinary compaction.

#### Scenario: Untouched subtype-zero object is referenced by a master
- **WHEN** an audited host has a uniquely resolved subtype-zero external object
  referenced by a live main master and only Pictures payloads are selected
- **THEN** its complete original wrapper, identity and references SHALL remain exact
- **AND** its inability to pass the separate DOC/XLS re-encoding profile SHALL NOT
  alone disqualify the Pictures strategy

#### Scenario: Multiple shapes share one BStore entry
- **WHEN** an audited FBSE has positive cRef greater than one and valid consumers
- **THEN** selected image recompression SHALL retain its index, sharing and UID
- **AND** every delay-store offset and size change SHALL resolve to the same image

#### Scenario: Total image workload exceeds the selection allowance
- **WHEN** some individually qualified PNGs would exceed the cumulative selection
  allowance
- **THEN** a deterministic bounded subset MAY be selected
- **AND** all other BLIPs SHALL be retained byte-identically
- **AND** actual root-budget exhaustion SHALL fail the trial rather than be ignored

#### Scenario: Notes or immutable object data changes during Pictures rewriting
- **WHEN** a candidate changes any notes byte, external-object wrapper, consumer,
  count, UID or other byte outside the precise permitted write fields
- **THEN** independent preservation verification SHALL reject it before publication
