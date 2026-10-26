## MODIFIED Requirements

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
