## MODIFIED Requirements

### Requirement: Qualified OfficeArt raster selection
The system SHALL enable qualified PNG/JPEG recompression only through
ole_recompress and a parsed host/BLIP profile. It SHALL retain both original
BLIP UIDs, FBSE identity, tags, names, geometry and drawing properties. Unknown
image/identity variants SHALL remain byte-identical with an explicit reason.

#### Scenario: Mixed picture store
- **WHEN** an enabled host contains qualified PNG, JPEG and EMF/WMF alongside unsupported images
- **THEN** each qualified codec is applied under its preservation contract
- **AND** unsupported image bytes and metadata remain identical.

#### Scenario: No raster opt-in
- **WHEN** ole_recompress is false
- **THEN** no raster payload is rewritten by this capability.

### Requirement: Exact PNG IDAT preservation contract
The original static PNG codec SHALL retain exact filtered scanline bytes. Only a
separately qualified DOC/PPT refiltering profile MAY compare exact unfiltered 8-bit
samples. Every profile SHALL preserve IHDR, sample depth, interlacing, palette/alpha,
every non-IDAT chunk and their relative order, color metadata and interpretation.
It SHALL validate chunk CRCs and complete zlib framing under enforced bounds.

#### Scenario: High-depth or interlaced PNG
- **WHEN** a qualified PNG uses 16-bit samples or interlacing
- **THEN** recompression retains exact inflated scanline bytes without converting sample depth or color mode.

#### Scenario: Altered ancillary metadata
- **WHEN** a smaller candidate changes a color/text/profile chunk or an image sample
- **THEN** independent verification rejects the candidate.

### Requirement: Exact JPEG coefficient and metadata contract
The system SHALL restrict the initial JPEG optimizer to qualified sequential
Huffman profiles. It SHALL preserve every quantized DCT coefficient, quantization
table, component/sampling layout, dimension, color/orientation field and APP/COM
marker content/order. Only proven entropy encoding and bookkeeping changes SHALL
be permitted. Unavailable independent coefficient validation SHALL skip JPEG.

#### Scenario: Smaller entropy-coded JPEG
- **WHEN** jpegtran produces a smaller qualified JPEG with equal coefficients, tables and metadata
- **THEN** the independently parsed candidate can enter host verification and physical-size selection.

#### Scenario: Pixels appear equal but a coefficient or EXIF field changed
- **WHEN** rendering matches but a coefficient, quantization table or required marker differs
- **THEN** verification rejects the candidate.

### Requirement: Independent raster and host union verification
The system SHALL independently parse source and candidate raster/host graphs and
account for each declared payload, length and pointer change. Every unrelated
byte and CFB metadata item SHALL match. Strict OLE and exact decoded PPT storage
contracts SHALL remain unchanged; combined transforms SHALL require verification
of their complete union.

#### Scenario: Stale FBSE or host pointer
- **WHEN** an otherwise valid raster replacement leaves an incorrect size or reference
- **THEN** the candidate is rejected before publication.

#### Scenario: Encoder reports a matching digest
- **WHEN** an encoder claims preservation without independently readable output
- **THEN** its claim alone cannot satisfy verification.

### Requirement: Bounded optional raster execution and measured selection
The system SHALL bound image dimensions, decoded samples/coefficients, cumulative
memory, scratch and encoder lifetime within the root operation. It SHALL retain
original image representations and verified compaction/prior alternatives,
accept only physically smaller verified files, and expose per-codec counts,
dependencies, fallback reasons and stream/file savings through existing policies.
It SHALL honor disabled parent image categories and preserve the required metadata
regardless of generic quality/metadata-stripping preferences.

#### Scenario: JPEG tooling is unavailable
- **WHEN** JPEG encoding or coefficient validation is missing but PNG support is available
- **THEN** JPEG is retained with a reason and qualified PNG/metafile work can continue.

#### Scenario: Smaller image yields equal CFB size
- **WHEN** raster stream savings do not reduce the verified final file
- **THEN** the existing smallest baseline is retained and no extra file saving is claimed.

#### Scenario: Parent disables images or requests metadata stripping
- **WHEN** effective parent policy disables images or supplies generic stripping preferences
- **THEN** disabled image codecs do not run
- **AND** any permitted raster operation retains its full required metadata contract.
