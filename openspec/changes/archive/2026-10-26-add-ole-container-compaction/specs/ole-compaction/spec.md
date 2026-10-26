## MODIFIED Requirements

### Requirement: Qualified CFB Office Detection

The system SHALL recognize initial CFB version-3 Office 97–2003 profiles using
both a qualified extension and validated document structures. The initial
extension sets SHALL be DOC/DOT, BIFF8 XLS/XLT/XLA and PPT/POT/PPS. A CFB signature
or Office extension alone SHALL NOT authorize rewriting. Other CFB applications,
version 4, incompatible legacy Office versions and opaque binary members SHALL
remain unsupported until separately qualified.

#### Scenario: Supported legacy document

- **WHEN** a version-3 DOC file has a valid qualified WordDocument/table-stream profile
- **THEN** the system SHALL evaluate it for container compaction using the same policy as its DOT alias

#### Scenario: Office suffix with a different format

- **WHEN** an XLS-suffixed input contains HTML, XML, raw BIFF or an unqualified CFB profile
- **THEN** the system SHALL leave it unchanged and explain why OLE compaction is unavailable

#### Scenario: Generic or unsupported CFB

- **WHEN** an input is a valid MSI or version-4 CFB file without a qualified profile
- **THEN** the system SHALL NOT invoke a generic CFB rewrite fallback

### Requirement: Complete OLE Eligibility Gate

Before encoding, the system SHALL establish encryption, document/VBA signature
and rights-management status using the qualified Office profile and relevant
container structures. Known protection or uncertainty SHALL prevent compaction.
Unsigned VBA SHALL be retained opaquely only when its profile's protection gate
is qualified. No inspection or compaction SHALL execute macros or OLE objects.

#### Scenario: Legacy encryption inside a document stream

- **WHEN** DOC FIB flags, XLS FilePass or PPT encryption references indicate protection
- **THEN** the whole input SHALL be skipped before candidate writing

#### Scenario: Signed or rights-managed document

- **WHEN** document/VBA signatures or rights-management structures are present
- **THEN** the source SHALL remain unchanged with a protection reason

#### Scenario: Incomplete protection inspection

- **WHEN** the bounded parser cannot establish protection status or encounters an unsupported protection variant
- **THEN** the system SHALL report uncertainty and SHALL NOT assume the file is unprotected

#### Scenario: VBA signature stored in host records

- **WHEN** a DOC StwUser contains Sign, SigAgile or SigV3, or a DocumentSummaryInformation set contains GKPIDDSI_DIGSIG
- **THEN** the source SHALL be skipped even when no stream name indicates a signature

#### Scenario: Qualified unsigned DOC or XLS project

- **WHEN** a canonical root DOC Macros or XLS _VBA_PROJECT_CUR project has the required opaque streams and a complete unsigned host-signature inspection
- **THEN** container compaction MAY retain that entire project byte-for-byte
- **AND** unknown, embedded or incomplete DOC/XLS VBA layouts SHALL remain unsupported

#### Scenario: Qualified unsigned PPT project

- **WHEN** a single-edit PPT/POT/PPS has one canonical VBAInfoContainer under its current document's DocInfoList, referencing a top-level recognized VBA project storage
- **THEN** the bounded decoder and independent nested-CFB reader SHALL qualify that project and its host-signature status before compaction
- **AND** the original encoded storage and every outer application stream SHALL remain byte-for-byte unchanged
- **AND** ambiguous/history-dependent references, unknown/empty project variants, malformed wrappers and decompression-budget violations SHALL prevent compaction

### Requirement: Stream-Preserving Container Compaction

For eligible inputs, the system SHALL compact CFB allocation structures while
preserving the complete logical storage hierarchy, exact names and types, empty
objects, every live stream's length and bytes, and relevant directory metadata
including CLSIDs, state bits and recorded FILETIME values. The input CFB version
SHALL be retained. Unknown live streams SHALL be copied without interpretation.
Observed nonzero root creation FILETIMEs in otherwise qualified inputs SHALL be
retained exactly, without timestamp normalization; both root FILETIMEs SHALL
remain subject to independent metadata and candidate preservation comparisons.
The operation SHALL NOT remove history inside live streams, recompress VBA or
application records, convert to another Office format or introduce compressed
stream bytes that the application format does not define.
Only the observed slot-zero service-name anomaly (UTF-16 `R`, zero padding,
declared length 2, object type 5) MAY normalize to `Root Entry`/length 22 in private
reader/writer views. This exception SHALL NOT change any application object name,
metadata, link or allocation field, or bypass protection and publication policies.

#### Scenario: Reclaimable allocation space

- **WHEN** a valid source has free regular or mini sectors beyond its logical content needs
- **THEN** a candidate MAY use a smaller allocation layout while retaining identical logical objects and stream bytes

#### Scenario: Unfamiliar and empty objects

- **WHEN** a source contains unfamiliar streams, empty storages, property sets or qualified unsigned VBA
- **THEN** all these objects and their relevant metadata SHALL remain present and unchanged

#### Scenario: Application history within live streams

- **WHEN** a PPT contains obsolete records within its live PowerPoint Document stream
- **THEN** container compaction SHALL retain that stream byte-for-byte

#### Scenario: Mini stream relocation

- **WHEN** the physical root mini-stream carrier is repacked
- **THEN** preservation SHALL compare its contained logical streams while allowing the carrier's physical layout and size to change

#### Scenario: Observed legacy root service name

- **WHEN** an otherwise qualified source has the exact slot-zero root-name anomaly
- **THEN** strict and independent readers and the native writer SHALL use the same canonical root view
- **AND** every live stream and all other logical metadata SHALL remain exact
- **AND** dry-run or an equal-size candidate SHALL leave the source bytes unchanged

#### Scenario: Recorded root creation timestamp

- **WHEN** an otherwise qualified legacy Office source records a nonzero root creation FILETIME
- **THEN** compaction SHALL preserve its exact creation and modification FILETIMEs
- **AND** a candidate changing either timestamp SHALL be rejected
- **AND** dry-run or an equal-size candidate SHALL leave the source bytes unchanged

### Requirement: Independent Structural and Preservation Validation

The system SHALL validate complete source and candidate allocation/directory
graphs and compare their full logical manifests through an independent reader
before publication. Validation SHALL reject cycles, overlaps, truncated chains,
invalid references, unreachable allocated objects, unexplained allocation and
incomplete object enumeration. A writer's success status or successful reopening
alone SHALL NOT prove preservation. Missing validators, differing stream
hashes/lengths, hierarchy/metadata mutations or reader disagreement SHALL prevent
publication. Required Office profile structures SHALL remain valid.

#### Scenario: Smaller but altered candidate

- **WHEN** a candidate is structurally readable but changes a stream byte, CLSID, timestamp or empty storage
- **THEN** the candidate SHALL be rejected and the original SHALL remain unchanged

#### Scenario: Partial parser view

- **WHEN** a directory graph contains an allocated object omitted by normal tree traversal
- **THEN** the source SHALL be rejected as ambiguous rather than compacted from a partial manifest

#### Scenario: Independent validation unavailable

- **WHEN** the complete independent validator is missing or disagrees with the writer's object view
- **THEN** the candidate SHALL NOT be published

#### Scenario: Unicode full-uppercase expansion

- **WHEN** a BMP directory name contains `ß` or a Greek character whose full uppercase expands
- **THEN** ordering and duplicate detection SHALL use original UTF-16 length and pinned simple uppercase per code unit
- **AND** names SHALL be preserved without full-uppercase expansion or Unicode normalization
- **AND** malformed ordinary names, duplicate comparison keys and invalid directory graphs SHALL remain rejected

### Requirement: Shared OLE Execution and Reporting Contract

OLE compaction SHALL use private staging and the existing shared transaction,
size/minimum-savings, dry-run, filesystem-preservation and nested archive-manifest
contracts. Source reads, entries, nesting, stream bytes, scratch use and helper
duration SHALL be bounded. Missing optional writers or exhausted limits SHALL
produce an explicit reason without modifying the source. Inspection estimates
SHALL be distinguished from measured candidate savings. Under the default size
policy, equal or larger outputs SHALL leave the source unchanged.

#### Scenario: Compaction provides no savings

- **WHEN** an eligible compact input produces an equal-size candidate under the default size policy
- **THEN** the operation SHALL report no accepted reduction and retain the source

#### Scenario: Verbose and structured diagnostics

- **WHEN** an OLE file is unchanged because a dependency is missing, its profile
  is unsupported/protected, verification fails or the candidate is rejected by size policy
- **THEN** its result SHALL retain the corresponding reason for CLI/library/JSON/bulk use
- **AND** verbose text output SHALL show that reason and the actual strategy even
  when a log file is enabled
- **AND** no-size-reduction DOC/XLS results SHALL explain that only container
  allocation space is compacted, with live application streams retained

#### Scenario: Dry-run or interrupted writer

- **WHEN** compaction is run in dry-run mode or its helper is interrupted
- **THEN** the original SHALL remain unchanged and owned staging files SHALL be cleaned up

#### Scenario: Qualified Office file inside an archive

- **WHEN** an archive member has a qualified DOC/XLS/PPT extension and profile
- **THEN** it SHALL use the same OLE eligibility and preservation rules, and the outer archive SHALL validate its intended member manifest

#### Scenario: Resource limit or missing writer

- **WHEN** a configured limit is exceeded or the qualified optional backend is unavailable
- **THEN** the operation SHALL report the corresponding reason without an unchecked fallback
