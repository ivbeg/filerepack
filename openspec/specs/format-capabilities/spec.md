# format-capabilities

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Typed Consistent Format Metadata
Typed extension/family/packer metadata SHALL drive identification and filter views. Capability views SHALL join dispatch, declared validators and configured tools/extras consistently. Declared routing SHALL not be presented as a successful backend round-trip.

#### Scenario: Verified current contract
- **WHEN** a registry view is generated
- **THEN** its aliases match compatibility tests and its prerequisites match the capability view

### Requirement: Supported Python Tool Configuration

Python 3.9+ installations SHALL read supported TOML configuration through an available declared parser, including conditional tomli on Python below 3.11. Env/config/PATH precedence and invalid config errors SHALL be deterministic and cache refresh SHALL account for effective configuration changes.

#### Scenario: Python 3.9 TOML config

- **WHEN** a supported older-Python installation supplies a valid tool config
- **THEN** its declared fallback parser SHALL load it instead of silently ignoring it

#### Scenario: Changed effective config

- **WHEN** configured executable or environment precedence changes
- **THEN** subsequent resolution/probing SHALL not reuse an invalid stale positive capability
