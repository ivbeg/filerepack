# data-preservation

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Data Schema and Metadata Fidelity
Qualified Parquet, Arrow/Feather, ORC, Avro and native HDF5/NetCDF profiles SHALL verify their documented logical values, schema and required metadata. Unqualified variants SHALL retain the source and report their limitation.

#### Scenario: Verified current contract
- **WHEN** a supported Parquet with custom metadata is accepted
- **THEN** the schema metadata and ordered values match the source

### Requirement: Arrow IPC Framing Preservation

Arrow inputs SHALL retain file or stream framing unless the user explicitly requests framing conversion. Recompression SHALL preserve logical schema and required metadata in either form.

#### Scenario: IPC stream recompression

- **WHEN** an Arrow IPC stream is repacked without conversion permission
- **THEN** the output SHALL remain an IPC stream and retain its schema and values

### Requirement: SQLite Offline and Snapshot Policy

In-place SQLite processing SHALL require the documented explicit offline policy and SHALL refuse known WAL/SHM-backed or detected active-writer inputs. Distinct-output snapshot operations SHALL use a consistent database snapshot and validate it before publication. The policy SHALL document detection limits rather than promise universal open-connection detection.

#### Scenario: Known live database

- **WHEN** WAL/SHM sidecars or an active writer are detected for an in-place request
- **THEN** the operation SHALL preserve the source and report that a snapshot/offline workflow is required

#### Scenario: Distinct snapshot

- **WHEN** a distinct-output snapshot is requested from a supported SQLite input
- **THEN** a consistent validated snapshot SHALL be produced without replacing the source database
