## ADDED Requirements

### Requirement: Same kind NetCDF compression
The system SHALL detect the source on-disk kind and NetCDF data model and SHALL
preserve both during ordinary repack. Compression profiles SHALL cover only
verified NetCDF-4/enhanced and NetCDF-4/classic-model files. CDF-1, CDF-2 and CDF-5
inputs SHALL remain unchanged when internal compression would require conversion.

#### Scenario: A classic CDF input is offered to nccopy
- **WHEN** ordinary repack receives a valid CDF-2 file
- **THEN** the system SHALL not silently emit a NetCDF-4 container under the same filename

#### Scenario: A classic-model NetCDF-4 file is rewritten
- **WHEN** a candidate is produced for a NetCDF-4 classic-model source
- **THEN** the candidate SHALL retain that data model and on-disk kind

### Requirement: Raw scientific data preservation
The system SHALL preserve group structure, dimension names/order/lengths and
unlimited status, variable dimension bindings, raw datatype representations and
raw values. Verification SHALL disable automatic masking, scaling and string
conversion and SHALL retain exact numeric float bits.

#### Scenario: Packed temperatures have scale and offset attributes
- **WHEN** a variable stores integer samples with `scale_factor` and `add_offset`
- **THEN** raw integer samples and typed packing attributes SHALL match without float re-encoding

### Requirement: NetCDF attribute and fill semantics
The system SHALL preserve typed global/group/variable attributes, fill and missing
values, units, calendars, coordinate associations and supported user-defined types.
Unknown or undefined states that cannot be compared SHALL cause an explicit skip.

#### Scenario: Values match but the calendar changes
- **WHEN** a candidate changes a time variable's calendar or units attribute
- **THEN** preservation validation SHALL reject it

#### Scenario: Unwritten no-fill data cannot be validated
- **WHEN** the verifier cannot establish equivalent no-fill/unwritten state
- **THEN** the system SHALL retain the original rather than infer equivalence from one read

### Requirement: Lossless storage policy
The system SHALL change only declared lossless compression/storage properties
supported by the source reader profile. Default rewriting SHALL preserve existing
chunk geometry and compatible filter semantics. Quantization, precision reduction
and unlimited-to-fixed conversion SHALL NOT be introduced by repack options.

#### Scenario: A compressor offers smaller quantized data
- **WHEN** a candidate requires rounding or quantization of source values
- **THEN** the ordinary NetCDF handler SHALL not generate or accept that candidate

### Requirement: Bounded verified NetCDF publication
The system SHALL compare complete supported datasets in bounded slices under the
shared operation budget before size acceptance and transactional publication.
Tool success or matching CDL text alone SHALL NOT establish preservation.

#### Scenario: nccopy exits successfully but raw values differ
- **WHEN** source/candidate raw comparison detects one changed value
- **THEN** the candidate SHALL be discarded and prior files SHALL remain intact

### Requirement: Per model compatibility and benefit evidence
Each enabled NetCDF model profile SHALL have real-file gain measurements, raw-data
and metadata fixtures, a read-only reader check and documented tool/library versions.
Attempted unchanged, unsupported and resource-limited files SHALL remain in the
benchmark coverage and savings denominators.

#### Scenario: Only enhanced-model fixtures have been checked
- **WHEN** classic-model preservation has no matching compatibility evidence
- **THEN** enhanced-model results SHALL not be presented as proof for that profile
