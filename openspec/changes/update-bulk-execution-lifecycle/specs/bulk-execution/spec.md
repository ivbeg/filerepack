## MODIFIED Requirements

### Requirement: Bounded Bulk Discovery and Scheduling

Bulk discovery SHALL be incremental and in-flight submissions SHALL remain within a documented bounded multiple of configured workers, default two. Resolved output/backup trees SHALL be excluded from discovery, and each known input SHALL be scheduled at most once.

#### Scenario: Large directory

- **WHEN** a directory contains more inputs than the in-flight capacity
- **THEN** the runner SHALL apply backpressure instead of submitting/materializing the entire batch

#### Scenario: Output inside input tree

- **WHEN** an existing output or backup directory lies below the input root
- **THEN** its files SHALL not be rediscovered as inputs

### Requirement: Coordinator Owned Destination Reservations

The bulk coordinator SHALL reserve effective output/conversion/backup identities before dispatch. Conflicting jobs SHALL receive explicit conflict outcomes rather than concurrent writes or overwritten backups.

#### Scenario: Two conversions share target

- **WHEN** movie.avi and movie.wmv would both publish movie.mp4
- **THEN** the coordinator SHALL prevent competing publication and report the conflict

### Requirement: Accounted Fail Fast and Cancellation

Fail-fast or interruption SHALL stop discovery/submission, cancel pending work, coordinate running work, and consume/report all known terminal results before returning. Running work SHALL NOT remain an unreported background mutator. Reports SHALL distinguish incomplete discovery from known cancelled inputs.

#### Scenario: First job fails

- **WHEN** fail-fast mode observes a failure with queued and running jobs
- **THEN** new submissions SHALL stop and all known results/cancellations SHALL be accounted for

#### Scenario: Encoder active during interrupt

- **WHEN** the user interrupts while a worker owns an encoder or candidate
- **THEN** the worker SHALL release process/publication ownership and report its actual terminal outcome
