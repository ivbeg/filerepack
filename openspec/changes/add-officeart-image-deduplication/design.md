# Complete reference graphs before image removal

## Decisions

### Initial equality and store profiles

Begin with XLS/PPT shared BStores and any floating Word store separately enabled
by the coverage proposal. Do not turn inline Word PICFs into a shared store.
Group candidates by digest, then compare complete BLIP bytes and all relevant
FBSE fields, UIDs, names, type/tag and storage conventions; hashes alone cannot
establish equality. Differences are allowed only for the proven reference count,
size and location fields that are intentionally recalculated. Different metadata
or identity conventions prevent merging even if rendered pixels match.

Choose the first compatible entry as the canonical target and preserve retained
entry order. Never remove unreferenced/history entries as a side effect. Inline
complex-property BLIPs and delay stores are separate profiles; admit a delay
store only with complete referenced-byte coverage and relocation qualification.

### Reference completeness

Inventory ordinary picture IDs, print pictures, fills, line and side-specific
fills, complex OfficeArt properties and relevant host/drawing references. This
includes references on hidden/grouped objects, not just visible pictures. Each
field has a qualified index base, target kind and ownership. Update BStore entry
counts, source-index to retained-index mappings and FBSE counts according to the
specified reference semantics. Preserve anchors, shape IDs, crops, geometry,
color/effect settings, edit metadata and every unrelated byte.

Unknown/private/FOPT/FRT consumers, incomplete counts or ambiguous aliases reject
deduplication for that store; they are never assumed irrelevant. Host/Pictures
length and delay-offset repairs use the existing complete relocation contracts.

### Independent graph verification

The verifier independently reparses source/candidate, confirms each removed entry
has a byte-identical compatible retained target, and compares every consumer's
normalized image content/identity plus exact display metadata. It accounts for
all permitted count/index/length/location changes and every removed span. A
candidate cannot claim an entire drawing store as an unconstrained changed region.
Strict OLE continues to reject stream changes.

The new option alone authorizes deduplication, not image re-encoding. Other
explicit options produce separate candidates or a fully verified union. Shared
root budgets, candidate staging and final-file minimum-savings policies apply.
Existing macro/protection exclusions remain. Rollback disables this option.

## Qualification

Acquire real duplicates and generated controlled copies with pinned provenance.
Cover two/few/many consumers, fill/print references, hidden shapes, distinct crop
properties, mixed BLIP kinds, one/two UIDs and unsupported stores. Corrupt a
reference to another valid entry and ensure verification rejects it. Publish
removed counts, repaired reference counts, final savings, time/memory and reasons
for skipped stores; do not estimate savings from image counts alone.

## Primary references

- [OfficeArt BLIP reference families](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/c67b883b-8136-4e91-a1a3-2981d16e934f)
- [OfficeArt FBSE fields](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/2f2d7f5e-d5c4-4cb7-b230-59b3fe8f10d6)
- [Qualified host and placement analysis](../add-officeart-payload-recompression/design.md)
