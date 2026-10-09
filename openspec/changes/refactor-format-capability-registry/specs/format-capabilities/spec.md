## MODIFIED Requirements

### Requirement: Typed Consistent Format Metadata

Format metadata SHALL provide one typed source for aliases, dispatch category/family, output policy, fidelity guarantees, required tools/extras, structural validator, and verified support level. Identification, filters, dispatch, and generated documentation SHALL derive consistent views from it while preserving documented legacy aliases.

#### Scenario: Registry and docs disagree

- **WHEN** a format changes its writer or validator requirements
- **THEN** generated capability views and consistency checks SHALL expose the same requirements

#### Scenario: Legacy alias

- **WHEN** a documented alias is identified or filtered
- **THEN** its established compatible mapping SHALL remain available unless a separately documented safety policy declines writing

### Requirement: Supported Python Tool Configuration

Python 3.9+ installations SHALL read supported TOML configuration through an available declared parser, including conditional tomli on Python below 3.11. Env/config/PATH precedence and invalid config errors SHALL be deterministic and cache refresh SHALL account for effective configuration changes.

#### Scenario: Python 3.9 TOML config

- **WHEN** a supported older-Python installation supplies a valid tool config
- **THEN** its declared fallback parser SHALL load it instead of silently ignoring it

#### Scenario: Changed effective config

- **WHEN** configured executable or environment precedence changes
- **THEN** subsequent resolution/probing SHALL not reuse an invalid stale positive capability

## ADDED Requirements

### Requirement: Executable and Per Format Capability Diagnostics

Tool diagnostics SHALL validate configured executable availability and probe supported versions/capabilities under deadlines. They SHALL distinguish read support, safe write support, required validators, and optional Python-extra availability. A non-runnable override SHALL NOT report ok. Plain doctor SHALL retain the required-archiver failure rule while displaying optional limitations.

#### Scenario: Nonexistent environment override

- **WHEN** FILEREPACK_7ZZ points to a nonexistent path
- **THEN** doctor SHALL report the required tool unavailable rather than ok

#### Scenario: Extractor without writer or extra

- **WHEN** a backend reads a format but cannot write it, or a Python extra is missing
- **THEN** diagnostics SHALL report each missing capability independently
