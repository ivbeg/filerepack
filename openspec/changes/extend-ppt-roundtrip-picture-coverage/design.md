## Scope and evidence

Qualify only additional standard immutable host forms needed to reach the existing
Pictures codec. The original has one edit and persist directory; isolated checks
of slide/master/optional-notes and embedded-object graphs pass. Complete host and
picture-consumer qualification, candidate preservation and rendering remain tasks.

The read-only report identifies these currently rejected forms:

| Record | Observed header/owner | Required audit |
| --- | --- | --- |
| 1058 RoundTripContentMasterId12Atom | version 0, instance 0, size 8; SlideContainer | Preserve logical master/layout IDs; reject wrong versions, lengths and owners. |
| 1054 RoundTripContentMasterInfo12Atom | version 0, instances 7–11; MainMasterContainer | Audit these additional layout-package instances and their relationship to immutable 1058 references. |
| 61722 OfficeArtColorMRUContainer | version 0, instance 2, size 8; OfficeArtDggContainer | Check the color array count/length and owner; it has no Pictures byte offsets. |
| 61730 OfficeArtTertiaryFOPT | version 3, instances 2 and 3; OfficeArtSpContainer | Reuse complete property-table bounds/reference accounting; preserve complex metroBlob package data. |
| 5000/5002/5003 shape PPT9 tags | version 15/15/0; OfficeArtClientData owner | Parse the named binary extension with the exact record-4012 form; audit its payload before admitting it. |

The 1058 master ID is 1 throughout the source and matches its immutable 1052
original-master ID. Layout references are 1 or 7 and corresponding 1054 instances
exist. This supports a targeted audit, not unconditional acceptance of all
round-trip data. The TertiaryFOPT tables pass existing consumer/bounds checks when
examined in isolation; expanding its admitted property count must not bypass them.

## Preservation and resources

Use the current Pictures-only replacement and intended-change contract. Document
stream length, all PPT record positions, persist IDs/offsets, edit chain and Current
User remain exact. Only the already enumerated FBSE size/delay fields can change.
Every selected PNG keeps exact samples and non-IDAT chunks; each unselected BLIP,
round-trip package, programmable tag, JPEG and unsupported PNG stays byte-identical.

The existing codec selects 13 PNGs with 8,971,836 sample bytes and uses 27,101,072
charged decode bytes during the isolated source/encoder experiment. All 13 shrink:
nine use qualified oxipng 10.2.0, four Zopfli 15 iterations. The trial uses unchanged
default budgets and writes no PPT. A final candidate must independently pass the
complete host verifier and improve the measured native compaction baseline.

Unknown extension forms must retain rejection. Admission is based on audited
semantics and checked structure; merely retaining an opaque prefix does not justify
skipping reference discovery. Do not extend compressed embedded-storage selection.

## Validation

Generate fixtures for admitted forms and mutate version, instance, owner, length,
property bounds, tag names/duplicates and reference targets. Check exact retention
of new immutable records and rejection of valid-looking candidate byte mutations.
Exercise native dry-run and explicit output, aliases, no-benefit cases and public
verbose/JSON diagnostics. Compare the original and candidate with an independent
slide/notes renderer and record actual whole-file savings and peak worker resources.
Keep private presentation bytes outside committed/generated test fixtures.

## Primary references

- [MS-PPT RoundTripContentMasterId12Atom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/e9a4f7c3-f3ac-4ba2-b94c-59a93f77d11b)
- [MS-PPT RoundTripSlideRecord](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/fe7a9588-d2e0-44d1-b9b1-ac2962592448)
- [MS-PPT ShapeProgTagsContainer](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/f8ad5874-193e-43f0-8400-246b29b606bf)
- [MS-PPT RecordType](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/38fb1fa5-0a62-477a-8b14-178df22de812)
- [MS-ODRAW OfficeArtDggContainer](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/dd7133b6-ed10-4bcb-be29-67b0544f884f)
- [MS-ODRAW OfficeArtTertiaryFOPT](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/a687e90c-1748-4f57-8758-be31cfb36185)

## Completed audit and implementation

The extended gate admits 1058 only as a version-0/instance-0, eight-byte direct
slide record. It binds its master ID to the unique original-master ID (1052) of
the live main master selected by SlideAtom, and its layout ID to a unique direct
1054 instance. Missing, duplicate or inconsistent identities reject the profile.
The trailing two unused bytes remain exact, without being interpreted as offsets.
Layout instances 1–11 are admitted; other instances remain outside this profile.

The color-MRU variant has two four-byte MSOCR entries, version 0, length 8 and a
drawing-group owner. The property-table variant admits counts 1–3, version 3 and
shape ownership, and always retains the existing sorted-property, complex-tail and
BLIP consumer checks. Complex metroBlob bytes stay immutable.

Shape tags require exact client-data and shape container headers and admit only
one `___PPT9` StyleTextProp9Atom of length 12 with all three PF9/CF9/SI masks zero.
This form has no optional bullet-image reference. Nonzero masks, additional runs,
duplicate names, other shape-tag versions and malformed framing still reject.
Document PPT9 and the existing PPT10/PPT12 forms retain their previous rules.

Additional audit sources:
- [MS-ODRAW OfficeArtColorMRUContainer](https://learn.microsoft.com/ka-ge/openspecs/office_file_formats/ms-odraw/3f5e4785-8128-48a4-b170-3442a2bbd46e)
- [MS-PPT RoundTripContentMasterInfo12Atom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/15e1aa89-93ac-4f24-8e0e-398ecec7897b)
- [MS-PPT PP9ShapeBinaryTagExtension](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/288d4b7c-200a-4fbf-bfcb-e60adba13db8)
- [MS-PPT StyleTextProp9Atom](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/b046e29f-7ff0-4ac6-9456-b014d812748f)
- [MS-PPT StyleTextProp9](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/fb67da92-7dd8-4964-9e44-b8b92291ee87)

Runtime evidence is in `dev/ole/qualification-ppt-roundtrip-runtime.json`.
The candidate saves 611,328 physical bytes (22.69%), including 5,632 bytes from
ordinary compaction and 605,696 additional bytes. The independent complete-host
verifier and all 11 slide/11 notes RGB pages agree. The worker uses 36,072,908
charged decode bytes, 85,032,960 peak RSS bytes and 21.47 seconds in this run,
within unchanged defaults. This is local macOS evidence; remote CI and Microsoft
PowerPoint opening/editing are not asserted.
