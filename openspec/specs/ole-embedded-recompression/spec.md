# ole-embedded-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Explicit embedded payload optimization mode
The system SHALL offer default-false ole_embedded_recompress and its CLI
equivalent for qualified DOC/XLS objects. Existing ole_recompress behavior and
the exact decoded-storage PPT contract SHALL remain independent. Embedded work
SHALL use only explicitly qualified lossless child contracts.

#### Scenario: Existing caller enables OfficeArt only
- **WHEN** ole_recompress is true and ole_embedded_recompress is false
- **THEN** embedded child bytes are not optimized by this new capability.

#### Scenario: Mode reaches an archive member
- **WHEN** the new option is enabled for a qualified DOC/XLS member inside an archive
- **THEN** the member receives the same option/protection/verification policies and shares the root budget.

### Requirement: Authoritative embedded object discovery
The system SHALL resolve host object/class records, wrapper boundaries and every
affected reference before rewriting a child. It SHALL distinguish serialized
files, serialized CFB and direct substorages from links, VBA and controls. It
SHALL NOT execute objects or use opaque signature carving.

#### Scenario: Ordinary embedded file and an ActiveX object coexist
- **WHEN** a qualified parent contains an allowed file object beside a control
- **THEN** the file is considered only through its qualified profile
- **AND** the control and all unrelated content remain exact.

#### Scenario: Object target is ambiguous
- **WHEN** a host ID or wrapper boundary cannot be resolved unambiguously
- **THEN** the parent content candidate is declined with a reason and strict compaction remains available when eligible.

### Requirement: Wrapper and substorage identity preservation
The system SHALL preserve all non-payload wrapper fields, suffixes, names, class
information, presentation caches and display properties except declared size
or reference repairs. Direct substorages SHALL retain complete hierarchy and
logical metadata; a synthetic child root SHALL NOT overwrite parent metadata.

#### Scenario: Child shrink changes a wrapper length
- **WHEN** a verified embedded file becomes smaller
- **THEN** only its payload and proven length/reference fields change and retained wrapper/presentation bytes match.

#### Scenario: Child writer loses a storage timestamp
- **WHEN** a reconstructed direct substorage changes a name, CLSID, state bit or timestamp
- **THEN** verification rejects the parent candidate.

### Requirement: Independent recursive intended-change verification
The system SHALL independently parse source/candidate parent graphs, verify each
changed child's complete preservation contract and compare every unaffected
byte/metadata item and normalized object target. Combined transformations SHALL
require complete union verification without weakening strict OLE or PPT checks.

#### Scenario: Child passes a structural check but changes content
- **WHEN** a nested candidate is well formed but violates its declared lossless contract
- **THEN** the parent candidate is rejected before publication.

#### Scenario: Composed candidate has an unaccounted pointer patch
- **WHEN** nested and OfficeArt changes are individually valid but their parent relocation contains an undeclared or wrong-target patch
- **THEN** union verification rejects the combined candidate.

### Requirement: Shared recursive execution and parent savings
The system SHALL enforce root cumulative depth/member/decoded-byte/memory/scratch
and lifetime bounds across child processing and verification. It SHALL preserve
unsupported/protected children exactly, abort publication on exhausted budgets
or cancellation, and apply existing transactions to final parent-file savings.
It SHALL honor effective parent category/member restrictions without enabling
disabled descendant packers.

#### Scenario: Several individually small children exceed the root limit
- **WHEN** cumulative processing exceeds the root budget
- **THEN** operation-owned work stops, scratch is cleaned and the parent source is preserved.

#### Scenario: Child saves bytes but parent allocation does not shrink
- **WHEN** a verified child improvement produces no smaller verified parent file
- **THEN** the existing smallest parent baseline is retained and diagnostics report the allocation outcome.
