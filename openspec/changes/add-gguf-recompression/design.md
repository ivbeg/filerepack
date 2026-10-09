## Context

GGUF is a versioned binary model format with metadata, tensor descriptors,
aligned offsets, and tensor payloads. The format supports mmap-oriented
loading, multiple tensor types, and extensible metadata. The survey found
substantial volume but did not obtain a bounded sample for a structural probe.

## Goals / Non-Goals

- Goals: establish supported structural versions, quantify same-format
  lossless savings, and qualify native reader behavior before registering a
  writer.
- Non-goals: quantization/requantization, dtype or tensor-layout conversion,
  metadata edits, external compression wrappers, or model conversion.

## Decisions

- Parse headers and tensor descriptors passively with bounds on counts,
  dimensions, metadata lengths, arithmetic, alignment, and total work.
- Preserve each tensor's stored bytes, tensor descriptors, metadata values,
  version, byte order, alignment contract, and shard identity. Unknown or
  ambiguous versions remain unchanged.
- Include reader checks for supported llama.cpp/GGUF tooling and mmap behavior
  relevant to the proposed profile; a parser round-trip alone does not qualify.
- Measure full real files across more than one project. Record unchanged,
  unsupported, failed, and limited cases. If same-format rewriting cannot save
  accepted space, retain inspection-only support and do not register a writer.
- Treat a multi-file/sharded model as a set for qualification. Do not rename,
  repartition, reorder, or independently publish its shards without reader
  evidence for the complete set.
- Use shared staged verification, size acceptance, resource budgets, and
  transactional publication.

## Risks

- Most bytes may be quantized or otherwise poorly compressible, making a
  same-format writer unhelpful.
- Rewriting offsets or padding can break mmap assumptions even when tensor
  bytes are unchanged.
- GGUF versions and reader implementations evolve; support must be versioned
  and profile-specific.

## Release Gate

Register only profiles with measurable real-file savings, exact tensor payload
preservation, valid descriptors and alignment, and successful reader/mmap checks.
Otherwise keep the capability inspection-only.
