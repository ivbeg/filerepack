## ADDED Requirements

### Requirement: Distinct absent store destination
The initial store entry point SHALL require a distinct output parent and SHALL
target `PARENT/basename(SOURCE)`. Source, destination and staging trees SHALL be
disjoint. Existing destinations SHALL be refused; in-place overwrite and directory
merge SHALL NOT be supported. Dry-run SHALL inspect without staging or publication.

#### Scenario: Output parent is nested inside the source
- **WHEN** the requested destination or staging would overlap the source tree
- **THEN** the operation SHALL fail before any candidate data is written

#### Scenario: Destination already exists
- **WHEN** a directory or file occupies the intended destination
- **THEN** it SHALL remain untouched and the store operation SHALL report a collision

### Requirement: Owned destination local directory staging
The system SHALL create a private operation-owned staging directory on the target
filesystem, enforce cumulative store resource budgets, preserve required file
attributes, and reject symlinks, special files, escaping keys and destination key
collisions. Cleanup SHALL affect only owned staging paths.

#### Scenario: Two source keys collide on the destination filesystem
- **WHEN** distinct keys normalize to the same destination path
- **THEN** staging SHALL be rejected without overwriting either source object

### Requirement: Stable source generation checks
The system SHALL require an offline store or stable snapshot, record its complete
key/file generation manifest, and recheck required source generations before
publication. Detected additions, removals or content changes SHALL abort publication.
Generation checks SHALL not be described as a general active-writer snapshot protocol.

#### Scenario: Another process adds a chunk during recompression
- **WHEN** the source key manifest changes before publication
- **THEN** the system SHALL discard staging and retain the source unchanged

### Requirement: Verified atomic no replace directory publication
The system SHALL publish a completely verified store using a tested atomic
no-replace directory primitive on the destination filesystem. If the platform
cannot establish this guarantee, publication SHALL fail safely. Ordinary rename
semantics that can overwrite an empty directory SHALL NOT be used as a substitute.

#### Scenario: Another process creates the destination after initial checks
- **WHEN** the destination appears immediately before publication
- **THEN** publication SHALL fail without replacing or merging that destination

### Requirement: Cancellation and no benefit preserve user trees
Cancelled, failed, resource-limited or non-beneficial operations SHALL remove owned
staging and SHALL preserve source and existing destination trees. No partial store
SHALL be exposed at the requested final path.

#### Scenario: Cancellation occurs after several arrays are staged
- **WHEN** cancellation is received before atomic publication
- **THEN** the final path SHALL remain absent and owned staging SHALL be cleaned
