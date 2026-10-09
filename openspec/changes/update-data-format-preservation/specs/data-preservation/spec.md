## MODIFIED Requirements

### Requirement: Data Schema and Metadata Fidelity

Accepted data-file rewrites SHALL preserve logical values, row order where semantically defined, types, nullability, nested schema, application-visible identifiers, and required file/schema metadata. Writers unable to retain that contract SHALL report an unsupported case without source replacement.

#### Scenario: Parquet custom metadata

- **WHEN** Parquet input has an `app` schema-metadata entry and an accepted recompression
- **THEN** the output SHALL retain the entry, logical schema, and row values

#### Scenario: Unsupported schema or identifiers

- **WHEN** a writer cannot retain required metadata, schema, or application-visible row identities
- **THEN** the source SHALL be unchanged and the unsupported contract SHALL be reported

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

## ADDED Requirements

### Requirement: Bounded Data Processing

Data writers with record-batch support SHALL process bounded batches under the operation's memory/resource policy. Whole-file-only implementations SHALL declare their estimated requirements and decline inputs exceeding the supported budget.

#### Scenario: Large batch-capable table

- **WHEN** a supported large table is recompressed
- **THEN** memory usage SHALL be bounded by processing batches rather than the complete logical table
