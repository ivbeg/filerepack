## Contract and audit

MS-PPT 2.8.1/2.8.2 describe the observed animation container and atom. Only the
bounded sound-free form is proposed; sound collections and unrelated unknown
extensions remain unqualified. Animation bytes are never changed.

MS-PPT 2.3.4–2.3.6 require unique persist identifiers and typed offsets. Storage
sharing must preserve distinct persist and external-object identifiers, rather
than redirecting ExOleObjAtom identities to one logical object. Verify all logical
references by expanding each persist ID to its complete unchanged wrapper.
No slide/master/notes alias may be admitted. Candidate sharing must be supported
by independent reader/render/editing controls before publication.

The supplied nested Photoshop CFB has consecutive red directory nodes. Only
immutable storage inspection may permit that color anomaly, with all allocation,
namespace, cycle and stream bounds still checked and independently cross-read.
The containing root remains strictly validated. Require the audited Photoshop
stream inventory, class identity and PSD header; arbitrary OLE subtypes remain
outside this sharing profile. Every nested byte remains unchanged.

Normalize only the existing FBSE fields, wrapper physical locations, persist
positions and edit/Current User offsets. Compare all other prefix bytes, consumer
properties, IDs, counts, ordering, nested data, pictures and outer CFB metadata.
Compose sharing with a verified existing image candidate through a fresh combined
contract, never accept a union of unverified patch masks.

## Primary sources

- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/a35de8fe-a76b-43fc-8e53-ebcff8843705
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/4361cc1f-cd51-4e61-a451-d252bf8e1069
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/d10a093d-860f-409c-b065-aeb24b830505
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/6214b5a6-7ca2-4a86-8a0e-5fd3d3eff1c9
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/a056484a-2132-4e1e-aa54-6e387f9695cf
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/a3517016-8e32-4585-9a42-adae02eea798

## Qualification outcome (2026-10-09)

A private native candidate retaining object IDs 24–30 and persist IDs 3–9, but
aliasing all seven storage offsets, shrank to 3,368,960 bytes. Apache POI 5.4.1
resolved only persist ID 9 (one of seven logical objects), both immediately and
after saving/reopening. Its offset-to-persist-ID map materializes one storage.
The source resolves all seven. This falsifies compatibility; runtime sharing,
alias masks, the nested-CFB exception and a new sharing verifier are excluded.
The final delta specifies retention/diagnostics, with exact duplicate sizes as
potential inventory only. No claimed saving includes the duplicate storage bytes.

The animation blocker also included PPT10 timing behaviors. Audit MS-PPT
2.8.34–36/44/49/61/62/69/70/82: checkerboard(across), setting visibility to visible,
style.visibility, shape visual targets, and integer node attributes 9/10/11/20.
All new fields and tags remain immutable; shape IDs are bound to their containing
page. This extends Pictures admission, never trailing-object rewriting.

Additional primary references:
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/8d75cc5b-6f80-4b2e-980b-a521e2691e54
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/498a5d0f-0725-4a06-a7de-7c67394e9146
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/f8876381-cf7f-4d2b-9888-965e2929c9dc
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/c53f2602-3854-4924-9a63-49400ec6255c
- https://raw.githubusercontent.com/apache/poi/REL_5_4_1/poi-scratchpad/src/main/java/org/apache/poi/hslf/usermodel/HSLFSlideShowImpl.java

## Fly-from-bottom audit (2026-10-09)

The supplied `opengovernment_rewired.ppt` contains thirteen AnimationInfoAtoms
with build/effect/direction/after-effect/text-build/OLE-verb tuple
`(1, 12, 3, 0, 0, 0)`, flags `0x4400` and no sound. MS-PPT 2.8.2 defines effect
0x0C/direction 0x03 as fly from the bottom of the slide. Admit only this additional
tuple; all existing header, owner, Boolean-flag, delay, order and sound checks
remain. Separate effect diagnostics name the rejected tuple.

PPT10 represents the same effect with TimeAnimateBehaviorContainer (61739),
TimeAnimateBehaviorAtom (61748), TimeAnimationValueListContainer (61759) and
TimeAnimationValueAtom (61763). MS-PPT 2.8.29-33/34-36 and the worked example in
3.7.2 describe the observed linear coordinate tracks. Admit exactly two ordered
keyframes at 0/1000: x retains `#ppt_x`; y moves from `1+#ppt_h/2` to `#ppt_y`.
Require calcMode/flags/valueType `(1, 0x38, 1)`, common behavior `(5, 0, 0, 0)`,
one matching coordinate name, empty formula variants, typed ordered children and
a unique live shape target within the page. No generic formula evaluator or
other fly direction is enabled.

The same host additionally needs bounded PPT9 StyleTextProp9 runs: each admitted
PF9 mask is zero, 0x02800000 or 0x03800000. Picture bullet references MUST be
0xFFFF (null); optional numbering fields are the observed none or `(1, 3, 1)`.
CF9/SI masks remain zero, each run consumes the node budget, and every byte must
belong to a complete run. Non-null picture bullets/unknown masks/truncation fail
closed. PPT10 document text defaults/master levels retain the exact observed
font-only tuple `(0x03000000, 0, 0xFFFF)`, five master levels and a unique font-0
target. The source uses the legacy 0xFFFF complex-script font sentinel; its bytes
are retained, never repaired or interpreted as a Pictures reference.

Three legacy main-master records are composite layouts linked by 1053 to the
one original 1052 master. Resolve every composite master and composite slide
to that live original, require a single non-overlapping layout instance, and
match the slide's legacy master. Original layout references keep their strict
1058/1052 binding. Unknown, missing, duplicated or conflicting graph identities
remain rejected. No record, layout package, tag, font, storage or animation byte
is in the Pictures write mask.

Independent qualification uses Apache POI 5.4.1 read/save/reopen, decoded ARGB
picture comparisons, full animation/tag serialization and embedded-object hashes.
LibreOffice source/candidate static slide/notes RGB hashes must match separately.
Static render equality does not measure animation playback; exact complete
animation/tag bytes and the independent reader are the dynamic-data controls.
See `dev/ole/qualification-ppt-opengovernment-fly-animation.json`.

Additional primary references:
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/bc65cd1c-14a7-4c0d-bc2d-192bab64a713
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/17969574-b32f-4ab0-b6d6-f5bb1a04f6fe
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/9177feba-1a81-40b8-950d-d1de63ae8ee7
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/be583d68-11d7-43c2-a300-8ef2ffac7841
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/13b03cf8-e193-4d7c-bece-efee91ea40bd
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/3e80f159-dab6-415d-a409-18ea6975b0c9
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/fb67da92-7dd8-4964-9e44-b8b92291ee87
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/72dd8636-450c-451f-a60d-9faddcff72be
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/43975b61-904e-46c3-8d4b-ec08ed1fcb22
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/77fea531-e839-4bc9-b813-7adc3f2adea0
- https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-ppt/ae0701f9-2b46-4b6c-90a0-49e7cfb20a7e
