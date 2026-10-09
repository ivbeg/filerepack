## Context

PyTorch DCP saves and loads state across multiple files and ranks and supports
load-time resharding. A valid input is therefore a complete checkpoint set
with metadata and shards, not an isolated shard. The survey counted many
objects but only two source projects and did not establish complete-set shape,
reader behavior, or savings.

## Goals / Non-Goals

- Goals: determine whether complete DCP sets can be safely inspected and
  losslessly recompressed as directory-level objects.
- Non-goals: per-shard extension handlers, changing rank/shard topology,
  rewriting model state, converting checkpoint formats, or unpickling
  untrusted state.

## Decisions

- Treat a DCP checkpoint as one logical directory/store. Require a complete
  inventory of its metadata and all referenced shards; missing, ambiguous, or
  unsupported layouts remain unchanged.
- Expand evidence beyond the current two projects and use complete real sets.
  Record DCP/PyTorch versions, layouts, outcomes, reader checks, storage use,
  and resource costs. If representative sets or meaningful savings cannot be
  established, end with inspection-only support and no writer registration.
- Never route an individual `.distcp` object through a generic file compressor.
  Keep passive inspection separate from framework state loading. Native
  validation uses generated trusted fixtures or controlled test checkpoints;
  arbitrary pickle globals are never invoked.
- Preserve checkpoint metadata, shard contents, rank identity, and state
  representation. Any candidate must pass DCP load and reshard checks for the
  tested topology before it can be considered.
- Stage and publish the complete output directory atomically using shared
  size, resource, cancellation, and transaction policies.

## Risks

- DCP internals and storage readers can vary by PyTorch version and backend.
- A generic byte rewrite may break metadata/shard agreement or load-time
  resharding even if each individual file remains readable.
- The currently observed two-project corpus may not contain representative
  complete checkpoints.

## Release Gate

Do not register a writer unless complete sets from independent projects show
accepted real-file savings, exact stored-state preservation, native DCP load and
reshard success, and atomic whole-directory publication. Otherwise retain
inspection-only results and no `.distcp` writer.
