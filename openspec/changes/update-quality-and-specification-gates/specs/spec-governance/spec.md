## ADDED Requirements

### Requirement: Verified Canonical Specification Baseline

Canonical specifications SHALL describe verified current contracts, with known implementation gaps recorded explicitly rather than future proposals declared implemented. Existing completed/archived change requirements SHALL be audited for accuracy and overlap; MODIFIED deltas SHALL be rebased to the reconciled named baseline before archiving.

#### Scenario: Absent canonical specs

- **WHEN** completed changes exist but openspec/specs is empty
- **THEN** reconciliation SHALL establish verified baseline requirements and record unmet promises separately

#### Scenario: Replacement baseline differs

- **WHEN** a new MODIFIED requirement was based on a historical completed change
- **THEN** it SHALL be checked/rebased against the reconciled canonical requirement before archive

### Requirement: Current Guidance and Deployment Aware Archival

Project and contributor guidance SHALL match the current architecture/testing/support conventions. Existing completed changes SHALL be archived only after deployment status is confirmed, and archival SHALL preserve history and update affected canonical specs.

#### Scenario: Completed checklist without deployment evidence

- **WHEN** an existing change has all tasks checked but deployment status is unknown
- **THEN** it SHALL not be marked deployed or archived solely from that checklist

#### Scenario: Guidance refresh

- **WHEN** architecture or test conventions are reconciled
- **THEN** project guidance SHALL no longer claim there are no tests or only the former monolithic design
