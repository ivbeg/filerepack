# Shared OfficeArt recompression with host-owned relocation

## Primary format evidence

The shared unit is an OfficeArt BLIP, not an arbitrary CFB stream. The following
Microsoft specifications were inspected on 2026-10-04:

- [OfficeArtMetafileHeader, MS-ODRAW 2.2.31](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/ffdcc2b8-98fd-46b2-921e-6bb6693d05e5):
  decoded `cbSize`, bounds and rendered size, encoded `cbSave`, compression and
  filter. Compression 0 is RFC1950 DEFLATE; 0xFE means uncompressed. The initial
  gate admits compressed EMF/WMF with filter 0xFE. Uncompressed metafiles and
  PICT require further qualification.
- [OfficeArtBlipWMF, MS-ODRAW 2.2.25](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/ee892f04-f001-4531-a34b-67aab3426dcb):
  version/instance distinguish one or two 16-byte UIDs. They identify decoded
  content; recompressing identical decoded bytes preserves both original UIDs.
  [EMF, 2.2.24](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/2c09e2c4-0513-419f-b5f9-4feb0a71ef32)
  has a parallel layout with different record type/instances.
- [OfficeArtFBSE, MS-ODRAW 2.2.32](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/2f2d7f5e-d5c4-4cb7-b230-59b3fe8f10d6):
  record length, BLIP size, reference count, UID, optional name and delay offset.
  An embedded BLIP makes `foDelay` irrelevant; preserve that ignored field.
- [PICFAndOfficeArtData, MS-DOC 2.9.192](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/dedb7505-8cc4-4053-aa2d-431b18d4bd97)
  and [PICF, 2.9.190](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/d81b079b-e28a-4d58-a7d3-e10c813a7098):
  inline pictures reside in Data at character-property `sprmCPicLocation` values;
  the 68-byte PICF declares the complete picture size. Shape-file names are a
  distinct optional prefix, not an OfficeArt header.
- [Character properties, MS-DOC 2.6.1](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/7022285b-9621-42e9-ad4d-4e02c115ef18)
  and [Direct character formatting, 2.4.6.2](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/be58bf9c-d1d3-40cc-91ee-36452d7939b2):
  the same property can designate a picture, binary data or an OLE storage ID.
  Resolving it requires text positions, FKP properties, piece PRMs and styles;
  a numeric property signature alone is insufficient.
- [MsoDrawingGroup, MS-XLS 2.4.171](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/43e0d496-45db-4f19-bb33-bcb2464aa83c)
  and [Globals substream](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/ca4c1748-8729-4a93-abb9-4602b3a01fb1):
  the OfficeArt drawing group is carried by BIFF MsoDrawingGroup and CONTINUE.
  Supported application variants can use MsoDrawingGroup instead of the first
  CONTINUE; qualify versions and fragmentation explicitly.
- [Workbook Index, MS-XLS 3.9.23](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/b06ea609-4ba2-4dab-9978-14e3b034706a)
  and [ExtSST](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/5d981e62-9e25-490a-9a75-b177373e2d79):
  worksheet starts are not the only absolute stream pointers. Index includes
  `ibXF` and DBCell offsets; ExtSST includes string-table record pointers.
- [Pictures stream, MS-PPT 2.1.3](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/150a72bc-487f-467e-994e-01270dfaf9bf):
  Pictures is an OfficeArt delay store, referenced by FBSEs in the live document's
  drawing group. Moving a picture changes delay offsets and FBSE sizes, while
  fixed-size reference patches need not move PPT persist/edit records.

These layouts motivate the architecture; they do not establish universal OLE
support. New OLE applications require separately audited host adapters.

## Measured development experiment

`dev/ole/officeart_pilot.py` accepts four exact SHA-256-bound Apache POI fixtures
at commit `12c3688d130035f3dc2ca2a0f50d929456435a93`, plus encoding-only variants
that it constructs itself. New fixtures retain original bytes and provenance,
Apache-2.0 LICENSE and NOTICE. It uses the existing independent test CFB allocator
for staging and the locked cfb 0.14.0 native compactor for final allocation.
Neither the allocator nor checksum-specific host mappings may enter production.

The shared codec parses nested OfficeArt record bounds and embedded FBSEs,
updates record/BLIP lengths and preserves UIDs, geometry, other records and
decoded metafiles. Three separate host adapters handle relocation:

| Fixture | Audited host-owned changes |
| --- | --- |
| `vector_image.doc` | One PICF at Data offset 0; update its complete length. The CPicLocation target remains 0. Retain all 2,289 logical padding bytes. |
| `word_with_embeded.doc` | Four contiguous PICFs; update their complete lengths and four picture CPicLocation operands. Other operands identifying OLE storages remain identical, as do every embedded-storage byte and all table data. |
| `SimpleWithImages.xls` | Merge/refragment one global drawing group into records of at most 8,224 payload bytes; patch three BoundSheet offsets and three Index `ibXF` pointers. Its ExtSST has no pointer entries and Index has no DBCell array. Retain its JPEG/PNG bytes and all worksheet records apart from those six pointers. |
| `ole2-embedding-2003.ppt` | Two EMFs in Pictures; patch their FBSE sizes and delay offsets. Other PPT bytes, edit/persist references and compressed embedded DOC/XLS objects remain identical. |

Measured originals with Zopfli 0.4.3 / 15 iterations:

| Original | Source bytes | Compaction bytes | OfficeArt candidate bytes | Extra file savings | Stream savings |
| --- | ---: | ---: | ---: | ---: | ---: |
| `vector_image.doc` | 24,064 | 24,064 | 24,064 | 0 | 74 |
| `word_with_embeded.doc` | 117,248 | 117,248 | 116,224 | 1,024 | 773 |
| `SimpleWithImages.xls` | 48,128 | 48,128 | 47,104 | 1,024 | 796 |
| `ole2-embedding-2003.ppt` | 40,448 | 37,888 | 37,888 | 0 | 149 |

zlib level 9 alone saves 599 stream bytes / 1,024 physical bytes in the embedded
DOC; it provides no metafile savings on the other three originals. The difference
between stream and file savings reflects mini/regular sector boundaries and FAT
allocation. In particular, neither a found payload nor a smaller wrapper guarantees
a smaller file. Rendering is identical even where the representation changes
without additional file savings; runtime must select the strict baseline there.

The report `dev/ole/qualification-officeart.json` contains 24 candidates: four
real originals, two controlled compression variants per original and two encoders
per input. All pass intended-content/CFB metadata comparison, native stage-manifest
equality and before/after page-pixel comparison. Rendering uses LibreOfficeDev
26.8.0.0.alpha0 commit `2c87e51eeaa2b413ff4ae097b2705eea1995d8e5`, Poppler 26.05.0,
96 DPI and a private profile with macro security level 3. Controlled zlib 0/1
wrappers preserve decoded content but are not additional real-world samples.
Microsoft Office repair prompts, other operating systems, generalized eligibility
and peak RSS are unmeasured. This experiment is evidence for feasibility, not
production qualification or an expected compression ratio.

## Runtime structure after approval

### Common record codec

Separate bounded OfficeArt parsing, payload decoding and representation selection
from host reference resolution. Admit audited version/type/instance combinations;
check exact container and embedded lengths, optional UID/name fields, `cbSize`,
`cbSave`, compression/filter, EOF, checksum and absence of trailing/concatenated
data. Preserve the exact decoded EMF/WMF bytes; no metafile simplification, object
activation, image conversion, metadata stripping or rendering-based equivalence.

Use zlib 9 and the qualified optional Zopfli 0.4.3 pass. Select the smallest of
the original, zlib and Zopfli wrappers. Retain the original when equal or larger.
Bound 64 selected payloads, 16 MiB per encoded/decoded payload, 64 MiB aggregate
decoded payloads and 1 MiB per Zopfli call. The existing operation limits can
reduce those ceilings, and all stages share the root decoded/node/scratch/time
accounting. Supervise native encoders/writers in the existing killable worker;
fixed bounds in the development experiment do not qualify runtime isolation.

Nonselected BLIPs and unknown leaf payloads remain opaque and byte-identical.
Unknown records that could contain host pointers cannot be accepted by assuming
opacity; a host allowlist must establish they do not need relocation.

### Host adapters

DOC initially targets inline PICF-backed Data pictures, not floating/delayed
WordDocument pictures. Discover all relevant properties through the complete
character-formatting model, account for aliases and every Data reference, and
distinguish picture, binary-data and OLE-ID operands. Restrict the first gate to
audited referenced PICF blocks and qualified padding; preserve padding bytes,
not just their visual effect. Repair selected PICF lengths, embedded FBSE sizes,
ancestor OfficeArt lengths and every affected actual reference. Reject unresolved
inheritance, unqualified property sources, external links and overlapping blocks.
Text, fields, OLE storage identifiers and their serialized payloads remain exact.

XLS initially targets embedded BLIPs in the global drawing group of BIFF8.
Reconstruct only that group with bounded fragmentation and checked lengths.
An audited BIFF/version allowlist is required before interpreting or preserving
records during relocation. Repair BoundSheet, Index `ibXF`/DBCell and ExtSST
pointers where qualified; reject populated/other pointer families until audited.
Verify each target's record identity and intra-record offset, not merely that it
points somewhere valid. Worksheet drawing indices, cells, formulas, styles,
other BIFF records and external CFB storages stay exact.

PPT initially targets a qualified single-edit live drawing group and Pictures
delay store. Account for every live reference and store record, empty slots,
UIDs, shared entries and unreferenced/historical payloads; do not discard history.
Reject layouts with unaccounted aliases/dead references. Preserve store indices
and reference counts, update sizes and map delay offsets to unchanged BLIP
identities. The PowerPoint Document length stays unchanged for fixed-size FBSE
patches; persist/edit/current-user bytes must remain exact.

Initially compare three separately verified PPT candidates: strict compaction,
existing embedded-storage recompression and OfficeArt recompression. Select the
smallest using its own verifier. Combining both live-stream transformations
requires a tested union contract; applying one and blindly reusing the other's
fingerprint is prohibited. This retains existing PPT capability during rollout.

### Native writer and verifier

Extend the native helper with a capability-advertised, bounded root-stream
replacement plan whose host-specific allowed names are explicit. Require all
replacement inputs to be private files, names to be unique and actual existing
root streams, exact source/replacement lengths, aggregate stream limits and empty
owned staging output. Copy all other streams and logical metadata exactly.
Keep existing compact and PPT replacement invocations compatible. A general
replacement mechanism does not authorize generic content transformation.

The `officeart` verifier reparses both files and their host graphs independently
of the candidate writer/patch plan. It checks complete CFB logical manifests,
all unaffected streams, every normalized host record, exact decoded hashes,
UIDs/geometry/metadata and reference target identities. Normalize only the
specific selected record lengths and reference fields; all other bytes remain
part of the fingerprint. The strict `ole` validator remains unchanged. Both CFB
readers and the protection/profile gates must agree before publication.

Build and verify a strict compaction baseline first. Unsupported profiles fall
back with a reason; a malformed transformed candidate or reader disagreement
fails the operation without publication. Select an OfficeArt candidate only if
it improves final physical size over that baseline. Shared transaction policies
then decide dry-run, minimum savings, output/backup and filesystem attributes.

### Diagnostics and later raster stage

Keep the existing boolean CLI/API option and archive propagation. Report actual
strategy, host/profile, selected/recompressed counts by payload type, decoded
bytes, encoder, stream savings, compaction size and additional file savings.
Distinguish no payload, unsupported references, missing writer/encoder,
already-optimal wrappers and sector rounding. Structured results stay parseable.

JPEG/PNG in mixed stores remain byte-identical in the first stage. Before raster
rewriting, qualify PNG chunk order/content/ancillary metadata, color and pixel
semantics, and JPEG coefficients/color/markers/metadata and decoder behavior.
Audit BLIP UID definitions and every reference before changing file bytes.
Do not assume a generic image packer's metadata policy matches OfficeArt.
Lossy transforms, arbitrary OLE formats, VBA and nested-CFB compaction are outside
the initial contract.

## Coordination and validation

The existing transaction/resource mechanisms are reused; pending broader outcome,
CLI-status, profiles, audit and resource-budget proposals are not implemented here.
Existing completed OLE/PPT preservation contracts remain independent. Mandatory
runtime checks cover three hosts/aliases, protected and unknown layouts, corrupt
envelopes, complete reference graphs, valid pointers to wrong objects, unrelated
bytes/metadata, CFB reader disagreement, budgets/cancellation, archives, thresholds,
dry-run and output safety. Qualify source/wheel/sdist and native platform CI.
Renderer comparisons supplement exact byte/graph preservation; they never replace it.


## Initial runtime qualification boundaries

The first Word adapter accepts canonical base FIB C1 with consistent effective
97/2000/2002/2003/2007 version/count pairs, audited non-picture style properties,
zero piece PRMs, complete character formatting and inline PICFs covering Data.
Every referenced paragraph style must exist; FIB/text/FKP overlaps and partially
aliased property blocks fail qualification. Special picture/object/binary flags
are never inferred from opaque numeric operands.

XLS initially accepts audited image-only BIFF8 records with empty SST/ExtSST/Index
arrays and embedded BLIPs. Its qualified absolute pointer families are BoundSheet
and Index ibXF; other populated/offset-bearing families are excluded. The common
FOPT allowlist contains only audited default colors/protection and picture
identity/name/flags. Split menu colors retain their fixed four-color layout.
PPT additionally uses the existing audited single-edit/trailing-storage gate.
These are structural gates, not fixture hashes or fixed production offsets.

Runtime sources additionally follow [effective Word version determination](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/fe661052-9c88-4ae1-aec4-44799b2b4777),
[FOPT property table lengths](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/10dc2fe1-9e69-48dc-a1d1-2921dfb9c28e),
[split menu colors](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/9ec5eac5-0690-4526-ae60-fed701133495)
and [FBSE semantics](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/2f2d7f5e-d5c4-4cb7-b230-59b3fe8f10d6).
Embedded FBSE foDelay fields are ignored by the host and are retained exactly;
PPT nonembedded foDelay fields are resolved and relocated explicitly.
