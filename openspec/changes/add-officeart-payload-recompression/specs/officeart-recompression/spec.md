## MODIFIED Requirements

### Requirement: Shared codec with authoritative host discovery
The system SHALL recompress EMF/WMF only after a qualified host adapter resolves
the containing OfficeArt records and every affected reference. The initial
operation SHALL be opt-in through the existing `ole_recompress` option. It SHALL
NOT select payloads by signature scanning of opaque CFB streams.

#### Scenario: Same codec in multiple hosts
- **WHEN** qualified DOC, XLS and PPT records contain compressed EMF/WMF
- **THEN** the same bounded RFC1950 codec processes them
- **AND** each host adapter independently repairs its own lengths and pointers.

#### Scenario: Unsupported host representation
- **WHEN** discovery cannot fully resolve a layout, history, alias or pointer
- **THEN** the operation retains a strictly verified compaction candidate
- **AND** exposes the reason for skipping content recompression.

### Requirement: Exact metafile preservation and separate verification
The system SHALL preserve every decoded metafile byte, UID, geometry, order and
reference identity. It SHALL preserve all unrelated stream and record bytes and
complete CFB logical metadata. It SHALL verify intended changes separately from
the strict `ole` verifier, which SHALL retain its byte-equality contract.

#### Scenario: Valid smaller representation
- **WHEN** the compressed bytes change and all intended-content checks pass
- **THEN** the OfficeArt verifier accepts the candidate
- **AND** strict `ole` equality still rejects the changed representation.

#### Scenario: Damaged payload or stale reference
- **WHEN** a decoded byte, checksum, UID, geometry, pointer, unrelated record or
  directory metadata differs outside the allowed changes
- **THEN** the candidate is rejected before publication.

### Requirement: Bounded encoding and measured candidate selection
The system SHALL share root-operation budgets and supervise encoding in a
killable worker. It SHALL check lengths, checksum, end-of-stream and trailing
data before and after encoding. It SHALL retain original wrappers when no
encoder improves them, and select content recompression only when its fully
verified file is smaller than the verified compaction baseline.

#### Scenario: Stream savings without file savings
- **WHEN** smaller compressed payloads do not reclaim additional CFB allocation
- **THEN** the operation selects the strict compaction baseline
- **AND** reports the lack of additional physical savings.

#### Scenario: Budget exhausted or operation cancelled
- **WHEN** parsing or encoding exceeds the shared budget or is interrupted
- **THEN** no candidate is published
- **AND** operation-owned processes and scratch files are cleaned up.

### Requirement: Raster image qualification is explicit
The initial capability SHALL copy PNG/JPEG and other non-EMF/WMF BLIPs unchanged.
Raster recompression SHALL require a separately qualified pixel/coefficient,
metadata, color, UID and reference preservation contract.

#### Scenario: Mixed raster and metafile store
- **WHEN** a qualified OfficeArt store contains JPEG, PNG, EMF and WMF
- **THEN** only EMF/WMF are eligible in the initial stage
- **AND** JPEG/PNG bytes and metadata remain identical.

### Requirement: Existing transaction and diagnostic policies apply
The system SHALL use the existing dry-run, minimum-savings, backup, output,
filesystem-attribute and archive-member policies. It SHALL expose actual
strategy, payload counts, measured savings and unsupported/no-op reasons.

#### Scenario: Verbose DOC with no eligible payload
- **WHEN** a DOC contains no qualified OfficeArt metafiles
- **THEN** verbose output explains why content recompression was skipped
- **AND** distinguishes it from any container-compaction result.
