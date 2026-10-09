## MODIFIED Requirements

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
