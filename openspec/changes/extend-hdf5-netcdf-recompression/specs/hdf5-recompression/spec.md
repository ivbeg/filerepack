## ADDED Requirements

### Requirement: Complete HDF5 graph preservation
The system SHALL compare the source and candidate object graph, hard-link alias
relationships, soft/external link targets, committed types, object and region
references, dimension scales, and exposed group/attribute creation order. Physical
addresses SHALL NOT serve as stable object identities across the rewrite.

#### Scenario: Two names and a reference identify one dataset
- **WHEN** a dataset has two hard links and an object reference in an attribute
- **THEN** both candidate links and the reference SHALL identify the same corresponding dataset

#### Scenario: A region selection changes
- **WHEN** candidate values match but a stored region reference selects different elements
- **THEN** the candidate SHALL fail preservation validation

### Requirement: Typed HDF5 values and metadata
The system SHALL preserve dataset shape, datatype structure, byte order, signedness,
string encoding/padding, fill values, attributes and decoded values. Numeric float
bits SHALL remain exact, including signed zero and NaN payloads. Unsupported typed
comparisons SHALL cause a skip instead of a coercing comparison.

#### Scenario: A datatype is silently normalized
- **WHEN** a writer changes an enum, compound field layout or string datatype despite equal displayed values
- **THEN** the candidate SHALL be rejected

### Requirement: HDF5 container and reader compatibility
The system SHALL retain the complete source user block and source reader-compatible
format bounds. It SHALL NOT follow external storage, merge/prune links, normalize
datatypes, add lossy filters or upgrade format bounds as a side effect of repacking.
Unsupported external/virtual storage or filter features SHALL prevent a verified rewrite.

#### Scenario: An application header occupies the user block
- **WHEN** a supported HDF5 file has an application-specific user block
- **THEN** every user-block byte SHALL remain identical in the accepted output

#### Scenario: A required filter is unavailable
- **WHEN** the source pipeline cannot be decoded and compared by the available verifier
- **THEN** the system SHALL leave the source unchanged and report the unavailable feature

### Requirement: Inspected lossless dataset compression
The system SHALL select bounded lossless candidates per eligible dataset based on
inspected storage properties and tested backend capabilities. Default rewriting
SHALL retain existing chunk geometry; any eligible contiguous-to-chunked change
SHALL be reported. Preservation validation SHALL precede size acceptance.

#### Scenario: Better compression loses a dimension scale
- **WHEN** a smaller candidate no longer binds the original dimension scale
- **THEN** the candidate SHALL be discarded despite its smaller size

### Requirement: Bounded offline HDF5 processing
The system SHALL operate on an offline source or stable snapshot with cumulative
decode, memory, scratch and process budgets, and SHALL publish through the shared
file transaction contract. Missing verification, limits, cancellation or source
changes SHALL preserve source and prior destination.

#### Scenario: A variable length chunk exhausts the memory budget
- **WHEN** a decoded chunk cannot be compared within the operation budget
- **THEN** the system SHALL stop without materializing the entire dataset or publishing staging

### Requirement: HDF5 profile release evidence
An HDF5 profile SHALL require complete domain comparison tests, real smaller-file
examples, a separate read-only verification adapter, and recorded backend/reader
bounds and lineages. Related libhdf5 wrappers SHALL NOT be counted as independent
implementations. Generic HDF5 results SHALL NOT establish MATLAB, AnnData or Loom
application support.

#### Scenario: Generic fixtures pass but MATLAB fixtures are absent
- **WHEN** the HDF5 compression profile has no MATLAB compatibility evidence
- **THEN** it SHALL not advertise verified MAT v7.3 support
