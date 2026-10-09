## MODIFIED Requirements

### Requirement: Audited extension routing
The system SHALL recognize Mellel, SQLite aliases, DuckDB, SWF, TGS and the
audited JSON/XML aliases, retaining extensions and canonical extension filters.

#### Scenario: Misleading map extension
- **WHEN** a `.map` file is not valid JSON
- **THEN** it remains unchanged

#### Scenario: Protected Mellel package
- **WHEN** a supported Mellel ZIP package is optimized
- **THEN** every decoded member and required document control remains identical

### Requirement: Verified offline databases
The system SHALL publish new SQLite alias and DuckDB candidates only when
bounded read-only verification proves the supported schema and values unchanged.

#### Scenario: Pending transaction
- **WHEN** a database has transaction sidecars
- **THEN** optimization is skipped without opening it for writes

#### Scenario: Unsupported database objects
- **WHEN** DuckDB contains objects or types outside the verified subset
- **THEN** it remains unchanged

### Requirement: Preserving animation compression
The system SHALL validate bounded SWF and TGS payloads and compare their exact
decoded bytes before publication, without running embedded scripts.

#### Scenario: Candidate changes animation
- **WHEN** a candidate has different decoded animation bytes
- **THEN** it is refused and the source remains unchanged

#### Scenario: Dry run or insufficient savings
- **WHEN** a valid candidate is previewed or does not meet savings acceptance
- **THEN** the original is preserved and temporary artifacts are cleaned
