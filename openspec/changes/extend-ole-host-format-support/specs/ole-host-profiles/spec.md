## ADDED Requirements

### Requirement: Qualified additional CFB host profiles
The system SHALL introduce individually qualified CFB v3 profiles for MSG, VSD,
PUB, MPP, MSI and HWP 5. Each enabled profile SHALL recognize actual host
structures/versions and state its exact feature boundaries. Extension matching
alone SHALL NOT establish eligibility, and unqualified host/version variants
SHALL remain explicit skips.

#### Scenario: Qualified MSG or HWP file
- **WHEN** a routed input satisfies an enabled host's complete structural/version profile
- **THEN** it can use strict container compaction under that profile's gates.

#### Scenario: MSI suffix on an arbitrary CFB
- **WHEN** an input's suffix matches but its database/host structures do not
- **THEN** no new profile is accepted and the source remains unchanged with a reason.

### Requirement: Host-specific protection and writer eligibility
Each profile SHALL completely audit its relevant protection/signature scopes and
the native/independent CFB naming/metadata capabilities. Incomplete or unsupported
inspection SHALL decline compaction. Preserved embedded authenticated bytes SHALL
be distinguished from authenticated container representation; no signature or
protection field SHALL be removed or guessed safe.

#### Scenario: Installer encoded names or signature scope are unqualified
- **WHEN** the MSI input uses an unsupported name variant or incompletely audited signature layout
- **THEN** it is skipped without relaxing shared CFB checks.

#### Scenario: Embedded signed attachment remains opaque
- **WHEN** an enabled MSG profile proves that embedded authenticated bytes and references are unchanged by strict compaction
- **THEN** those bytes remain exact without execution or signature rewriting.

### Requirement: Identical streams and complete metadata across new hosts
Every additional host compaction candidate SHALL preserve all live stream bytes,
storages, empty objects, hierarchy, names, CLSIDs, state bits and timestamps.
The system SHALL independently compare complete manifests and validate the same
host profile before publication; application readers alone SHALL NOT prove this.

#### Scenario: HWP or MSI contains compressed streams
- **WHEN** strict compaction is applied to a qualified file
- **THEN** encoded document/CAB bytes remain identical even if allocation changes.

#### Scenario: Reader opens a candidate with a missing private stream
- **WHEN** an application reader accepts a candidate whose complete manifest differs
- **THEN** strict verification rejects it before publication.

### Requirement: Compatible execution and per-host evidence
New hosts SHALL use existing source/output/backup/dry-run/threshold, archive,
resource and diagnostic contracts. Each enabled host SHALL publish pinned real
fixture provenance, qualified versions, protection skips, independent/native
evidence and application/platform limits. Original savings SHALL be separated
from controlled allocation-hole opportunities.

#### Scenario: No reclaimable allocation
- **WHEN** a qualified file has no smaller verified compaction result
- **THEN** it remains unchanged and diagnostics distinguish no savings from unsupported input.

#### Scenario: New host inside a selected archive member
- **WHEN** archive processing selects a member satisfying an enabled profile
- **THEN** identical host gates and strict verification apply under the archive's root budget and member manifest.
