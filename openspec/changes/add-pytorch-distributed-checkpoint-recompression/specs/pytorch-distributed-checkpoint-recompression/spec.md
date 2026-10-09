## MODIFIED Requirements

### Requirement: DCP is handled as a complete checkpoint set
The system SHALL model a supported PyTorch Distributed Checkpoint as one
logical directory/store containing its required metadata and all referenced
shards. It SHALL NOT advertise or route an individual `.distcp` shard as a
standalone DCP recompression target.

#### Scenario: A shard is submitted without its checkpoint metadata
- **WHEN** a `.distcp` file is presented without a complete recognized DCP set
- **THEN** it SHALL remain unchanged and SHALL not enter a generic compression handler

### Requirement: Passive and bounded checkpoint inspection
The system SHALL inspect checkpoint structure within shared resource limits
without unpickling arbitrary state, invoking checkpoint-provided globals, or
executing model code.

#### Scenario: A metadata object contains an executable pickle global
- **WHEN** the checkpoint is inspected or compared
- **THEN** the object SHALL be treated as untrusted data and SHALL never be invoked

## ADDED Requirements

### Requirement: Feasibility-gated DCP writer registration
The system SHALL register a DCP writer only after complete real checkpoint sets
from independent projects demonstrate accepted same-format savings and pass
qualified native DCP load and reshard checks. If the corpus or a profile fails
these gates, the system SHALL retain inspection-only behavior and SHALL NOT
advertise a writer.

#### Scenario: Current samples do not establish a complete checkpoint
- **WHEN** inventory cannot prove all required metadata and shards are present
- **THEN** the set SHALL remain unchanged and SHALL not qualify a writer

### Requirement: Exact DCP state and shard preservation
Any accepted rewrite SHALL preserve checkpoint metadata, stored state bytes,
rank/shard identity, and the qualified topology/reshard contract. It SHALL NOT
repartition, rename, drop, or independently rewrite shards unless that exact
whole-set profile passes native validation.

#### Scenario: A candidate omits one shard
- **WHEN** complete inventory comparison detects a missing or changed shard
- **THEN** the candidate set SHALL be rejected and SHALL NOT be published

### Requirement: Atomic whole-directory DCP publication
The system SHALL stage, validate, and publish a DCP result as one directory
transaction. Failures, resource exhaustion, cancellation, or publication errors
SHALL preserve the source set and any prior destination.

#### Scenario: DCP reshard validation fails
- **WHEN** a required native DCP load or reshard check fails
- **THEN** no part of the candidate checkpoint SHALL be published
