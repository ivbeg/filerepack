## Context

HDF5 is a graph with typed datasets, attributes, links and references, not a set
of arrays that can safely be copied through generic Python values. NetCDF adds a
specific scientific model and conventions on top of its storage. Compression and
format conversion are different operations: classic CDF formats cannot simply
acquire HDF5 compression while keeping their original kind.

## Goals / Non-Goals

- Goals: useful native lossless recompression with explicit preservation and budget evidence.
- Non-goals: schema rewriting, precision reduction, NetCDF classic-to-4 conversion,
  automatic application-format registration, external storage consolidation or live-store repacking.

## Decisions

1. Build a deterministic HDF5 manifest using graph identities rather than physical
   object addresses. Preserve hard-link equivalence classes; soft/external link
   text; object/region reference targets and selections; committed datatypes;
   dimension scales; attribute values/types and exposed creation order. Compare
   fixed-size numeric data bitwise and structured/vlen/string data with a typed
   representation retaining encoding, padding and special values. Never follow
   external links to rewrite external files.
2. Copy the entire HDF5 user block exactly. Preserve source format bounds and avoid
   native-type conversion, latest-format upgrades, link merge/prune, datatype
   normalization and lossy filters. Initial writers skip external raw storage,
   virtual datasets, unsupported reference types, encrypted/unknown filter pipelines
   and structures the verifier cannot fully compare.
3. Use inspected per-dataset lossless candidates. The initial backend profile uses
   built-in DEFLATE and supported lossless shuffle arrangements; changing a pipeline
   requires complete decoded and metadata equivalence. Preserve chunk shapes by
   default; compression of eligible contiguous datasets can introduce bounded
   chunks as an explicitly reported storage change. Do not rewrite an existing
   lossy/unknown pipeline or replace application-critical filter semantics blindly.
4. Backend discovery records executable/library versions, encoder/decoder support and
   maximum verified format bounds. Compare with a read-only HDF5 library adapter,
   not merely the successful exit status of the same `h5repack` invocation. Record
   the verifier's reader lineage; two wrappers of libhdf5 are not two independent
   implementations, even when their comparison paths are separate.
   Neither `H5TOOLS_BUFSIZE` nor a chunk row count alone is a hard operation-memory bound.
5. For NetCDF, detect `data_model` and on-disk kind and request that same kind explicitly.
   Preserve dimension order, unlimited status and lengths; groups; variable names,
   dimension bindings, raw dtypes/endian representations; attributes and typed fill,
   missing, packing and calendar metadata. Read with automatic masking/scaling and
   character/string transformations disabled. Compare raw values and float bits
   in bounded slices. Do not use a normalized CDL dump as the equality oracle.
6. NetCDF compression settings can change only under a profile whose storage changes
   are enumerated. Default keeps chunk geometry and existing compatible filters;
   eligible uncompressed variables can acquire built-in lossless DEFLATE/shuffle
   with reported chunks. Quantization, scale-offset rewriting, unlimited-to-fixed
   conversion and model promotion are prohibited. Unsupported user types or
   undefined/unwritten no-fill states cause a skip rather than inferred equivalence.
7. Apply shared candidate validation, budgets and publication after format-specific
   comparison. Large files are processed by bounded chunks/hyperslabs; account for
   variable-length data, backend caches, source/candidate passes and scratch growth.

## Risks / Trade-offs

- Structural validity does not prove graph or CF metadata fidelity; failure of any
  mandatory domain check rejects the candidate.
- A source created by an actively writing application has no stable snapshot guarantee.
  Require an offline file or stable snapshot; generation checks detect changes but are
  not represented as a general solution to concurrent scientific writers.
- Generic HDF5 preservation is necessary but insufficient for application schemas.
  MATLAB/AnnData/Loom claims require their own reader fixtures and feature scope.
- Compression may harm random-access speed. Keep chunk layout stable by default and
  report compression, elapsed time, memory and representative read costs with gains.

## Migration Plan

First upgrade existing handlers to fail safely when domain verification is missing.
Enable passing HDF5 and NetCDF-4 profiles independently. Keep classic CDF inputs
unchanged under ordinary repack. Document any narrowed previously implicit support
and retain the original file when a profile is unavailable.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.

NetCDF candidates use the native netCDF4 Python writer rather than `nccopy`; it
keeps the source data model, disables automatic transformations and retains
existing chunks, shuffle/Fletcher32 and packing/fill metadata.
