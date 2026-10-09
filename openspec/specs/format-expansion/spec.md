# format-expansion

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Additional format routing
The system SHALL identify PSB, GeoJSON, IPYNB, JSONL, NDJSON, QGZ, QGS, QGD, UI,
BLEND, FITS/FIT/FTS, NRRD and ASE/ASEPRITE for standalone and recursive processing.
The system SHALL preserve their filename extensions and SHALL NOT add LAS/LAZ.

#### Scenario: Direct and nested aliases
- **WHEN** a supported new format is encountered directly or in an archive
- **THEN** the appropriate handler SHALL run without renaming the file or member

#### Scenario: Excluded extension conversion
- **WHEN** a LAS or LAZ file is encountered
- **THEN** it SHALL remain unsupported and unchanged

### Requirement: Text and QGIS preservation
JSON-based aliases SHALL retain exact tokens. JSON Lines SHALL retain ordered
records and their line endings. XML aliases SHALL retain existing conservative
XML semantics. QGIS rewrites SHALL validate project structure and auxiliary
SQLite data and SHALL preserve unrelated members and logical database contents.

#### Scenario: JSON Lines lexical fidelity
- **WHEN** valid records contain duplicate keys, large numbers or escaped strings
- **THEN** only token-external whitespace SHALL change within each record

#### Scenario: Unsupported project or auxiliary database
- **WHEN** a QGIS project is malformed or its database cannot be verified
- **THEN** unsupported changes SHALL be rejected and original contents retained

### Requirement: Verified native lossless optimization
PSB and Aseprite SHALL retain decoded channels/chunks and structural metadata.
Blender SHALL retain the complete decoded stream. FITS SHALL retain exact image
values and scientific metadata without quantization. NRRD SHALL retain decoded
binary arrays and header bytes except the supported encoding value.

#### Scenario: Scientific floating-point preservation
- **WHEN** FITS or NRRD contains floating-point arrays
- **THEN** lossless output SHALL retain exact values including signed zero and NaN bits

#### Scenario: Native verification failure
- **WHEN** candidate decoding, structure or content verification fails
- **THEN** the candidate SHALL be discarded and the original SHALL remain unchanged

#### Scenario: Unsupported or excessive input
- **WHEN** an input requires unsupported framing, external files or exceeds parser bounds
- **THEN** it SHALL be left unchanged without applying a lossy fallback

### Requirement: Existing transaction contracts
All new handlers SHALL honor dry-run, minimum savings, growth rejection, distinct
output, filesystem metadata, source-conflict detection and scratch cleanup.
Optional verification dependencies SHALL be declared and their absence SHALL
leave inputs unchanged.

#### Scenario: Dry-run and rejected savings
- **WHEN** dry-run is requested or a candidate does not satisfy size acceptance
- **THEN** source bytes and filesystem metadata SHALL remain unchanged

#### Scenario: Missing optional backend
- **WHEN** an optional format backend is unavailable
- **THEN** the input SHALL remain unchanged and normal processing SHALL continue
