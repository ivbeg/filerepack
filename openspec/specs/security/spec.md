# security

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Safe Command Execution
External tools SHALL receive argv lists through subprocess adapters without a shell. User-controlled filenames SHALL remain literal arguments. Owned long-running processes SHALL use the shared supervision helpers.

#### Scenario: Verified current contract
- **WHEN** a filename contains shell metacharacters
- **THEN** the tool receives a literal filename and no shell command is interpreted

### Requirement: Command Execution Helper
commands.py SHALL centralize argv execution, bounded capture and decoder consumption. Compatibility helper imports SHALL remain available and failed commands SHALL provide failure outcomes.

#### Scenario: Verified current contract
- **WHEN** an encoder exits unsuccessfully
- **THEN** its candidate does not authorize publication

### Requirement: Path Validation
Request validation SHALL reject NUL-containing paths before writes. Other legal platform filenames SHALL be passed literally through argv, with archive-specific identity and containment checks.

#### Scenario: Verified current contract
- **WHEN** a request path contains NUL
- **THEN** validation rejects it before a writer starts
