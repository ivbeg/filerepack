# officeart-recompression

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Shared codec with authoritative host discovery
The system SHALL recompress EMF/WMF only after a qualified host adapter resolves
the containing OfficeArt records and every affected reference. The initial
operation SHALL be opt-in through the existing `ole_recompress` option. It SHALL
NOT select payloads by signature scanning of opaque CFB streams.

#### Scenario: Same codec in multiple hosts
- **WHEN** qualified DOC, XLS and PPT records contain compressed EMF/WMF
- **THEN** the same bounded RFC1950 codec processes them
- **AND** each host adapter independently repairs its own lengths and pointers.

#### Scenario: Unsupported host representation
- **WHEN** discovery cannot fully resolve a layout, history, alias or pointer
- **THEN** the operation retains a strictly verified compaction candidate
- **AND** exposes the reason for skipping content recompression.

### Requirement: Exact metafile preservation and separate verification
The system SHALL preserve every decoded metafile byte, UID, geometry, order and
reference identity. It SHALL preserve all unrelated stream and record bytes and
complete CFB logical metadata. It SHALL verify intended changes separately from
the strict `ole` verifier, which SHALL retain its byte-equality contract.

#### Scenario: Valid smaller representation
- **WHEN** the compressed bytes change and all intended-content checks pass
- **THEN** the OfficeArt verifier accepts the candidate
- **AND** strict `ole` equality still rejects the changed representation.

#### Scenario: Damaged payload or stale reference
- **WHEN** a decoded byte, checksum, UID, geometry, pointer, unrelated record or
  directory metadata differs outside the allowed changes
- **THEN** the candidate is rejected before publication.

### Requirement: Bounded encoding and measured candidate selection
The system SHALL share root-operation budgets and supervise encoding in a
killable worker. It SHALL check lengths, checksum, end-of-stream and trailing
data before and after encoding. It SHALL retain original wrappers when no
encoder improves them, and select content recompression only when its fully
verified file is smaller than the verified compaction baseline.

#### Scenario: Stream savings without file savings
- **WHEN** smaller compressed payloads do not reclaim additional CFB allocation
- **THEN** the operation selects the strict compaction baseline
- **AND** reports the lack of additional physical savings.

#### Scenario: Budget exhausted or operation cancelled
- **WHEN** parsing or encoding exceeds the shared budget or is interrupted
- **THEN** no candidate is published
- **AND** operation-owned processes and scratch files are cleaned up.

### Requirement: Raster image qualification is explicit
The initial capability SHALL copy PNG/JPEG and other non-EMF/WMF BLIPs unchanged.
Raster recompression SHALL require a separately qualified pixel/coefficient,
metadata, color, UID and reference preservation contract.

#### Scenario: Mixed raster and metafile store
- **WHEN** a qualified OfficeArt store contains JPEG, PNG, EMF and WMF
- **THEN** only EMF/WMF are eligible in the initial stage
- **AND** JPEG/PNG bytes and metadata remain identical.

### Requirement: Existing transaction and diagnostic policies apply
The system SHALL use the existing dry-run, minimum-savings, backup, output,
filesystem-attribute and archive-member policies. It SHALL expose actual
strategy, payload counts, measured savings and unsupported/no-op reasons.

#### Scenario: Verbose DOC with no eligible payload
- **WHEN** a DOC contains no qualified OfficeArt metafiles
- **THEN** verbose output explains why content recompression was skipped
- **AND** distinguishes it from any container-compaction result.

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

### Requirement: Versioned OLE maximum effort mapping
The system SHALL preserve current default OLE codec effort and use existing ultra
selection for a documented versioned stronger mapping. Version 1 SHALL retain
original/zlib9/Zopfli15 trials with the existing 1 MiB Zopfli15 cutoff and add a
qualified Zopfli50 trial up to 2 MiB. Hard root/payload limits SHALL NOT increase.

#### Scenario: Ultra on an eligible metafile
- **WHEN** ole_recompress and ultra are true for a qualified payload within the maximum cutoff
- **THEN** the additional bounded trial is considered and effective mapping/version are reported.

#### Scenario: Ultra without a content mode
- **WHEN** ultra is selected without enabling OLE content recompression
- **THEN** no payload transformation is activated and strict compaction behavior remains unchanged.

### Requirement: Best verified OLE trial retention
The system SHALL retain original and best default representations while trying
maximum effort, independently verify each new result and select the smallest
fully verified physical candidate. More iterations SHALL NOT be assumed to
produce a smaller representation or justify discarding an earlier result.

#### Scenario: Stronger trial is larger
- **WHEN** a Zopfli50 result is larger than the retained default result
- **THEN** the default result remains available and the larger result is not selected.

#### Scenario: Extra encoded saving has no physical effect
- **WHEN** a stronger stream result produces the same allocated file size
- **THEN** no extra file saving is claimed and the existing best baseline is retained.

### Requirement: Effort compatibility and cumulative bounds
The system SHALL propagate resolved effort through existing caller/worker paths,
keep optional encoders optional, and charge all trials to one root budget. It
SHALL NOT enable loss, change image quality or apply mappings to unqualified
framing/codecs. Timeouts/cancellation SHALL retain the existing no-publication
root policy and report incomplete effort accurately.

#### Scenario: Optional Zopfli is absent
- **WHEN** ultra is requested without a qualified binding
- **THEN** original/zlib9 processing remains available and diagnostics state that the stronger trial was unavailable.

#### Scenario: Maximum trial exceeds the root deadline
- **WHEN** cumulative trial work exhausts the deadline
- **THEN** owned work stops, scratch is cleaned and no interrupted maximum result is published.

### Requirement: Measured maximum effort evidence
The system SHALL report mapping/encoder versions, eligible/completed/skipped
counts, wall time, memory, accepted-candidate rate and physical gains on the same
pinned real corpus against default and strict compaction. Synthetic weak encodings
SHALL be separated and no unmeasured savings percentage SHALL be promised.

#### Scenario: Maximum effort documentation is published
- **WHEN** users are advised to enable ultra for OLE
- **THEN** guidance includes measured costs/gains and codec/dependency/size limits.

### Requirement: Independent notes-bearing PPT Pictures qualification

The system SHALL qualify Pictures recompression separately from embedded DOC/XLS
record recompression for audited notes-bearing PPT hosts. It SHALL bind every
untouched external-object wrapper and consumer to the same logical host object,
preserve them byte-identically, and account for every selected delay-store BLIP.
It SHALL permit audited shared FBSE entries while preserving BStore indexes,
sharing counts, UIDs and all shape properties. A bounded deterministic PNG
selection SHALL retain unselected BLIPs byte-identically without increasing the
existing operation limits. Verification SHALL compare the qualified exact PNG
sample identity (filtered or independently unfiltered) and non-IDAT chunks,
every unchanged record and all outer CFB metadata/streams;
only selected BLIP encodings and their enumerated FBSE size/delay fields may
change. Acceptance SHALL use verified final-file savings over ordinary compaction.

#### Scenario: Untouched subtype-zero object is referenced by a master
- **WHEN** an audited host has a uniquely resolved subtype-zero external object
  referenced by a live main master and only Pictures payloads are selected
- **THEN** its complete original wrapper, identity and references SHALL remain exact
- **AND** its inability to pass the separate DOC/XLS re-encoding profile SHALL NOT
  alone disqualify the Pictures strategy

#### Scenario: Multiple shapes share one BStore entry
- **WHEN** an audited FBSE has positive cRef greater than one and valid consumers
- **THEN** selected image recompression SHALL retain its index, sharing and UID
- **AND** every delay-store offset and size change SHALL resolve to the same image

#### Scenario: Total image workload exceeds the selection allowance
- **WHEN** some individually qualified PNGs would exceed the cumulative selection
  allowance
- **THEN** a deterministic bounded subset MAY be selected
- **AND** all other BLIPs SHALL be retained byte-identically
- **AND** actual root-budget exhaustion SHALL fail the trial rather than be ignored

#### Scenario: Notes or immutable object data changes during Pictures rewriting
- **WHEN** a candidate changes any notes byte, external-object wrapper, consumer,
  count, UID or other byte outside the precise permitted write fields
- **THEN** independent preservation verification SHALL reject it before publication

### Requirement: Qualified PPT PNG refiltering
The system SHALL independently qualify static, noninterlaced 8-bit PPT PNGs for
refiltering through exact unfiltered sample identity. It SHALL preserve complete
IHDR, sample depth/color mode, palette/index/alpha samples, all non-IDAT chunks and
their order, BLIP/FBSE identities and the complete immutable host graph. Other
PNG layouts SHALL retain the exact-filtered contract. It SHALL run only through
the existing ole_recompress opt-in, with optional qualified oxipng and verified
original/zlib/Zopfli alternatives. A final independent host verifier SHALL
account for every changed payload, length and permitted delay-store field.

#### Scenario: Smaller refiltered image with exact samples
- **WHEN** a qualified PPT PNG changes filters but every unfiltered sample is exact
- **THEN** its IDAT candidate MAY be selected after restoring exact source chunks
- **AND** the native result SHALL pass independent whole-host verification.

#### Scenario: Encoder changes depth, metadata or an invisible color sample
- **WHEN** a trial changes IHDR, a palette entry, alpha or any unfiltered sample
- **THEN** that trial SHALL be rejected
- **AND** source non-IDAT chunks SHALL never be replaced by encoder metadata.

#### Scenario: Qualified optional encoder is unavailable
- **WHEN** the qualified oxipng version is missing or an ordinary encoder trial fails
- **THEN** verified original/zlib/Zopfli alternatives SHALL remain usable
- **AND** diagnostics SHALL explain the unavailable refiltering trial.

#### Scenario: Local optional encoder ceiling is reached
- **WHEN** an optional trial reaches its local time ceiling while the root remains available
- **THEN** its owned process SHALL be stopped and partial output accounted and removed
- **AND** verified prior encodings SHALL remain usable
- **AND** actual root exhaustion or cancellation SHALL NOT be masked as a fallback.

### Requirement: Sequential PPT PNG root reservation
The system SHALL inspect and encode PPT PNGs sequentially with compact identities.
It SHALL derive a deterministic sample selection allowance from conservative
root decode reservations while retaining individual PNG and record-count bounds.
Every actual decode and process SHALL remain charged to the same root resource
limits. It SHALL NOT increase default root memory/decode/scratch/deadline limits.
Completed independent whole-host verification MAY be reused only when bound to
exact source and candidate digests and file snapshots. Publication SHALL retain
all source, candidate, metadata and destination conflict guards.
Embedded Photoshop storages and their independent object identities SHALL remain
byte-identical; storage sharing SHALL NOT be inferred from matching bytes.

#### Scenario: Image workload exceeds the old retained-sample allowance
- **WHEN** sequential processing can fit a larger qualified PNG workload in the root reservation
- **THEN** more images MAY be selected without retaining all expanded samples
- **AND** unselected images SHALL remain byte-identical.

#### Scenario: Actual root budget or cancellation is reached
- **WHEN** parsing, decoding, encoding or validation exhausts a root limit or is cancelled
- **THEN** no candidate SHALL be published and owned work SHALL be cleaned up.

#### Scenario: Files change after independent worker verification
- **WHEN** the source or candidate differs from the completed verification binding
- **THEN** acceptance SHALL refuse publication and retain the current source.

### Requirement: Audited additional PPT round-trip Pictures forms
The system SHALL extend Pictures-only qualification to independently audited
RoundTripContentMasterId12Atom slide records, additional content-layout package
instances, drawing-group color-MRU records, multi-property OfficeArtTertiaryFOPT
tables and the observed shape-owned PPT9 extension forms. It SHALL additionally
resolve audited composite masters/slides to one live original master, require
unique non-overlapping layout instances and match each slide's legacy master.
Shape-owned PPT9 text runs SHALL be bounded and fully framed; only the observed
zero or null-picture-bullet/numbering PF9 forms and zero CF9/SI masks SHALL be
admitted. Non-null bullet-picture targets SHALL remain outside this profile.
It SHALL validate their
standard versions, instances, lengths, owners and relevant reference semantics
before selecting image payloads. It SHALL retain every byte of these records and
tags, complete property-table reference accounting, existing notes/host validation,
PNG sample/metadata preservation, unselected-image preservation and resource bounds.
Only the existing exact FBSE size/delay fields and selected Pictures encodings MAY
change. Unknown or malformed forms SHALL remain outside this extended profile.

#### Scenario: Audited round-trip presentation contains compressible Pictures
- **WHEN** a single-edit PPT contains only qualified round-trip forms and its complete host and Pictures references pass validation
- **THEN** existing bounded PNG encoders SHALL be eligible under the ole_recompress option
- **AND** every round-trip record, package, tag and logical identifier SHALL remain byte-identical
- **AND** acceptance SHALL require independent whole-host preservation and physical size improvement over verified compaction.

#### Scenario: Added extension form has invalid structure or references
- **WHEN** a proposed form has an unqualified header, owner, tag name, property bound or relevant reference
- **THEN** Pictures recompression SHALL be rejected before publication
- **AND** any compaction fallback SHALL retain its separate strict preservation contract.

#### Scenario: Candidate changes an admitted immutable extension byte
- **WHEN** a candidate changes an admitted round-trip record, complex property package or programmable tag outside the existing FBSE write mask
- **THEN** independent preservation verification SHALL reject the candidate.

#### Scenario: Composite layout and null-bullet text runs are qualified
- **WHEN** composite master/slide identities resolve consistently and every PPT9 text run has an audited mask and null picture-bullet reference
- **THEN** the existing Pictures operation SHALL be eligible under the same exact immutable-byte contract
- **AND** missing original masters, conflicting slide references, duplicate layouts and unqualified text properties SHALL be rejected.

### Requirement: Audited Word table-style and display-property coverage
The system SHALL admit audited offset-free Word formatting operands and
conditional table-style operands only with complete framing and permitted nested
property validation. Conditional operands SHALL occur only in table styles,
contain a qualified condition and contain no picture/OLE identity, Data offset,
unknown operand or further conditional operand. Exceptional tab-stop lengths
SHALL be computed from bounded array counts. Word-specific scalar protection and
shape flags and the shape-owned scalar tertiary dhgt property SHALL be preserved
exactly. Only empty complex fillBlip/lineFillBlip defaults SHALL be admitted by
this additional property profile. Other hosts SHALL retain their existing
qualification scope. Publication SHALL require independent whole-document
preservation and physical savings against strict compaction; unreferenced
pictures, history, formatting and unrelated streams SHALL remain byte-identical.

#### Scenario: Formatted inline Word pictures are recompressible
- **WHEN** a DOC contains qualified pictures with the admitted formatting and drawing properties
- **THEN** lossless image recompression SHALL be eligible through ole_recompress
- **AND** every unrelated stream, formatting byte and reference identity SHALL be preserved.

#### Scenario: Conditional formatting hides a reference or has invalid framing
- **WHEN** a conditional operand contains a forbidden nested property, invalid condition, unqualified owner or truncated operand
- **THEN** content recompression SHALL be rejected before publication
- **AND** independently verified strict compaction SHALL remain available.

#### Scenario: Newly admitted immutable bytes change
- **WHEN** a candidate changes a conditional style, scalar drawing property or unreferenced picture
- **THEN** independent intended-content verification SHALL reject that candidate.

### Requirement: Qualified DOC PNG refiltering
The system SHALL qualify static, noninterlaced 8-bit PNGs in audited inline and
floating DOC pictures for filter selection using exact unfiltered samples. It
SHALL preserve all non-IDAT chunks, IHDR, palette/index identity, alpha and
invisible colors, complete Word formatting/references and unselected picture
bytes. It SHALL reuse bounded optional encoder execution and independent final
host verification. Sequential compact identities SHALL reserve five decode
passes per selected sample workload and retain the existing DOC 64 MiB aggregate
bound and unchanged root resource limits. Other PNG layouts and XLS SHALL retain
their existing exact-filtered contract.

#### Scenario: Qualified Word picture uses better row filters
- **WHEN** ole_recompress selects a qualified inline or floating Word PNG
- **THEN** a smaller refiltered candidate MAY be accepted only after exact sample,
  metadata and whole-host verification
- **AND** all consumers SHALL resolve to the same picture and formatting.

#### Scenario: Optional encoder changes a hidden sample or metadata
- **WHEN** an encoder changes a sample, IHDR, palette or source metadata
- **THEN** changed samples/header SHALL reject its candidate and only validated
  IDAT MAY be used with restored exact source metadata
- **AND** verified earlier representations SHALL remain available.

#### Scenario: Optional encoder is absent or reaches its local ceiling
- **WHEN** qualified oxipng is absent, invalid or reaches its optional trial ceiling
- **THEN** earlier verified encodings SHALL remain usable with a diagnostic
- **AND** actual root exhaustion or cancellation SHALL still refuse publication.

#### Scenario: Word picture workload exceeds its reservation
- **WHEN** a PNG exceeds the deterministic aggregate/root selection allowance
- **THEN** its encoded bytes SHALL remain exact
- **AND** every actual decode and process SHALL retain the root resource guards.

### Requirement: Audited sound-free PPT animation Pictures qualification
The system SHALL admit the audited sound-free AnimationInfoContainer and
AnimationInfoAtom checker-entrance and fly-from-bottom forms for Pictures processing after validating
headers, instances, sizes, shape/client-data ownership, child inventory and
relevant fields. The additional legacy fly tuple SHALL be exactly
`(1, 12, 3, 0, 0, 0)` for build/effect/direction/after-effect/text-build/OLE-verb.
It SHALL admit the bounded PPT10 checker effect, visibility set,
begin-condition and integer-property forms after checking their typed owners,
children, exact audited fields/strings and visual references to live shape IDs.
It SHALL additionally admit audited linear PPT10 coordinate tracks with exactly
two ordered 0/1000 keyframes, x values `#ppt_x`/`#ppt_x`, y values
`1+#ppt_h/2`/`#ppt_y`, empty formula variants and exact calculation/behavior fields.
The coordinate names, keyframe roles and live visual targets SHALL be validated
together. The observed PPT10 document font-only defaults/master levels SHALL
require exact fields and a unique live font-0 target.
It SHALL retain every animation/tag byte and all existing image/host, resource
and protection checks. Unknown, malformed or sound-bearing forms SHALL be rejected.
The existing trailing-storage recompression contract SHALL remain unchanged.

#### Scenario: Qualified presentation contains sound-free animation
- **WHEN** all animation forms and existing host/picture references are qualified
- **THEN** existing bounded lossless image encoders SHALL be eligible
- **AND** complete animation and embedded storage bytes SHALL remain unchanged.

#### Scenario: Animation is malformed or outside the audited scope
- **WHEN** an animation has an invalid owner, header, child, field or sound reference
- **THEN** Pictures qualification SHALL reject it before publication.

#### Scenario: PPT10 timing refers to a shape
- **WHEN** a supported checker/visibility behavior has a typed visual shape reference
- **THEN** the reference SHALL resolve to a shape within its containing live page
- **AND** unknown effects, strings, variants and missing targets SHALL be rejected.

#### Scenario: Qualified fly-from-bottom presentation contains coordinate timing
- **WHEN** the sound-free legacy fly tuple and its bounded PPT10 coordinate/keyframe forms pass qualification
- **THEN** existing lossless Pictures encoders SHALL be eligible
- **AND** the complete animation/timing bytes SHALL remain exact and the independent host contract SHALL verify them.

#### Scenario: Fly timing has mismatched coordinate, keyframe or target
- **WHEN** a coordinate track has an unqualified formula, calculation flag, timestamp, child order, value instance or visual target
- **THEN** Pictures qualification SHALL reject it before publication
- **AND** the separate strict compaction fallback SHALL remain available.
