# PPT embedded-storage recompression design

Research and implementation date: 2026-10-04. Approved by the user and implemented;
the change remains pending release/archive.

## Context and evidence

The current `ole` preservation verifier compares hashes of every live stream.
Changing a zlib representation necessarily changes the PowerPoint Document
stream. Existing compaction and unsigned-VBA qualification do not authorize a
weaker verifier. This feature needs its own explicit, narrower equality rule.

Primary format sources:

- [MS-PPT published revision 10.1, 2024-11-12](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/6be79dde-33c1-4c1b-8ccc-4b2301c08662).
  The complete PDF was searched for stream-position fields; its SHA-256 is
  `4cdd467ceb57bb91aa40c2733b8d6f3408b41b4ed3b652270a73901487a9adf1`.
- [ExOleObjStgCompressedAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/305e541f-2c91-49c5-a742-4955330fd2b9)
  specifies a top-level storage wrapper with record version 0, instance 1,
  decoded length and RFC1950/RFC1951 data.
- [ExOleObjAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/a3517016-8e32-4585-9a42-adae02eea798)
  relates an object identity to a persist identifier; live object discovery is
  defined in MS-PPT 2.1.2. Parts 8–11 distinguish ActiveX, embedded, linked and
  VBA storages despite their shared storage-record type.
- [UserEditAtom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/3ffb3fab-95de-4873-98aa-d508fbbac981),
  [PersistDirectoryEntry](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/6214b5a6-7ca2-4a86-8a0e-5fd3d3eff1c9)
  and MS-PPT 2.3.2/2.3.6 define absolute offsets. Identifiers are not offsets.
  OfficeArt picture references use the separate Pictures stream, which remains
  unchanged. The standard-field audit is not proof about private extensions.

The pinned Apache POI fixture has three ordinary top-level objects, then two
compressed storages, one persist directory and one user edit. The objects are
embedded DOC and XLS, not VBA or linked/ActiveX data. Each has exactly one
ExOleObjAtom/ExObjRefAtom identity and a unique persist target. Its known
`___PPT10` extension payloads contain grid/time data. They were left byte-identical
in the experiment; production accepts only those explicitly audited tag shapes.

`dev/ole/ppt_record_pilot.py` accepts only this checksum-pinned fixture and its
encoding-only derivatives. It checks every surrounding byte and reference;
it cannot rewrite arbitrary user PPT files. A test-only CFB allocator stages
the experiment, followed by the existing native compactor. That allocator MUST
NOT become the production writer.

| Input | Compaction alone | zlib level 9 | Zopfli, 15 iterations | Additional Zopfli savings |
| --- | ---: | ---: | ---: | ---: |
| Real original, 40,448 bytes | 37,888 | 37,888 | 37,376 | 512 |
| Controlled zlib level 1 wrappers | 38,400 | 37,888 | 37,376 | 1,024 |
| Controlled zlib level 0 wrappers | 87,552 | 37,888 | 37,376 | 50,176 |

The real compressed payloads shrink from 2,615/2,590 bytes to 2,291/2,393 bytes
with Zopfli. Their decoded CFBs remain exactly 40,448/13,824 bytes. zlib level 9
saves 100 stream bytes, which does not cross a 512-byte sector boundary; Zopfli
saves 521 stream bytes, which does. Controlled variants demonstrate encoder
opportunity, not expected real-world savings. All six candidates pass fixture
intent/independent CFB checks and pixel comparison with LibreOfficeDev
26.8.0.0.alpha0 / Poppler 26.05.0, at 96 DPI with macro security level 3.
Microsoft Office interaction, wider corpus coverage and peak memory are unmeasured.

## Eligibility and relocation boundary

Start with the existing CFB version-3 PPT profile and protection gate, then
require exactly one edit and one persist directory. Previous-edit offset must
be zero; all persist identifiers must be unique, positive and within the seed
and standard maximum. Every target must be a preceding top-level record in the
same edit. Shared target aliases are unsupported in this first scope.

Resolve each selected storage through an ExOleEmbedContainer in the current
document's ExObjList and its ExOleObjAtom. Confirm the corresponding unique
shape ExObjRefAtom, supported subtype and independently recognized DOC/XLS
profile. Reject protection/VBA ambiguity in both host and selected nested CFBs.
No storage is selected by magic-byte search or by record type alone.

All selected compressed storage atoms must form the final contiguous object
block, followed immediately by the persist directory and final user edit.
Other application records stay at their original absolute positions. No dead
records are removed or rearranged. VBA, ActiveX, linked objects, multiple edits,
interleaved tail records and private/unqualified extension layouts are outside
the first gate. The record/extension allowlist must be documented with fixtures
and format-source evidence before production eligibility is enabled.

Build a map from original top-level record positions to their new positions.
Change exactly these fields:

| Location | Allowed change |
| --- | --- |
| Selected compressed storage | `recLen` and zlib data; decoded-size field stays identical |
| Persist directory | Each target's mapped absolute position; IDs, counts, ordering and other bytes stay identical |
| Final user edit | `offsetPersistDirectory`; previous edit stays zero, all other fields stay identical |
| Current User | `offsetToCurrentEdit`; every other byte stays identical |

Use checked unsigned-32-bit arithmetic and require every repaired reference to
resolve to the same logical object. Only smaller wrappers are substituted; equal
or larger encodings retain the original record. Sector rounding and the final
shared acceptance policy determine actual file savings.

## Preservation contract and verification

Add a distinct `ppt-ole` preservation contract; never weaken or reuse `ole`
hash equality to accept changed application streams.

The independent verifier reparses source and candidate, qualifies the same
layout, resolves objects by unchanged identity/persist ID, and checks:

1. All CFB objects, names, hierarchy, CLSIDs, state bits, raw FILETIMEs and empty
   storages agree. Every stream except PowerPoint Document and Current User has
   identical length and hash, including unknown streams.
2. The application-record prefix is byte-identical and remains at the same
   positions. No record is omitted, inserted or reordered. Header versions,
   instances, object identifiers, pictures, geometry and metadata agree.
3. Each selected wrapper decodes within a bound, with exact declared length,
   checksum, EOF and no trailing/concatenated data. Its decoded bytes and complete
   independent nested-CFB manifest agree exactly. Embedded document bytes are
   never compacted or reserialized in this mode.
4. The directory/edit/current-user records agree after replacing only the
   allowed offset values with the identities of their referenced records.
   Each actual offset equals its mapped value; missing or additional changes
   reject the candidate. Unselected wrappers remain byte-identical.
5. Both strict CFB readers agree, the host and nested protection gates still pass,
   and no transaction/budget validation is waived.

The experiment deliberately records `strict_ole_manifest_equal=false` for changed
encodings. Successful rendering supplements these checks; it cannot substitute
for them. Fault tests must show that a wrong persist/edit offset, changed decoded
object, unrelated stream, metadata field or extension payload is rejected.

## Writer, encoders and resource bounds

Python owns selection, reconstruction and intent verification. Extend the locked
Rust CFB helper with an explicit replacement mode limited to the two named root
PPT streams. It must copy every other stream and logical metadata exactly, use
bounded private input files, and advertise capability so an old helper is not
mistaken for a rewriting backend. Keep its existing compaction invocation intact.

The runtime transformation and verifier must share format definitions, not a
candidate byte buffer trusted as evidence. Test-only construction stays outside
the runtime. Publication happens only through the existing candidate transaction.

Use standard zlib level 9 everywhere. A stronger optional Zopfli pass selects
the smallest of the original, zlib and Zopfli representations. Zopfli's binding
is Apache-2.0; [0.4.3 requires Python 3.10+](https://pypi.org/project/zopfli/0.4.3/).
Qualify an older compatible binding for Python 3.9 or retain zlib-only operation
there. Do not raise the project's minimum Python version. Bind compression to
a killable worker rather than relying on interruption of a native in-process
call. No mandatory Zopfli dependency is added to base or ordinary OLE compaction.

Initial ceilings: existing 128 MiB CFB input, 8,192 directory entries, 32 levels
and 200,000 application records; additionally 64 selected objects, 16 MiB encoded
and decoded bytes per object, 64 MiB aggregate decoded storage, and 1 MiB maximum
input for each optional Zopfli call. Apply a 120-second overall transformation
deadline and shared worker memory/scratch budgets, not 120 seconds per object.
When limits or worker deadlines are hit, reject the recompression attempt and
retain the source or independently verified ordinary compaction candidate.

## Rollout and current boundary

The proposed option defaults to false and must survive standalone, bulk, worker
and nested-archive propagation. An unsupported recompression profile can use the
existing compaction path only if its own eligibility and strict verifier pass;
the result must identify the strategy actually applied. No less strict fallback
is permitted. Without a full-file size improvement, prefer verified ordinary
compaction rather than publishing changed records without a benefit.

The runtime gate/verifier and native stream replacement are implemented after
approval, with fault/transaction tests, expanded pinned fixtures, platform CI
configuration and user documentation. General PPT compatibility cannot be
inferred from one positive real fixture. Existing DOC/XLS compaction and opaque
PPT VBA support remain intact.

## Implemented record and extension boundary

`ole_ppt_records._VERSIONS` lists each accepted standard record type and its
audited `recVer`, including document/slide/master, text/environment, embedded
object, edit/persist and OfficeArt drawing records found in the pinned positive
fixture. All application-prefix bytes retain their absolute positions. Unknown
types or versions are rejected rather than treated as opaque relocation data.
MS-PPT revision 10.1 and its referenced MS-ODRAW definitions establish those
headers; the real fixture qualifies the allowed combination. Programmable
tags are additionally limited to `ProgTags` → `ProgBinaryTag` containing exactly
`CString(___PPT10)` plus a 16-byte `BinaryTagDataBlob`. That blob must contain one
8-byte `GridSpacing10Atom` (type 1037) or `SlideTime10Atom` (type 12011)
with version/instance zero. No private tag or arbitrary binary payload
is accepted. These header-only grid/time payloads do not contain stream offsets
([PP10DocBinaryTagExtension](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/70ef1f3c-eacd-4b42-bbb3-2f5035b4a0ed)).

The expanded 23-file corpus has 15 eligible compaction profiles and eight skips.
The additional real embedding fixture `testPPT_oleWorkbook.ppt` is strictly
compacted but its type 1058 remains outside record rewriting; another embedding
fixture is rejected for unknown VBA flags. Thus the rewriting boundary is a
general structural gate with one positive real layout and explicit negative
variants, rather than checksum-bound acceptance. `dev/ole/qualification-ppt-runtime.json`
records 33 equal native manifests, 18 equal rendering pairs and 11 public-API
PPT cases, including four record transformations and seven strict fallbacks.
Local application evidence is macOS LibreOffice only; CI is configured for
Linux/macOS/Windows Python 3.9/3.13, and interactive Microsoft Office is unmeasured.

Optional Zopfli is accepted only when installed metadata reports qualified
version 0.4.3; absent or other versions use zlib alone. Selected wrappers never
grow, and a physical-size tie prefers the strict compaction baseline. Shared
workers enforce root budgets, supervise private stream/candidate scratch, and
inherit the same overall 120-second deadline through candidate verification.
