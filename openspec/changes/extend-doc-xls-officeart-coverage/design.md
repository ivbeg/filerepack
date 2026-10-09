# Expanded host discovery without application resaving

## Context and scope

The encoder already handles eligible EMF/WMF. The missing work is proving that a
larger DOC/XLS layout can be resized without changing other content. Coverage
expansion does not compress text, numbers or formulas themselves. Existing
macro-bearing content-recompression exclusions remain in force even when strict
compaction accepts an unsigned project.

## Decisions

### BIFF8 relocation

Parse the complete Workbook stream into bounded record identities and substreams.
Classify known offset-free records separately from records owning references.
Audit cells/formulas, shared/array formula groups, row blocks, global settings and
string tables before admitting each profile. Preserve formula tokens, cached
results, shared-string order/indices, rich-text/phonetic data, numeric bit patterns
and all non-drawing record bodies except explicitly relocated pointer fields.

Preserve SST and its original CONTINUE boundaries/encoding transitions rather
than reserializing strings. Resolve BoundSheet starts, Index fields, DBCell
relative offsets and ExtSST record/interior-string pointers by target identity,
using each field's specified origin and unit. Refragment only drawing records;
recalculate every affected absolute or relative reference even when a field's
value happens to stay unchanged. Unknown offset-bearing families, charts/pivots,
external/control objects and unqualified future records keep the existing
explicit fallback. Adding one family requires evidence for its complete layout.

The single global drawing group may use one immediately adjacent second
MsoDrawingGroup instead of its first Continue (MS-XLS product behavior note 6).
Any subsequent fragments must be Continue. They are reparsed as one root;
multiple/nonadjacent groups are never inferred to be continuations. Worksheet
MsoDrawing fragment handling remains unchanged.

The qualified tertiary worksheet property profile is exactly OfficeArtTertiaryFOPT
version 3, instance 1, six-byte body and scalar Fill Style Boolean property
0x01BF with fBid/fComplex clear. Its value contains display flags, not host
offsets. Every worksheet drawing byte stays exact. Other tertiary properties
remain rejected. Deduplication still excludes all tertiary/private consumers;
payload recompression preserves store indices and does not remove images.

### Word references and mixed streams

Resolve character properties using FIB versions, text pieces, piece PRMs, styles,
character/paragraph FKPs and the specified inheritance order. Keep picture
locations distinct from binary Data references and OLE identifiers. Represent
each property operand's provenance and all of its consumers before patching a
shared/inherited operand.

Style inheritance applies to permitted formatting, not picture identity.
MS-DOC UpxChpx forbids properties preserved when sprmCIstd is applied, including
sprmCPicLocation, sprmCFSpec, sprmCFObj, sprmCFOle2, sprmCFData and revision IDs.
These fields must remain in direct character or piece-PRM formatting. The
previous synthetic style-owned picture location was a qualification error and
is now a rejection case; the positive style control inherits font size instead.

Admit nonoverlapping mixed Data regions only with a complete boundary/reference
map; preserve opaque islands and padding exactly. Identical aliases may share a
target when all consumers are resolved; overlapping interpretations remain
unsupported. For floating pictures, qualify FIB-addressed drawing stores,
OfficeArt references and all FIB/table offsets affected by relocation. Preserve
text, anchors, formatting, crop, geometry and editing metadata. Do not delete
unreferenced data, history or revision records to simplify allocation.

### Independent comparison

The writer emits a bounded ledger of changed payloads, container lengths and
pointer fields. A source/candidate parser independently reconstructs the graph
and permitted changes; it does not trust ledger declarations. Every byte outside
the approved spans and every normalized reference identity must match. A record
that cannot be classified rejects content recompression for the affected host;
the independently verified strict compaction candidate remains available.

## Qualification and rollout

Stage BIFF8 first, then inherited Word formatting, mixed Data and floating
drawings as separate qualified subsets. Existing fixtures remain regressions.
Add licensed real examples with populated strings, formulas, multiple row blocks
and each Word layout, plus controlled boundary/alias/corruption variants.
Benchmarks report eligibility, physical bytes beyond compaction, time, peak
memory and exact fallback reasons. Run installed-artifact and native integration
checks; application rendering supplements complete preservation comparison.
Rollback removes only the new qualification entries.

## Primary references

- [MS-XLS drawing group](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/43e0d496-45db-4f19-bb33-bcb2464aa83c)
- [MS-XLS workbook index](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/b06ea609-4ba2-4dab-9978-14e3b034706a)
- [MS-XLS ExtSST](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/5d981e62-9e25-490a-9a75-b177373e2d79)
- [MS-XLS product behavior, note 6](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/a3ad4e36-ab66-426c-ba91-b84433312068)
- [MS-ODRAW tertiary property table](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/a687e90c-1748-4f57-8758-be31cfb36185)
- [MS-ODRAW Fill Style Boolean Properties](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/baf2613d-c676-43c8-8077-828bdcc70dca)
- [MS-DOC character properties](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/7022285b-9621-42e9-ad4d-4e02c115ef18)
- [MS-DOC UpxChpx restrictions](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/0188ecda-b590-4cb4-bb95-e76a47a9a2e2)
- [MS-DOC direct character/piece formatting](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/be58bf9c-d1d3-40cc-91ee-36452d7939b2)
- [Existing primary-source host analysis](../add-officeart-payload-recompression/design.md)
