# optimization-profiles

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Versioned Named Optimization Profiles

The system SHALL provide `fast`, `balanced`, `maximum`, and `preserve` optimization profiles with documented versioned definitions. Version 1 SHALL set compression level/ultra to 3/false, 6/false, 9/true, and 6/false respectively; preserve SHALL additionally request metadata retention. Selecting a profile alone SHALL NOT enable any lossy encoder or quality policy.

#### Scenario: Profile does not authorize loss

- **WHEN** a user selects maximum without an explicit lossy/quality request
- **THEN** higher supported lossless effort is selected while media/PDF fidelity rules remain lossless

#### Scenario: Preserve profile requires metadata

- **WHEN** preserve selects a writer unable to retain requested metadata
- **THEN** the adapter reports its limitation and skips rather than silently discarding metadata

#### Scenario: Unprofiled caller remains compatible

- **WHEN** a caller supplies existing RepackOptions without a profile
- **THEN** the existing effort defaults and explicit options are retained

### Requirement: Deterministic Explicit Option Precedence

Option resolution SHALL apply baseline defaults, selected profile values, and explicitly supplied CLI/library overrides in that order and SHALL validate the final result before writes. The system SHALL distinguish explicit overrides from parser/dataclass defaults and expose profile version plus effective options to outcome and available planning/report/resume consumers.

#### Scenario: Explicit default-valued override wins

- **WHEN** maximum is selected with compression level explicitly set to 6 or ultra explicitly disabled
- **THEN** the explicit override wins and is reflected in effective settings

#### Scenario: Implicit CLI default does not win

- **WHEN** fast is selected without an explicit compression level
- **THEN** the profile level 3 is retained despite the unprofiled parser default

#### Scenario: Definition version changes

- **WHEN** a profile definition or effort mapping changes
- **THEN** its version changes and execution fingerprints cannot reuse the previous definition silently
