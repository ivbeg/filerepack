## MODIFIED Requirements

### Requirement: Qualified compiled nib routing
The system SHALL recognize `.nib` as a standalone document format and optimize
only NIBArchive version 1/coder 9 or 10 with completely parsed, contiguous
documented tables, value types 0–10, terminated class names and valid fallback
class indexes. Unsupported or malformed input SHALL retain its
original bytes and report a reason without instantiating archived objects.

#### Scenario: Unsupported nib variant
- **WHEN** a nib is a keyed plist, has another coder version, or contains unknown
  types, gaps, overlapping tables or trailing data
- **THEN** no candidate SHALL be published and the reason SHALL be available.

### Requirement: Identity-preserving archive compaction
The system SHALL share identical stored value components and canonicalize
structural varints while retaining all object ordinals, classes, reference
targets, per-object value order, keys, scalar payload bits, opaque data, class
fallback indexes, coder version and ordered unreferenced records. Objects SHALL
NOT be merged.

#### Scenario: Equal properties on distinct objects
- **WHEN** two distinct objects have identical serialized properties
- **THEN** the stored property sequence MAY be shared but both object ordinals
  and all references to them SHALL remain distinct.

#### Scenario: Overlapping value ranges
- **WHEN** objects use partially overlapping ranges of the same value table
- **THEN** relocation SHALL preserve each object's complete ordered values.

### Requirement: Independent bounded verification and publication
The system SHALL structurally parse and compare source/candidate preservation
without calling the optimizer, enforce cumulative format budgets and cooperative
cancellation, and publish only through the existing verified transaction and
size-acceptance policies. CLI, library, bulk and nested archive processing SHALL
route nibs consistently.

#### Scenario: Smaller but changed archive
- **WHEN** a valid smaller candidate changes a value, object identity, reference,
  key, class metadata or unreferenced value
- **THEN** preservation validation SHALL reject it and retain the source.

#### Scenario: Policy refusal or resource exhaustion
- **WHEN** dry-run, insufficient savings, cancellation or a resource limit
  prevents publication
- **THEN** the source SHALL remain unchanged and owned scratch SHALL be cleaned.
