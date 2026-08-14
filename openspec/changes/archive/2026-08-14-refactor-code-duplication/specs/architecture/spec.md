## ADDED Requirements
### Requirement: DRY Principle
Common patterns SHALL be extracted into reusable helper functions rather than duplicated across multiple packers.

#### Scenario: Single packer invocation
- **WHEN** a packer function is called
- **THEN** it delegates size tracking, dryrun handling, and OS-specific redirection to shared helpers
- **AND** the packer function contains only format-specific logic

#### Scenario: Extension dispatch
- **WHEN** a file extension needs to be mapped to its packer function
- **THEN** `_dispatch_packer(ext, filepath)` is called
- **AND** no duplicate if/elif chains exist for format dispatch

### Requirement: Dead Code Removal
Unused or duplicate code SHALL be removed to maintain a clean codebase.

#### Scenario: No duplicate function definitions
- **WHEN** searching for function definitions
- **THEN** no function name appears more than once as a definition

#### Scenario: No unused imports
- **WHEN** reviewing imports
- **THEN** every imported module is referenced in the code

#### Scenario: No unused variables
- **WHEN** reviewing assignments
- **THEN** every assigned variable is read later in the code path

### Requirement: Code Compactness
The main `repack.py` module SHALL be under 1,200 lines of code by extracting reusable patterns.

#### Scenario: Line count check
- **WHEN** counting lines in `repack.py`
- **THEN** the total is less than 1,200 lines
- **AND** no behavioral functionality has been removed
