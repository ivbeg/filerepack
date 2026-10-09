## ADDED Requirements

### Requirement: Shared Root Input Resource Context

Every root input SHALL have a shared context governing cumulative decoded bytes, member count, nesting depth, and deadline across all descendants and verification stages. Nested work SHALL NOT reset those counters. Bulk execution SHALL additionally reserve concurrent scratch/memory/CPU resources across workers.

#### Scenario: Nested archive budget

- **WHEN** a nested archive would make its root input exceed a cumulative limit
- **THEN** processing SHALL stop with a budget reason and preserve the root source

#### Scenario: Parallel scratch pressure

- **WHEN** workers compete for the configured live scratch budget
- **THEN** the coordinator SHALL apply backpressure or decline work rather than independently grant every worker the full shared quota

### Requirement: Bounded Decoding and Process Lifetime

Standalone streams, PSD payloads, asset extraction, archive extraction, and validators SHALL obey enforced output and lifetime limits, not only listed estimates. Stream peeking and subprocess I/O SHALL have deadlines and bounded diagnostic capture. Exceeded limits SHALL terminate operation-owned work and prevent publication, with documented monitoring granularity for external writers.

#### Scenario: Stalled peek or standalone decoder

- **WHEN** a decoder stalls before 512 peek bytes or emits output beyond policy
- **THEN** the process SHALL be stopped with a timeout/budget outcome and no source publication

#### Scenario: Misreported extracted size

- **WHEN** actual extraction exceeds its advertised size and configured limit
- **THEN** monitoring SHALL stop work and preserve the source rather than trust preflight alone

### Requirement: Extraction Path and Link Containment

Extraction SHALL validate normalized paths, member identities, and link targets before permitting writes into staging. Escaping paths/links and unsupported duplicate or case-colliding identities SHALL be rejected. Containment validation SHALL not assume the selected external archiver enforces all application policies.

#### Scenario: Escaping member or link

- **WHEN** an archive member or link resolves outside allowed staging
- **THEN** the operation SHALL reject extraction and retain original bytes

### Requirement: Explicit Extraction Limit Compatibility

Existing default extraction byte/ratio limits and the explicit zero-disable setting SHALL translate consistently into the documented shared policy. Additional depth/member/deadline settings SHALL have documented defaults and deterministic CLI/library validation.

#### Scenario: Explicit legacy disable

- **WHEN** max-extract-size zero is requested
- **THEN** the legacy byte/ratio caps SHALL be disabled while independently configured depth/member/deadline policies remain explicit
