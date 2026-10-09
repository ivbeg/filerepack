# concurrency

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Process-Invariant Working Directory
File processing SHALL not change the parent process working directory. External tools SHALL receive an explicit cwd when operating inside owned staging.

#### Scenario: Verified current contract
- **WHEN** concurrent jobs use different staging directories
- **THEN** the parent cwd remains unchanged

### Requirement: Absolute Path Usage
Root source, output and owned temporary paths SHALL be normalized to absolute paths. Archive-member arguments MAY be relative to an explicit owned staging cwd.

#### Scenario: Verified current contract
- **WHEN** a relative source path is supplied
- **THEN** publication uses its normalized absolute identity
