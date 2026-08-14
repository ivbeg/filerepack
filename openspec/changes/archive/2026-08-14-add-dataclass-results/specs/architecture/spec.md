## ADDED Requirements
### Requirement: Typed Result Structures
The system SHALL use dataclasses for all function return values instead of raw lists or dictionaries.

#### Scenario: PackResult
- **WHEN** a `pack_*()` function completes processing a file
- **THEN** it returns a `PackResult(filepath, insize, outsize, savings_pct)` instance
- **AND** callers access fields by name (e.g., `result.filepath`) not by index

#### Scenario: RepackSummary
- **WHEN** `repack_zip_file()` completes processing an archive
- **THEN** it returns a `RepackSummary` containing a list of `PackResult` entries
- **AND** the summary includes aggregate totals and elapsed time

### Requirement: Dataclass Definitions
All result dataclasses SHALL be defined in `filerepack/models.py` and exported from the package root.

#### Scenario: Import path
- **WHEN** a user imports `from filerepack import PackResult`
- **THEN** the import succeeds and provides access to the dataclass
- **AND** the dataclass has proper type annotations on all fields
