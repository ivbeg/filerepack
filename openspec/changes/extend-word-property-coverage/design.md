## Qualification and preservation

The Word Data relocation and independent whole-host comparison already exist.
This change expands discovery only. The writer continues changing selected
BLIP encodings, containing lengths and resolved Data references. It retains all
other WordDocument/Data bytes, complete table streams, root/storage metadata,
private streams, unreferenced PICFs, revision data and zero padding.

The supplied `gov.doc` has ten selected PNGs in 89 Data blocks. Its styles contain
conditional character, paragraph and table formatting. It also has a shape-owned
OfficeArtTertiaryFOPT with scalar `dhgt`. The floating drawing store's empty
complex fill/line defaults are separately framed but do not select any payload.
The existing inline profile now qualifies the document without a new host writer.

## Offset-free Word operand audit

All additional ordinary operands below are bounded by their specified `spra`
length and retained verbatim. None contains a Data-stream offset. Conditional
operands are parsed separately rather than treated as arbitrary byte arrays.

| Family | Additional properties | Relevant meaning |
| --- | --- | --- |
| Character | `0800`, `0801`, `4804`, `6805`, `6817`, `4863`, `6864`, `CA89`, `2A83` | Revision flags, author indices, timestamps, revision IDs and property revision marks |
| Character | `6865`, `6877`, `2A0C` | Border, underline color and highlighting |
| Paragraph | `2431`, `2437`, `2438`, `2448`, `2405`, `2407`, `4439` | Pagination, East Asian spacing and font alignment |
| Paragraph | `6424`, `6425`, `6427`, `6428`, `6629`, `C64E`, `C64F`, `C651`, `C652`, `C653` | Legacy/current paragraph borders |
| Paragraph | `C615` | Tab-stop arrays; exceptional `cb=255` length computed from bounded deletion/addition counts |
| Table | `D613`, `D605`, `3404`, `3488`, `3489`, `D687` | Table borders, repeated row flag, style band sizes and style shading |
| Conditional styles | `CA85`, `C666`, `D66A` | Character/paragraph/table CNFOperand, only within table styles |

CNFOperand's condition must be one of the twelve specified single-bit values.
Its nested character properties use the existing offset-free style compatibility
profile; no special-character flags, picture/OLE identity, author/revision
identity or Data references are allowed. Nested paragraph properties exclude
Data references and preserved table/revision state. Nested table properties are
an explicit small set of permitted border/padding/indent/shading/band operands
and the six specified TCnf cell-border exceptions (`D47F`, `D680`–`D684`).
Unknown properties, recursive CNF, wrong property families and truncated operands
reject discovery. Every nested array is at most 253 bytes, so nested qualification
cannot evade the existing root graph budget or add unbounded recursion.

Observed Word style language/bidi fields remain in the existing byte-preserving
compatibility profile, including `CFBiDi` within the supplied table-style CNF.
They are retained without interpreting them as picture identity; this profile
qualifies preservation rather than certifying full document conformance.
New direct revision/highlight properties remain forbidden in inherited styles.
The conditional fields themselves are never flattened into the picture identity.

## Word-specific drawing properties

The shared parser enables these additions only for a verified DOC host:

- Scalar Protection Boolean (`007F`) and Shape Boolean (`033F`) properties require
  clear fBid/fComplex flags and remain exact.
- Complex `fillBlip` (`0186`) / `lineFillBlip` (`01C5`) defaults require a zero
  byte length. Empty complex operands own neither trailing bytes nor a store
  index; nonempty complex and scalar-index variants remain outside this addition.
- Tertiary `dhgt` (`03AA`) requires a shape owner, version 3, instance/count 1,
  a six-byte body and clear property fBid/fComplex. Its z-order value remains exact.

XLS/PPT shared-parser qualification and the deduplication property sets remain
unchanged. Private or other tertiary drawing consumers remain rejected.

## Primary references

- [MS-DOC character modifiers](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/7022285b-9621-42e9-ad4d-4e02c115ef18)
- [MS-DOC paragraph modifiers](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/484822ee-a9d9-4af4-8423-29fda67a6a58)
- [MS-DOC table modifiers](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/b39a6648-501c-4361-8366-4f042f579469)
- [MS-DOC conditional formatting](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/8c71d6a6-35dd-4462-9471-d376adebfe98)
- [MS-DOC character style restrictions](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/0188ecda-b590-4cb4-bb95-e76a47a9a2e2)
- [MS-DOC paragraph style restrictions](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/659f448a-473a-44c6-8b69-a25984af3645)
- [MS-DOC table style restrictions](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/eed2eef0-2943-4c2f-b348-3f1d1af59fdf)
- [MS-DOC exceptional tab stops](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/0fa864c2-4660-402f-b726-3e9895748a49)
- [MS-ODRAW tertiary property table](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/a687e90c-1748-4f57-8758-be31cfb36185)
- [MS-ODRAW protection flags](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/962b5499-8ae1-4375-baaa-a8a46b2e9bc6)
- [MS-ODRAW shape flags](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/aff4b132-455c-40bf-9639-e48a13e1cd5c)
- [MS-ODRAW z-order](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/b9da2bcb-13a2-4bcb-810e-c0557db3edf6)
- [MS-ODRAW fill image](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/df4c1209-6ed5-4cd5-b3de-f0a86618b018)
- [MS-ODRAW line fill image](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/06682cc4-76f6-4fd4-bf19-2ac35ca6a0ae)

## Evidence

The local public API report is
[`qualification-word-properties-2026-10-08.json`](../../../dev/ole/qualification-word-properties-2026-10-08.json).
It records source/candidate hashes, unchanged originals, complete independent
preservation, strict compaction baselines and equal 96-DPI page pixels (34 + 48
pages). The original user documents are not added to the redistributable fixture
corpus. Controlled regressions derive from licensed fixtures instead.
The related native OLE regression suite passed 427 tests. Ruff and mypy passed
for the changed runtime modules; changed tests and the qualification script also
passed Ruff. Strict change/spec validation and the canonical ownership audit
passed (186 canonical requirements and 287 audited source blocks).
Microsoft Office repair behavior and execution on other native platforms remain
unmeasured; this is local working-tree qualification, not release evidence.
