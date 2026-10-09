## MODIFIED Requirements

### Requirement: Read Only Inspection Command

The system SHALL provide file and directory inspection through `filerepack inspect PATH --json` and a typed library entry point. Inspection SHALL perform bounded read-only probes without encoding candidates, extracting complete payloads, or creating output, backup, or scratch files.

#### Scenario: File inspection leaves the filesystem intact

- **WHEN** a supported archive is inspected with JSON output
- **THEN** the response describes the format and planned operations without invoking any encoder
- **AND** source bytes and existing destinations remain unchanged and no processing files are created

#### Scenario: Directory inspection is bounded

- **WHEN** a large directory or expensive header is inspected
- **THEN** discovery, probe output, and probe duration remain within configured limits
- **AND** an incomplete probe is identified explicitly rather than performed without a limit

### Requirement: Capability and Eligibility Planning

Inspection SHALL apply the same detection, tool/extras, preservation, resource, and destination policies as execution. It SHALL report available operations, missing prerequisites, known protection, unknown protection, and destination conflicts; an unknown protection result SHALL NOT be represented as permission to rewrite.

#### Scenario: Known and unknown protection are distinct

- **WHEN** one input has a known signature and another cannot be fully checked by bounded probes
- **THEN** the first record declares a protection blocker and the second declares protection unknown

#### Scenario: Unavailable writer or occupied target

- **WHEN** an alias lacks a proven writer or its requested output already exists
- **THEN** the inspection record explains the corresponding blocker using shared capability and destination policy

### Requirement: Estimated and Measured Information Separation

Inspection SHALL label resource values as estimates with their provenance and unknown values as unknown. It SHALL NOT advertise compression savings as measured without encoding. Existing dry-run SHALL remain the operation for measuring actual candidate savings.

#### Scenario: Header provides a size estimate

- **WHEN** an archive listing advertises uncompressed size
- **THEN** inspection labels the value as a listing estimate and does not report measured savings

#### Scenario: Execution follows a plan

- **WHEN** a user executes a previously inspected operation after the source or destination has changed
- **THEN** execution revalidates current state and does not rely on the earlier plan as authorization or proof of safety
