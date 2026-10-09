# Change: Qualify PPT animation and exact embedded-storage sharing

## Why

The user supplied openbudget.ppt and openbudget.pptx. Their eleven common PNGs
are byte-identical, but the PPT Pictures gate rejects AnimationInfo records
4116/4081. The PPT also contains seven identical compressed Photoshop OLE
storages with distinct object/persist IDs, totaling 5,045,754 bytes. The PPTX
has one identical embedding. Simple removal or logical-object merging is not
sufficient to preserve editing and references.

## What Changes

- Audit and admit the observed sound-free AnimationInfo container/atom form for
  immutable Pictures processing, with strict headers, owners, fields and children.
- Audit sharing of complete byte-identical Photoshop storage wrappers while
  preserving every distinct object ID, persist ID, name, consumer and prefix byte.
- Isolate storage aliases to the new verified contract; ordinary compaction and
  existing record/picture contracts retain their respective equality rules.
- Preserve all nested storage bytes, including its observed legacy directory colors;
  never repair or reserialize the Photoshop embedding.
- Require independent complete-content/reference verification, application-reader
  compatibility, actual physical savings and existing root/transaction limits.
- Keep defaults and existing flags; the new transformation is reached only by
  the existing opt-in ole_recompress mode after successful qualification.

## Impact

Capabilities: officeart-recompression and ppt-ole-recompression. Runtime files:
PPT extension/host/art helpers, a dedicated storage contract, worker/verification
registration and orchestration. Generated regressions and local qualification
use private intermediates; the original PPT/PPTX remain unchanged.

## Authorization

The user requested this implementation with “Проделай эту работу” on 2026-10-08,
after reviewing the animation blocker, repeated embeddings and need to verify
references/editing behavior. This proposal records that authorized scope. Sharing
is eligible only if qualification supports preserved logical object independence;
otherwise it must retain the verified image/compaction candidate and explain why.
No release, deployment or archive is implied.

## Final qualified scope

The sharing experiment failed independent object resolution (one of seven in
Apache POI), including save/reopen. The final implementation therefore preserves
all separate storages and adds explicit duplicate-retention diagnostics. It does
not enable persist aliases, a nested-CFB color exception, or a sharing verifier.
Pictures admission includes the observed PPT10 checker/visibility timing forms,
with bounded typed structures and live shape references. This follows the approved
fallback above; the failed experiment is evidence, not a production capability.

## Authorized fly-in extension (2026-10-09)

The user requested verified support for the observed animation in
`opengovernment_rewired.ppt` with “Реализуй проверенную поддержку этого варианта
анимации”. This authorizes implementation without another approval round.
Extend the existing immutable Pictures profile to the sound-free legacy fly-from-
bottom tuple `(1, 12, 3, 0, 0, 0)` and its PPT10 linear x/y keyframe representation.
Audit accompanying PPT9 shape text runs with null bullet-picture references;
non-null picture bullets and other property forms remain outside this profile.
Also admit the host's exact PPT10 font-only document defaults/master levels and
resolve the accompanying composite master/layout/slide graph. This graph's delta
remains owned by `extend-ppt-roundtrip-picture-coverage`, avoiding duplicate live
requirement ownership.
Require generated malformed/mutation/reference controls, exact source/candidate
contracts and animation bytes, independent reader/save/reopen controls and equal
slide/notes rendering before reporting qualification. Preserve the supplied source.
