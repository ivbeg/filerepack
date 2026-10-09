# Change: Investigate PyTorch Distributed Checkpoint recompression

## Why

The survey found 5,195 checkpoint-related objects totaling 1,060,930,025,723
declared bytes, but they came from only two projects and were not validated as
complete checkpoints. PyTorch Distributed Checkpoint (DCP) is a multi-file,
rank-aware store, not an independent `.distcp` file format. The current corpus
does not justify a per-shard writer or establish a compatible compression
mechanism.

## What Changes

- Establish how complete, versioned DCP checkpoint sets can be identified,
  inspected, validated, and published as a single logical object.
- Expand the corpus with complete checkpoints from independent projects and
  measure any same-format lossless recompression opportunity.
- Consider a writer only if full-set preservation, native DCP read/reshard
  behavior, real-file savings, and transactional publication are demonstrated.
- Do not register `.distcp` shard files as standalone recompression targets;
  do not deserialize arbitrary pickle or execute checkpoint-provided code.

## Impact

- Affected specs: `pytorch-distributed-checkpoint-recompression`.
- Affected code if feasible: directory-level checkpoint inspector, DCP-aware
  validator, protected routing, directory transaction support, registry and
  reporting, and test fixtures.
- Reuses shared resource budgets and structural-output validation. This is
  separate from `.pt`/`.pth` `torch.save` ZIP checkpoint handling.

## Evidence

- [Survey and checkpoint object inventory](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [PyTorch Distributed Checkpoint documentation](https://docs.pytorch.org/docs/stable/distributed.checkpoint.html).
- [PyTorch serialization notes](https://docs.pytorch.org/docs/stable/notes/serialization.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
