## ADDED Requirements

### Requirement: Preservation Oriented Writer Evidence

Every advertised safe writer SHALL have a round-trip preservation fixture for its declared backend/platform or an explicit unavailable/experimental label. Tests SHALL check logical/member/pixel/schema contracts, not merely command flags, headers, or non-None results.

#### Scenario: Advertised writer without fixture

- **WHEN** a support table claims safe rewrite for a format/backend
- **THEN** release readiness SHALL require its preservation evidence or downgrade the claim

### Requirement: Explicit Integration Availability and Platform Coverage

CI SHALL exercise supported core Python versions, representative macOS/Windows/Linux process/filesystem behavior, optional data/fonts/media/pdf/progress integrations, and installed artifacts. Missing optional integrations SHALL skip explicitly with reasons; required provisioned integrations that do not work SHALL fail.

#### Scenario: Integration unavailable

- **WHEN** an optional tool is absent in an intentionally minimal lane
- **THEN** the test SHALL be explicitly skipped with an availability reason

#### Scenario: Provisioned integration broken

- **WHEN** a required tool/extra exists in its designated lane but its round-trip fails
- **THEN** the lane SHALL fail rather than return early as a pass

### Requirement: Measured Coverage and Performance Gates

Quality gates SHALL preserve regression and fault/property assertions while ratcheting coverage from the reviewed baseline toward the documented target. A fixed representative corpus SHALL record tool versions, elapsed time, peak memory, scratch use, acceptance rate, and actual final savings separately from inner candidate savings.

#### Scenario: Coverage passes but preservation fails

- **WHEN** a change passes numeric coverage but loses an intended member or value
- **THEN** quality gates SHALL still fail

#### Scenario: Benchmark comparison

- **WHEN** an optimization profile or writer change is benchmarked
- **THEN** results SHALL use the same versioned corpus and report resource/fidelity metrics alongside savings
