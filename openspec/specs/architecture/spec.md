# architecture

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Typed Result Structures
Public file packers SHALL return PackResult or None and FileRepacker SHALL return RepackSummary. Versioned terminal outcomes SHALL use RepackOutcome; documented legacy mapping adapters SHALL remain available.

#### Scenario: Verified current contract
- **WHEN** A public packer returns
- **THEN** the caller accesses named size, replacement and reason fields

### Requirement: Dataclass Definitions
PackResult, RepackOptions and RepackSummary SHALL be defined in models.py; RepackOutcome SHALL be defined in outcomes.py. These public dataclasses SHALL be exported at the package root.

#### Scenario: Verified current contract
- **WHEN** a caller imports public result classes
- **THEN** the classes are available with annotated fields

### Requirement: DRY Principle
Shared candidate verification, savings acceptance, source snapshots and destination publication SHALL be implemented in dedicated helpers. Dispatch SHALL use the central registered packer views.

#### Scenario: Verified current contract
- **WHEN** a format candidate is accepted
- **THEN** publication follows the shared transaction boundary

### Requirement: Dead Code Removal
Configured Ruff checks SHALL reject unused imports and variables. Compatibility re-exports and methods with the same name in separate modules/classes SHALL remain valid.

#### Scenario: Verified current contract
- **WHEN** unused imports are introduced in runtime code
- **THEN** Ruff reports them

### Requirement: Code Compactness
The main `repack.py` module SHALL be under 1,200 lines of code by extracting reusable patterns.

#### Scenario: Line count check
- **WHEN** counting lines in `repack.py`
- **THEN** the total is less than 1,200 lines
- **AND** no behavioral functionality has been removed
