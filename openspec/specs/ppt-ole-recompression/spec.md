# ppt-ole-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Explicit PPT record recompression mode

The system SHALL offer opt-in compressed embedded-OLE record recompression for
qualified PPT/POT/PPS files. With the option disabled, it SHALL retain the existing
OLE compaction contract of identical live stream bytes. DOC/XLS outer documents
SHALL retain their existing behavior.

#### Scenario: Default PPT compaction
- **WHEN** a user repacks a PPT without enabling OLE record recompression
- **THEN** every live application stream SHALL remain byte-identical
- **AND** record-level encoding changes SHALL be rejected by the strict OLE verifier

#### Scenario: Explicit mode reaches an archive member
- **WHEN** the option is enabled for a qualified PPT member in a supported archive
- **THEN** the worker/member handler SHALL receive the same explicit setting
- **AND** both inner preservation and outer member-preservation policies SHALL apply

### Requirement: Qualified single-edit embedded-object selection

The system SHALL select compressed storage records only through complete,
unambiguous ExOleEmbedContainer/ExOleObjAtom/ExObjRefAtom and persist references
in the current document. The first profile SHALL require one edit, one persist
directory, unique identifiers/targets, recognized nested DOC/XLS profiles and
a final contiguous compressed-storage block followed by its directory and edit.
It SHALL reject VBA, linked/ActiveX objects, protection ambiguity, unqualified
extensions, multi-edit/interleaved layouts and malformed references.

#### Scenario: Supported embedded objects
- **WHEN** each embedded DOC/XLS object has a unique qualified live reference and
  the required trailing layout
- **THEN** only its identified compressed storage SHALL be eligible for re-encoding
- **AND** unrelated streams and application records SHALL be preserved

#### Scenario: Shared storage type hides a VBA or control object
- **WHEN** a storage has the same record type as an OLE object but resolves to
  VBA, ActiveX, linked or unclassified data
- **THEN** the record recompression profile SHALL be rejected
- **AND** any ordinary compaction fallback SHALL pass its own strict eligibility/verifier

### Requirement: Exact decoded-storage preservation and checked relocation

The system SHALL preserve every decoded storage byte, wrapper version/instance,
decoded-size field and object identity. It SHALL update only selected compressed
data/record lengths and the mapped persist-directory, user-edit and Current User
position fields. It SHALL retain unchanged records, ordering, persist IDs/counts,
all directory metadata and all other stream bytes. Arithmetic and references
SHALL be bounded and resolve to the same logical objects after rewriting.

#### Scenario: A compressed storage becomes shorter
- **WHEN** an encoder produces a smaller valid RFC1950 representation
- **THEN** its decoded bytes SHALL equal the original storage exactly
- **AND** every affected reference SHALL map to the same logical target
- **AND** no nested CFB compaction or application-level resave SHALL occur

#### Scenario: An encoder offers no wrapper improvement
- **WHEN** alternative encodings are equal to or larger than the source wrapper
- **THEN** that original wrapper SHALL be retained byte-identically

### Requirement: Independent intended-change verification

The system SHALL use a separate PPT record preservation contract, leaving strict
OLE stream equality intact. It SHALL independently reparse source and candidate,
compare complete CFB object metadata and unaffected stream hashes, verify exact
decoded bytes and nested manifests, and account for every allowed record/offset
change. Rendering or a successful writer exit SHALL NOT replace these checks.

#### Scenario: A persist offset is not repaired
- **WHEN** a candidate contains a stale offset or resolves a reference to another object
- **THEN** preservation verification SHALL reject it before publication

#### Scenario: An unrelated byte or metadata field changes
- **WHEN** a candidate modifies a decoded object, unaffected stream/record, directory
  field or Current User byte outside the permitted offset
- **THEN** preservation verification SHALL reject it before publication

#### Scenario: Strict compaction verifier sees re-encoded data
- **WHEN** a valid re-encoded PPT is compared under the ordinary `ole` contract
- **THEN** the changed PowerPoint Document stream SHALL fail strict hash equality
- **AND** only an explicitly selected, qualified PPT record contract can accept it

### Requirement: Bounded encoders and compatible native replacement

The system SHALL enforce file, record, selected-object, encoded/decoded aggregate,
scratch, memory and overall-time bounds. Zlib level 9 SHALL be available without
a new mandatory dependency; any stronger Zopfli pass SHALL use qualified optional
versions in a killable worker without raising Python 3.9+ compatibility. Native
replacement SHALL be limited to the two named PPT streams and SHALL require
explicit compatible helper capability.

#### Scenario: Invalid termination or decoded expansion
- **WHEN** a storage has an incorrect length, invalid checksum, trailing/concatenated
  zlib data or exceeds a byte budget
- **THEN** the recompression attempt SHALL fail closed before publication

#### Scenario: Encoder timeout
- **WHEN** the worker exceeds its operation deadline
- **THEN** the timed-out worker SHALL be stopped and private intermediates cleaned up
- **AND** only an independently verified ordinary compaction result can be used

#### Scenario: Optional encoder is unavailable
- **WHEN** the optional stronger encoder is unavailable
- **THEN** the bounded zlib baseline SHALL remain available
- **AND** its candidate SHALL pass the same preservation and acceptance checks

#### Scenario: Helper lacks stream replacement capability
- **WHEN** the configured native helper supports only ordinary compaction
- **THEN** the system SHALL NOT treat it as a stream replacement backend
- **AND** an eligible strict compaction fallback can retain existing behavior

### Requirement: Transaction and physical-savings acceptance

The system SHALL use existing source staging, verification, dry-run, destination,
backup, filesystem-metadata and minimum-savings policies for the final file.
It SHALL compare against a verified ordinary compaction baseline and prefer that
baseline if changed records provide no full-file size improvement. Reports SHALL
distinguish actual strategy and measured physical savings from stream-byte savings.

#### Scenario: Stream savings do not cross a sector boundary
- **WHEN** re-encoding reduces a stream but does not improve final size over compaction
- **THEN** the system SHALL prefer the verified ordinary compaction candidate
- **AND** it SHALL NOT claim additional physical savings from those record changes

#### Scenario: Dry-run verifies a smaller result
- **WHEN** dry-run is enabled and a qualified candidate is smaller
- **THEN** source and user-visible destination SHALL remain unchanged
- **AND** private candidates SHALL be removed after verification and reporting

### Requirement: Notes-aware immutable PPT host graph

The system SHALL qualify a single-edit PPT host independently of its selected
payload codec through complete typed persist and live-object accounting. When
notes are present, it SHALL validate NotesContainer/NotesAtom headers and children,
NotesListWithText instance 2, unique notes/slide IDs, bidirectional slide-to-notes
links and the notes master referenced by DocumentAtom. It SHALL preserve every
notes byte and logical identifier. The initial extended profile SHALL admit only
audited record versions, owner roles and programmable-tag forms, and SHALL retain
existing protection, ambiguity and resource rejection. Embedded DOC/XLS
recompression SHALL retain its separate strict payload-selection contract.

#### Scenario: Presentation contains ordinary notes and a notes master
- **WHEN** a qualified single-edit presentation contains fully accounted notes pages
  and a uniquely referenced notes master
- **THEN** the host graph SHALL identify their roles and validate both directions of
  every ordinary slide/notes link
- **AND** notes data SHALL remain byte-identical during selected payload recompression

#### Scenario: Audited old notes-master field variant
- **WHEN** the uniquely referenced notes master has the independently qualified old
  `(slideIdRef, slideFlags)` pair `(0x80000000, 2)`
- **THEN** this pair SHALL be accepted only for that master role and preserved exactly
- **AND** it SHALL NOT authorize arbitrary nonzero master fields or dangling ordinary
  notes-slide references

#### Scenario: Notes reference is missing or ambiguous
- **WHEN** a notes ID is duplicated, targets the wrong object kind, resolves to a
  different slide, or leaves an unreferenced notes container
- **THEN** the extended host profile SHALL be rejected before writing a candidate

#### Scenario: Record or extension is outside the audited profile
- **WHEN** a host contains an unqualified record version, owner role or programmable
  extension form
- **THEN** the extended qualification SHALL fail closed
- **AND** immutable-prefix reasoning SHALL NOT silently admit that unknown form

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
