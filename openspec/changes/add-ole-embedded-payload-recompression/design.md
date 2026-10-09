# Parent and child preservation contracts

## Decisions

### Separate authorization and object profiles

The new flag is independent of ole_recompress. Existing calls retain every
embedded object byte, including the PPT wrapper pass's exact decoded-storage
contract. CLI/library/bulk/archive workers propagate the new option explicitly.
Lossy/quality/conversion options do not authorize lossy embedded-file work.
Honor effective parent category/member restrictions when selecting child packers;
the new option does not silently re-enable a disabled category in a descendant.

Qualify host object records and class/ProgID markers before selection. Distinguish
Word ObjectPool-style substorages and Excel embedded object records from links,
VBA, controls and unrelated storages with similar names. No execution or object
activation is used for inspection. Unsupported/protected children remain exact
and receive a per-object reason; a malformed parent/reference map rejects the
parent content candidate rather than selecting a guessed object.

### Three representations, separate reconstruction

1. Serialized native files in proven wrappers: parse payload boundaries, length
   fields, filenames/paths, label/flags, reserved fields and retained suffixes.
   Preserve every non-payload byte except exhaustive size/reference patches.
2. Serialized CFB streams: use the child operation's independent complete
   preservation contract; decoded child bytes may change only in this new mode.
3. Direct CFB substorages: construct a bounded logical child view preserving
   storage/stream hierarchy, names, CLSIDs, state bits, times and property bytes.
   A qualified native substorage operation must map this view back without
   replacing a storage with a serialized file or importing a synthetic root's
   metadata into the parent. Stage this after wrapped-file support.

Retain OLE class, CompObj/ObjInfo-style metadata, presentation caches, links,
icons and display geometry byte-identically. Initially reject a profile whose
cache/checksum/length coupling requires an unqualified cache regeneration. The
unchanged presentation must remain consistent with a content-preserving child
optimization; rendering alone does not establish this consistency.

### Child allowlist and cumulative budgets

Start with delivered child packers whose complete lossless preservation contract
can be evaluated in memory/private staging: strict CFB compaction, qualified
OfficeArt if explicitly requested, and qualified archive/OOXML preservation.
No generic extension-driven child acceptance or structural-only validators.
Enforce child source protection and dependency gates independently of the parent.

Every decode, extraction, recursive verification and process consumes the same
root depth/member/decoded-byte/memory/scratch/deadline context. Reject cycles and
ambiguous aliases; an object ID is not a filesystem path. Keep untrusted wrapper
names as metadata and use operation-generated private paths for staging. Optional
child codec absence leaves that child unchanged; exhausted budgets or cancellation
abort publication under the existing root policy.

### Parent intended-change verification

Independently rediscover objects in source/candidate, compare class/metadata and
normalized host targets, verify each changed child's declared contract, and
compare every unaffected storage/stream/record byte. A writer's manifest is a
bounded proposal, not proof. Native replacement uses a versioned allowlisted
substorage/root-stream interface qualified against the same complete manifest.

Keep strict compaction and other operation candidates. Compare final parent size
after allocation. Composition with OfficeArt requires union verification of
payload changes and all shared host offsets; otherwise compare separate candidates.
No new transformation is accepted by the old strict/PPT verifiers.

## Qualification and rollout

Deliver wrapped-file profiles, serialized CFB and direct substorages separately.
Acquire real examples with multiple objects, Unicode names, nested archives,
empty/property streams and retained caches. Fault tests cover size/suffix/class
changes, wrong-target IDs, child modifications outside its contract, substorage
metadata loss and cumulative limit bypass. Report per-object counts/reasons and
whole-parent size/time/memory. Rollback disables the new flag/profile entries.

## References

- [Existing OLE design and embedded representation analysis](../add-ole-container-compaction/design.md)
- [Existing exact PPT decoded-storage contract](../add-ppt-ole-record-recompression/specs/ppt-ole-recompression/spec.md)
- [Shared root budget proposal](../add-operation-resource-budgets/proposal.md)
- [MS-CFB structure](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/50708a61-81d9-49c8-ab9c-43c98a795242)
