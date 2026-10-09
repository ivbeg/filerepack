# OLE recompression feasibility and design

Research and implementation date: 2026-10-04. The design below records the original
proposal; the implementation/qualification record at the end defines shipped scope.

## Context

OLE Compound File Binary (CFB, also called OLE2 structured storage) is a hierarchy
of storages and streams inside a sector-based file. Its allocation structures
include FAT, MiniFAT, DIFAT and directory sectors. The format provides no general
compression codec for its streams; compression, where present, belongs to the
application's stream format. See the [Microsoft CFB overview](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/bc33425a-fbb9-4f73-911f-2662c7a14060).

In the current working tree, `consts.py` registers ZIP-based Office extensions,
and `dispatch.py` has no legacy Office packer. `candidates.py` already stages,
verifies and publishes candidates; `verification.py` requires structural checks
and supports source/candidate preservation comparisons. These are the integration
points, rather than treating an OLE file as a ZIP archive.

## Three distinct optimization levels

| Level | Transformation | Preservation contract | Expected opportunity |
| --- | --- | --- | --- |
| Container compaction | Copy live streams/storages into a compact CFB allocation layout | Identical stream bytes and logical directory metadata | Unused sectors, holes in the mini stream and redundant allocation/directory capacity |
| Supported compressed payloads | Re-encode an identified compressed record or image and update its host references | Identical decompressed bytes or a separately defined image contract; all surrounding content preserved | PPT compressed OLE objects, OfficeArt metafiles, PNG/JPEG data |
| Application-level resave | Reconstruct the document using an Office object model | Whole-document semantic preservation must be independently demonstrated | Obsolete application records and other format-specific redundancies |

The first level is the initial implementation scope. It retains the complete
logical stream content, including unknown streams, metadata property sets, VBA,
embedded objects and application history contained in live streams. It is not a
byte-for-byte copy of the physical container: free-sector remnants, directory
padding and allocation ordering can change or disappear. Applications requiring
forensic preservation of deleted physical data should retain the original file.

Fragmentation alone does not establish savings: moving the same number of live
sectors changes their placement, not the file size. Required sector rounding
remains. DOC fast-save remnants inside a live stream and PPT obsolete persist
records inside `PowerPoint Document` survive this stage. A compact file can yield
zero savings. No percentage should be advertised before a representative pilot.

## Libraries and backend decision

| Library/API | Actual capability relevant to this work | Integration trade-off |
| --- | --- | --- |
| [olefile](https://olefile.readthedocs.io/en/latest/Howto.html) | Python stream/directory/property inspection; overwrite only with the same stream length | Useful independent reader; insufficient as the compaction writer |
| [OpenMcdf](https://github.com/openmcdf/openmcdf) | .NET storage/stream read/write and explicit consolidation through `Flush(consolidate: true)` | Fastest candidate for a compaction experiment; runtime/distribution cost and directory-tree limitations need qualification |
| [Rust cfb](https://docs.rs/cfb/latest/cfb/) | CFB read/write; explicit version creation and storage metadata setters in the [CompoundFile API](https://docs.rs/cfb/0.14.0/cfb/struct.CompoundFile.html) | Candidate for a small optional native helper; preserve metadata explicitly and pin a tested release |
| [Apache POI POIFS](https://poi.apache.org/components/poifs/how-to.html) | Read, create and write an OLE filesystem, including nested directories | Java dependency; useful baseline and potential companion to Office-specific parsing |
| [Apache POI HSSF/HSLF/HWPF](https://poi.apache.org/components/) | Format-specific XLS/PPT/DOC object models | More useful for later record analysis; high-level resave needs a stronger preservation contract |
| [libgsf MS OLE2](https://gnome.pages.gitlab.gnome.org/libgsf/api/gsf-MS-OLE2.html) | C input/output APIs for OLE storages and CLSIDs | GLib/native deployment and coverage of directory fields need investigation |
| [SheetJS js-cfb](https://github.com/SheetJS/js-cfb) | JavaScript CFB parse/read/write APIs | Useful comparison implementation; Node dependency and complete metadata retention require qualification |
| [Windows IStorage::CopyTo](https://learn.microsoft.com/en-us/windows/win32/api/objidl/nf-objidl-istorage-copyto) | Microsoft documents copying root storage to a new storage as a way to compact a document file | Useful Windows reference implementation; insufficient as the cross-platform backend |

Recommendation: use OpenMcdf for the first comparative compaction experiment;
evaluate a Rust `cfb` helper as the preferred distributable backend alongside an
independent Python reader. Pin versions and record license, platforms, metadata
behavior, runtime footprint and malformed-input behavior before selecting the
production backend. Keep only one production writer initially.

The helper operates on a read-only source and a new private destination, never
on the original in update mode. Python owns budgets, eligibility, validation,
acceptance and publication. This fits the project's existing external-tool
pattern and avoids requiring a JVM or .NET runtime in the base Python package.
Self-contained .NET distribution remains an alternative if its qualification
results outweigh its packaging cost.

Do not assume that reading and writing a high-level document model is lossless.
Apache specifically documents limited/incomplete HWPF functionality and possible
invalid outputs in its [Word component documentation](https://poi.apache.org/components/document/).
LibreOffice or Microsoft Office resaving can be an experimental comparison, but
cannot establish the default stream-preserving contract.

## Eligibility and detection

Start with CFB version 3 and tested Office 97–2003 profiles. Version 4 is inspected
and reported as unsupported until its writer/application fixtures are qualified.
Preserve the input version; never select a writer's default version implicitly.

1. Verify CFB magic `D0 CF 11 E0 A1 B1 1A E1`, header consistency, allocation
   chains and a complete directory graph within operation limits.
2. Match a known document profile: DOC's `WordDocument` and selected table stream,
   XLS's BIFF8 `Workbook` and record boundaries, or PPT's `PowerPoint Document`
   and `Current User` with a valid edit/persist chain. Extensions only suggest a
   profile; RTF/HTML/XML/raw-BIFF files with Office suffixes are not CFB candidates.
3. Establish protection status using the relevant format structures. For DOC,
   inspect [FibBase encryption flags](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/26fb6c06-4e5c-4778-ab4e-edbf26a545bb);
   for XLS, inspect [FilePass](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/cf9ae8d5-4e8c-40a2-95f1-3b31f16b5529);
   for PPT, inspect the [UserEditAtom encryption reference](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/3ffb3fab-95de-4873-98aa-d508fbbac981).
4. Check document signatures, VBA signatures and rights-management structures.
   Include `_signatures`, `_xmlsignatures` and actual control-character-prefixed
   storage names. A simple filename/string search is not a complete protection
   check. See [binary document signatures](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-offcrypto/2770c801-5f0f-4326-89e8-d6ef15b68ef1)
   and the [MS-OFFCRYPTO index](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-offcrypto/9d9cebee-a465-4c2f-a4df-d9ae83be5d77).
5. Skip protected files or unknown protection status. Encrypted OOXML wrapped in
   CFB (`EncryptionInfo` / `EncryptedPackage`) is a different profile and is not
   a way to enable the existing ZIP walker. Unsigned VBA can stay opaque only
   after the signature/protection gate for that profile has been qualified.

This conservative gate is a product choice, not a claim that container compaction
must invalidate every signature or cannot physically compact encrypted streams.
Stream equality alone does not constitute signature validation.

Other CFB applications, such as MSG, VSD, PUB, MSI/MSP, AAF, SUO and Thumbs.db,
are investigation targets. A valid CFB container does not prove that an arbitrary
application tolerates relocation of entries/sectors. Add their writer profiles
only after format-specific validation and fixture evidence. Do not add a generic
rewrite fallback for every file starting with CFB magic.

## Compaction and verification

Construct a manifest before writing. For each object retain its exact parent
path/name and type. For storages retain CLSID, state bits and recorded FILETIME
values; include root metadata and empty storages. For streams retain length,
SHA-256 and relevant directory fields. Keep names as CFB components, not host
filesystem paths; avoid normalization, truncation or case folding of stored
names. Microsoft defines these fields in the [directory entry specification](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/60fe8611-66c3-496b-b70d-a504c94c9ace).

Copy all live stream bytes, including unfamiliar streams. Restore recorded
metadata after copying, since creation/writes can update timestamps. Preserve
zero/unrecorded timestamps exactly; round-tripping through a datetime conversion
must not silently change FILETIME precision or an absent value.

Rebuild the allocation layout without redundant capacity. The root mini stream
is a physical carrier for small streams, not an ordinary application stream:
compare its contained logical streams, not its raw physical carrier bytes or
physical carrier length. Physical sector IDs, directory IDs, sibling links,
colors and allocation tables may change subject to structural validity and the
qualified document profile.

Candidate acceptance requires:

- Complete header, FAT/DIFAT/MiniFAT and directory validation, including cycles,
  overlaps, out-of-bounds links, ownership, supported name ordering and tree
  structure. Reject unreachable allocated objects and unexplained allocation;
  never interpret a parser's partial enumeration as permission to drop content.
- Independent reopening and comparison of every logical object, field, stream
  length and hash. `olefile` is a useful second reader, but needs complete
  directory-field/graph coverage; supplement its API where necessary. A writer
  exit code or successful opening alone is insufficient.
- Rechecking the Office profile's required streams and structural references.
- Passing the existing minimum-savings/size policy and dry-run/publication rules.
  Under default policy, an equal/larger candidate leaves the source unchanged.

Integrate as `pack_ole()` in `filerepack/ole.py`, with structural and preservation
verification in `filerepack/ole_verify.py`, then register dispatch and aliases.
Use `guard_packer` and `commit_output(..., verify='ole', lossless=True, ...)`.
Exact inspection/outcome/budget interfaces follow their shared pending proposals.
Initially archive members with qualified Office extensions can use the same
standalone handler. Opaque `.bin` members, `vbaProject.bin`, compressed PPT
records and direct substorage transformations require later host-aware handling.

Budget source/candidate reads, aggregate stream bytes, entries, nesting, scratch
space and helper time. A limit hit or reader disagreement produces an explicit
skip/failure with an untouched source, not an unchecked fallback writer.

## Later recompression work

Prioritize identifiable compressed records with exact decoded-byte equality
before broader application-model resaving:

1. **PPT compressed OLE objects:** [ExOleObjStgCompressedAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/305e541f-2c91-49c5-a742-4955330fd2b9)
   contains an uncompressed length and an RFC1950 zlib-wrapped DEFLATE payload.
   Re-encode the identical decoded storage bytes with stronger DEFLATE settings;
   update record lengths and all affected position-dependent references. A later
   nested-CFB compaction changes those decoded bytes and needs a separate nested
   manifest contract. Do not mix the two forms of preservation.
2. **OfficeArt EMF/WMF:** the [OfficeArtMetafileHeader](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/ffdcc2b8-98fd-46b2-921e-6bb6693d05e5)
   specifies original/encoded lengths and DEFLATE or uncompressed storage.
   Preserve metafile bytes, geometry and identities, and update compressed lengths,
   containing records and references. This shared structure can eventually serve
   DOC/XLS/PPT, but each host still needs a qualified relocation adapter.
3. **PNG/JPEG OfficeArt data:** reuse existing image packers only for parsed BLIP
   payloads, after defining preservation of image samples/coefficients and required
   metadata. Maintain UIDs, references, display geometry, crop and color behavior
   according to the affected record types. Byte-signature carving is insufficient.
4. **Embedded document data:** distinguish direct CFB substorages, serialized CFB
   streams and wrappers such as Ole10Native. Parse wrapper lengths/fields and
   retain OLE class, presentation and link information. Recurse under one root
   budget with an explicit intended-change manifest.
5. **Application history/dead records:** defer. PPT can contain obsolete records
   inside a still-live stream, as illustrated by Microsoft's [persist object
   example](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/7bd57959-d49c-48a1-940a-bde37ec93c6f).
   Removing them needs complete reachability/reference analysis and an explicit
   history-preservation policy; DOC fast-save structures have analogous concerns.

XLS needs BIFF/CONTINUE/OfficeArt-aware record handling and offset repair; DOC
needs FIB/table/data and picture-reference handling; PPT needs record-tree,
Pictures-stream and edit/persist relocation handling. An OLE writer solves the
outer container only. VBA uses its own format-specific compressed structures;
exclude VBA recompression from this proposal.

## Qualification and rollout

Collect redistributable real DOC/XLS/PPT samples with provenance, supported
aliases, pictures, embedded objects, non-ASCII/control-character names, unknown
streams, property sets, empty objects and unsigned VBA. Include protected and
damaged samples expected to skip. Add controlled CFB fixtures for freed regular
and mini sectors, multiple FAT/DIFAT sectors, timestamps/CLSID/state bits,
mini-stream threshold edges and unsupported version 4.

Compare candidate size, stream totals, reclaimable allocations, runtime, peak
memory, fixture manifest equality and independent-reader results for pinned
backends. Separate inspection estimates from actual dry-run measurements.
Use the same pinned application/renderer before and after; opening must not
request repair. For XLS, include formulas, styles, charts, external links and
macro bytes, not just displayed cell values. Rendering is supplementary evidence
and never replaces the complete stream manifest.

Publish only the qualified subset; missing optional tools produce a documented
skip. Extend formats or start record-level recompression through a separate
proposal after the first pilot establishes both preservation and useful savings.

## Initial implementation and qualification record

The user authorized implementation on 2026-10-04. The production helper uses
`cfb 0.14.0` (MIT), a locked dependency graph and Rust 1.89+; the adapter adds
independent bounded Python graph validation and pinned `olefile 0.47` (BSD).
`OpenMcdf 3.3.0` (MPL-2.0, net8.0 qualification project) was compared on identical
inputs. Its `Flush(consolidate: true)` candidates changed root/storage CLSIDs,
state bits and FILETIMEs; embedded DOC candidates also failed the independent
empty-stream check. That invocation is unsuitable for the full preservation
contract. Only the Rust writer is a production backend.

The pilot contains 18 real Apache POI samples pinned by commit/hash/license:
9 eligible files and 9 protected/unsupported skips. All 18 Rust candidates
(9 originals and 9 controlled variants with allocation holes and metadata)
retained their complete logical manifests. All 9 original/candidate pairs
exported successfully in headless LibreOfficeDev 26.8.0.0.alpha0, commit
2c87e51eeaa2b413ff4ae097b2705eea1995d8e5, with macro security level 3; their
96-DPI Poppler page pixels were equal. This covers a PNG, embedded OLE objects,
formulas and a chart. It is supplementary renderer evidence, not a Microsoft
Office repair-dialog/interactive validation claim.

Original SampleShow.ppt reclaimed 512 bytes and ole2-embedding-2003.ppt reclaimed
2,560 bytes. The other seven original fixtures had no size reduction. Controlled
holes reclaimed 40,960–48,640 bytes; these are synthetic opportunities, not an
expected production savings percentage. Exact sizes and single-run writer costs
are published in `dev/ole/qualification.json`; peak memory was not measured.

The initial gate skips all VBA-bearing files because unsigned-VBA protection
qualification is deferred. It accepts CFB v3 minor versions 0x3B/0x3E, BMP names
with simple uppercase mapping, zero root creation time and storage entries with
zero stream allocation fields. Further valid variants can be conservatively
unsupported. CFB directory validation follows Microsoft's ordering/no-consecutive-
red rules; all-black unbalanced trees are valid and equal black-height is not
required by MS-CFB. Root directory color is not part of the preservation manifest.

Fixed limits are 128 MiB input/candidate and aggregate stream bytes, 8,192
directory slots, 32 storage levels, 128 directory traversal levels, 200,000
application records, 4,096 PPT edits and 120 seconds for the helper. The graph
bounds, immutable-stream checks and shared candidate transaction fail closed.
The optional executable's source/lock/licenses ship in the sdist; runtime wheels
contain Python integration only. Native platform CI is configured for Linux,
macOS and Windows with Python 3.9/3.13. Local execution is macOS arm64; platform
CI and Microsoft Office application tests have not been executed locally.

## Continued unsigned-VBA qualification

The user's “Продолжай” follow-up on 2026-10-04 authorizes qualification of unsigned
VBA within the original proposal's conditional gate. `filerepack/ole_protection.py`
now checks the actual host signature locations before permitting a canonical
root DOC `Macros` or XLS `_VBA_PROJECT_CUR` project. At that stage, unknown, embedded,
incomplete and PPT VBA layouts still skipped. The project streams, module code, caches, forms
and editor-lock/password metadata are copied opaquely; no VBA code is decoded
or executed, and document encryption remains a skip.

For DOC, pair 60 of FibRgFcLcb97 addresses StwUser in the selected table stream.
The parser checks the complete bounded names and parallel values, rejecting
`Sign`, `SigAgile` and `SigV3` regardless of project-storage presence. See
[MS-DOC StwUser](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/41981ee7-6f8d-4004-93de-0e897046a000)
and [FibRgFcLcb97](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/0c9df81f-98d0-454e-ad84-b612cd05b1a4).
For DocumentSummaryInformation, the parser validates the entire section/property
index and rejects `GKPIDDSI_DIGSIG` (ID 0x18) in the document-summary section.
The same ID in the user-defined section is an ordinary custom property. Unknown
sections, duplicate/overlapping/truncated indices, non-simple property storages
and unexplained stream padding fail closed. Property values remain opaque;
this checks signature presence rather than full typed-value conformance or
cryptographic validity. Existing Office unaligned string/vector property offsets
are preserved. See [MS-OSHARED signature locations](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-oshared/210c866a-8b2f-40ad-8db8-874130e1383a),
[DocumentSummaryInformation](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-oshared/3ef02e83-afef-4b6c-9585-c109edd24e07)
and [MS-OLEPS property-set streams](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-oleps/6e65d6fa-6044-4e23-ae71-d65d1e3b1249).

Each inspected StwUser table or property stream is limited to 4 MiB and 4,096
variables/properties. Required PROJECT/dir/cache streams must exist, and the
version-independent cache/container headers must be recognized; project internals
are not reserialized. See the [MS-OVBA cache header](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ovba/ef7087ac-3974-4452-aab2-7dba2214d239).

The expanded corpus has 21 real fixtures: 13 eligible, eight protected/unsupported.
The three actual unsigned-VBA projects are SimpleMacro.doc, SimpleMacro.xls and
external_name.xls. HeaderWithMacros.doc has no VBA project storage; SquareMacro.xls
remains unsupported because its root creation time is nonzero. All 26 native
candidates retain equal complete manifests, and all 13 real original/candidate
pairs render identically with the same pinned LibreOffice/Poppler environment
and macros disabled. The four newly eligible originals save no bytes; controlled
holes demonstrate reclaimable allocation space. The new measurements are retained
separately in `dev/ole/qualification-vba.json`; the initial pilot report remains
a historical snapshot. Interactive Microsoft Office and other-platform rendering
remain unqualified.

## PPT unsigned-VBA qualification

The next user continuation authorizes the remaining PPT unsigned-VBA protection
qualification in the original conditional scope. The first qualified variant is
a single user edit, one VBAInfoContainer directly in the current document's
DocInfoList, `fHasMacros=1`/runtime version 2, and a unique persist reference to
one top-level project storage. Multiple edits, duplicate references, misplaced
markers, empty/unknown project flags and unsupported project layouts skip.
Macro-free PPT profiles retain their existing edit-history support.

The referenced VbaProjectStg may use the recognized compressed RFC1950 wrapper
or uncompressed CFB bytes. Inspection bounds encoded and decoded project
bytes to 16 MiB, checks exact declared length, checksum/end-of-stream and absence
of trailing/concatenated data, then independently validates the nested CFB and
canonical root PROJECT/VBA/dir/_VBA_PROJECT layout. Host and nested signature,
encryption and rights-management markers remain disqualifying. No project is
recompressed, rewritten or executed: the native writer still copies the original
PowerPoint Document stream verbatim.

Primary sources: [VBAInfoContainer](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/ca0b2c2b-b1f8-4298-90bd-45296415f0a6),
[VBAInfoAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/93d20ef2-1514-43f9-901c-50c56d3a3073),
[compressed storage](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/03882002-995a-42f4-997c-e9d1dce888b1),
[uncompressed storage](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/ca12ee80-d3a6-424f-82ce-56a927669fed)
and [live persist-object discovery](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/1fc22d56-28f9-4818-bd45-67c2bf721ccf).

The implementation is in `filerepack/ole_ppt.py`. Persist entries must resolve
to preceding top-level records, with no duplicate identifiers within one index.
`ole_verify.independent_manifest` also accepts an in-memory binary reader so the
decoded project is independently checked without temporary extraction. Read-only
`OleInspection.unsigned_vba` records recognized project presence for the pilot.

The 21-file corpus now has 14 eligible originals and seven skips. The PPT stage
(`dev/ole/qualification-ppt-vba.json`) has 29/29 equal native manifests: 14 original
and 14 controlled-hole candidates, plus one fixture-derived uncompressed-wrapper
variant. All 15 renderer pairs are equal with macros disabled; the uncompressed
variant also matches the original compressed presentation's rendered pages.
SimpleMacro.ppt's compact original reclaims zero bytes; its controlled-hole
variant reclaims 41,984 bytes. The other original savings remain 512 and 2,560
bytes. Peak memory, interactive Microsoft Office and other-platform rendering
are not locally qualified. Regression coverage includes malformed wrappers,
bounded expansion, ambiguous references/history, nested protection/reader
disagreement and PPT VBA preservation inside nested ZIP archives.
