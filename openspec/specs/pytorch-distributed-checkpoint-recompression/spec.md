# pytorch-distributed-checkpoint-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

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
