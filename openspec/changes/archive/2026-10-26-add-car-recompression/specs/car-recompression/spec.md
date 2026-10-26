## MODIFIED Requirements

### Requirement: Preserving CAR recompression
The system SHALL recognize `.car` case-insensitively and optimize qualified Apple
BOMStore v1 catalogs without removing any asset variants or changing decoded
DEFLATE resource bytes. It SHALL retain every live block ID, named variable,
tree/key record, CSI/TLV field and opaque resource, normalizing only documented
allocation and compressed-length fields.

#### Scenario: Known ZIP image resources
- **WHEN** a qualified catalog contains MLEC/CELM codec-2 single or KCBC-banded
  zlib/gzip resources
- **THEN** the system SHALL retain the codec, bands, wrapper metadata and exact
  decoded bytes and select smaller DEFLATE encodings when available

#### Scenario: Other resource encodings
- **WHEN** a qualified catalog contains LZFSE, LZVN, Deepmap, palette, ASTC,
  raw data or unknown resource codecs
- **THEN** those complete blocks SHALL remain byte-identical while physical
  allocation/index compaction may reduce the host file

### Requirement: Qualified structural and preservation gates
The system SHALL support the fixed CARHEADER storage versions 8–17, KEYFORMAT
v0 and CSI v1 profile. It SHALL reject overlapping/out-of-range allocations,
ambiguous variables, invalid tree references/chains, malformed length framing,
unclassified nonzero unallocated bytes and malformed DEFLATE envelopes.
Validation SHALL compare source/candidate logical fingerprints independently
of the optimization writer before publication.

#### Scenario: Damaged input or changed candidate
- **WHEN** parsing fails or a candidate changes a key, metadata, opaque block,
  band boundary, compression wrapper or decoded payload
- **THEN** the original file SHALL remain unchanged and a reason SHALL be reported

### Requirement: Bounded CAR lifecycle
CAR processing SHALL obey cumulative format resource budgets, cancellation,
dry-run, output/backup/metadata and minimum-savings policies. It SHALL operate
through the standard CLI/library/bulk and nested archive routes and remain
lossless even when lossy options are enabled.

#### Scenario: Interrupted or refused work
- **WHEN** a resource limit, cancellation, validation or publication failure occurs
- **THEN** the source SHALL remain intact and operation-owned temporary files
  SHALL be cleaned

#### Scenario: Ordinary and nested publication
- **WHEN** a smaller verified CAR candidate is accepted directly or inside a
  deeply walked archive
- **THEN** the standard destination and archive member-preservation policies
  SHALL apply
