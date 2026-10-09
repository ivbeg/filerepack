# repack-transactions

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Destination Local Atomic Publication

Accepted candidates SHALL be published from a verified staging file on the destination filesystem. Encoding scratch paths MAY be elsewhere, but cross-device publication SHALL NOT copy directly over the existing destination. Failed staging, validation, metadata application, or replacement SHALL preserve original source and existing destination bytes.

#### Scenario: Cross-volume scratch

- **WHEN** encoding scratch and destination reside on different devices
- **THEN** publication SHALL use destination-local staging and complete without a destructive cross-device fallback

#### Scenario: Publication failure

- **WHEN** destination-local publication fails after encoding
- **THEN** the original source and prior destination SHALL remain intact and owned scratch SHALL be cleaned

### Requirement: Filesystem Preservation and Source Generation

In-place replacement SHALL retain documented permission/time/extended-attribute policy and verify that source identity/generation has not changed since inspection. Unsupported requested preservation, source changes, file symlinks, or multiple hard links without an explicit supported policy SHALL prevent in-place publication.

Every source extended attribute SHALL retain its exact value. On macOS only,
when the source lacks `com.apple.provenance`, publication MAY additionally retain
the exact system-assigned value observed immediately after staging-file creation,
before candidate copying or metadata application. This allowance SHALL NOT cover
any other attribute, a later-added provenance value, or an unpreserved source value.

#### Scenario: Permission preservation

- **WHEN** a 0644 file is successfully repacked under the default filesystem policy
- **THEN** it SHALL retain mode 0644 and the documented timestamp policy

#### Scenario: macOS assigns protected provenance to a new stage

- **WHEN** the source lacks provenance and macOS assigns it at staging-file creation
- **THEN** publication MAY retain that exact creation-time provenance value
- **AND** all source attributes, permission mode and mtime SHALL still be verified

#### Scenario: Provenance or other metadata cannot meet the preservation policy

- **WHEN** source provenance differs, creation-time provenance changes, or any other required metadata cannot be retained
- **THEN** publication SHALL be refused while source and existing destination remain intact

#### Scenario: Concurrent source or unsupported link

- **WHEN** source generation changes or an unsupported linked source is discovered
- **THEN** the system SHALL report a conflict/unsupported case rather than replacing that source

### Requirement: Typed Shared Transaction Interfaces

All packer families SHALL use shared typed interfaces for command execution, candidate staging, acceptance, and publication. Codec relocation SHALL preserve existing documented public imports and SHALL NOT introduce process-global cwd mutation or shell command evaluation.

#### Scenario: Existing helper import

- **WHEN** an application imports an existing documented pack_* helper after relocation
- **THEN** the import and supported calling contract SHALL remain available

#### Scenario: Nested packer lifecycle

- **WHEN** a nested packer invokes the shared lifecycle
- **THEN** its transaction SHALL obey parent policy and use typed results without dynamic Any back-imports

### Requirement: Explicit Publication Durability Guarantees

The system SHALL document whether a platform supports atomic visibility and requested crash durability. A requested durability guarantee SHALL require the corresponding supported file/directory flush behavior; unsupported durability SHALL be reported rather than asserted.

#### Scenario: Unsupported durability request

- **WHEN** a platform cannot establish requested crash durability
- **THEN** the operation SHALL report the unsupported guarantee before publication
