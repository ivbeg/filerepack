## MODIFIED Requirements

### Requirement: Explicit byte-identical OfficeArt deduplication
The system SHALL offer default-false ole_deduplicate_images for qualified shared
picture stores. Equality SHALL require complete BLIP bytes and compatible
FBSE/identity metadata after exact comparison; digest or rendered-pixel equality
alone SHALL NOT authorize merging. Other options SHALL remain independent.

#### Scenario: Repeated identical image
- **WHEN** the option is enabled and two compatible store entries contain identical BLIPs
- **THEN** one can be retained and the other removed after complete reference verification.

#### Scenario: Same pixels with different metadata or UID
- **WHEN** two entries render alike but differ in image bytes, identity or retained metadata
- **THEN** they are not deduplicated by the initial profile.

### Requirement: Exhaustive deduplication consumer mapping
The system SHALL resolve all affected picture, fill, line, print and host
references including hidden/grouped objects. It SHALL apply qualified index and
count semantics and reject stores with unresolved consumers or ambiguous aliases.
It SHALL preserve retained entry order and every consumer's display properties.

#### Scenario: Several shapes use different crops of one image
- **WHEN** compatible duplicates are referenced by shapes with different crop/anchor properties
- **THEN** all references target the retained identical image and each shape's crop/anchor bytes remain exact.

#### Scenario: Unknown property could hold an image reference
- **WHEN** a store has an unqualified private/reference-bearing property
- **THEN** deduplication for that store is skipped with a specific reason.

### Requirement: Independent image removal verification
The system SHALL independently compare the complete source/candidate image
consumer graphs, prove each removed entry's equivalent retained target, and
account for every removed span and changed count/index/size/location field.
Unrelated bytes and CFB metadata SHALL match; strict OLE SHALL remain unchanged.

#### Scenario: Valid index selects a different image
- **WHEN** a relocated consumer references another in-bounds store entry
- **THEN** normalized graph verification rejects the candidate.

#### Scenario: Undeclared entry is removed
- **WHEN** a candidate removes an orphan/history entry or any incompatible image
- **THEN** verification rejects it regardless of file-size savings.

### Requirement: Bounded deduplication with actual savings reporting
The system SHALL share root graph/memory/time budgets and existing protection,
transaction and final-file threshold policies. It SHALL independently verify
any composed transformation and report removed entries, repaired references,
actual strategy, physical savings and no-op/unsupported reasons.
It SHALL honor effective parent image/category selection.

#### Scenario: Store removal does not reduce allocated file size
- **WHEN** the verified deduplicated file is not smaller than the existing verified baseline
- **THEN** the baseline is retained and no additional saving is claimed.

#### Scenario: Option is disabled
- **WHEN** the deduplication option is false
- **THEN** other compression modes retain all store entries under their existing contracts.
