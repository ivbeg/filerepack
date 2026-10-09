## Context

Zarr is a key/value store. A compressor declaration applies to an entire array;
individual chunks cannot independently select a different codec configuration.
Consolidated metadata is a cache of those declarations. Its consolidation version
is separate from the Zarr storage version. The current transaction pipeline stages
and publishes regular files, not multi-object directories.

## Goals / Non-Goals

- Goals: consistent local v2 recompression with exact decoded bytes and safe whole-tree publication.
- Non-goals: in-place replacement, live writer coordination, remote storage, v3 migration,
  rechunking, dtype conversion, changing filters, or processing chunks as separate bulk jobs.

## Decisions

1. Require an explicit local directory root with valid v2 `.zgroup`/`.zarray` content.
   Acquire a complete key manifest of an offline store or stable snapshot before work.
   Reject links, special files, path escapes and key collisions under destination
   filesystem rules. Copy auxiliary files unchanged. Record file generations and
   recheck the source, while documenting that this is not a live-writer snapshot protocol.
2. Initial arrays use fixed-size non-object dtypes and `filters=null`. Accept only
   an allowlist of tested built-in Numcodecs configurations; never resolve arbitrary
   codec classes from metadata. Unknown filters/codecs or version mismatches cause a
   whole-store skip in the first release. Default candidates retain codec family and
   compatible algorithm; increasing compression effort is allowed after verification.
   Leave uncompressed arrays unchanged initially. Algorithm changes such as LZ4 to
   Zstd require explicit `zarr_codec_policy=compatible-upgrade`, tested target-reader
   support and a reported compatibility change; CLI exposes `--zarr-codec-policy`.
3. Compare the exact decompressed bytes of every stored chunk, including edge padding,
   with unchanged dtype, byte order, shape, chunk geometry and C/F layout. Preserve
   the set of missing chunks and fill semantics; do not synthesize zero-filled chunks.
   Keep attributes and auxiliary payloads byte-identical. Only selected compressor
   objects in array metadata and matching existing consolidated entries can change;
   preserve all other fields and unknown extension values without numeric coercion.
4. Candidate decisions are per array, not per chunk. Generate and verify all its chunks
   under one compressor declaration or retain that whole array. Select using total
   array bytes including metadata, then evaluate complete-store bytes including the
   consolidated metadata and auxiliaries against the shared minimum-savings policy.
   Copying unchanged chunks/arrays is part of the output cost and scratch budget.
5. Preserve whether consolidation exists. If present, check its consistency with the
   individual metadata first; reject a stale/ambiguous source cache. Change matching
   compressor declarations together and verify both ordinary and consolidated reads.
   `zarr_consolidated_format=1` does not imply Zarr storage v1.
6. Create a private staging directory under the output parent on the destination
   filesystem. `repack-store` requires `--output-dir`; destination is
   `PARENT/basename(SOURCE)` and must be disjoint from the source and absent. No
   `--overwrite` support in v1. Verification and source-generation checks precede
   publication. Directory publication requires a tested atomic no-replace primitive
   for that platform/filesystem; ordinary rename that can overwrite an empty directory
   is insufficient. If this guarantee is unavailable, fail safely before publication.
7. Preserve required relative-file metadata under the project's filesystem-attribute
   policy. Cleanup removes only operation-owned staging paths, never user trees.
   Report logical stored-byte sums, file/chunk counts, per-array codec decisions and
   verification status. Do not label logical savings as allocated filesystem savings.
8. Ordinary `bulk` remains file-oriented and does not gain implicit store discovery.
   A future store-aware bulk change must own each root once and exclude its objects
   from ordinary jobs. The new command does not promise that unrelated bulk invocations
   automatically recognize Zarr roots.

## Risks / Trade-offs

- A distinct output requires space for a full copy; estimate and enforce scratch/output
  budgets before and during writing. Large incompressible arrays can make no-benefit
  attempts expensive; report measured costs and clean rejected staging.
- Store-level atomic publication depends on platform/filesystem support. Test native
  no-replace behavior and collision races on macOS, Linux and Windows; advertise only
  validated combinations rather than a portable overwrite guarantee.
- A partial listing cannot distinguish an intentionally missing chunk from an omitted
  download. Only a complete user-provided root is eligible; the survey tree is not a fixture.

## Migration Plan

Implement directory lifecycle independently of existing `repack`/`bulk`. Establish
complete-store baselines and codec reader matrices, then enable local v2 profiles.
Rollback removes the new command/registration without modifying sources.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.
