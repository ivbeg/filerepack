## Context

Modern `torch.save` uses an uncompressed ZIP64 container with separately stored
tensor storage and pickle metadata, including alignment rules. Storage identity,
views and mmap behavior are part of useful checkpoint compatibility. A generic
ZIP reader accepting compressed members does not prove the framework reader does.

## Goals / Non-Goals

- Goals: exact checkpoint bytes within verified ZIP records and explicit load compatibility.
- Non-goals: deserialize user input, quantize, clone tensors, trim unused storage,
  rewrite pickle, convert to safetensors, or advertise compression based on size alone.

## Decisions

1. Phase zero tests generated trusted fixtures and provenance-reviewed real files
   against supported Python Torch and applicable LibTorch readers. Test STORED and
   DEFLATE separately for metadata and storage members, ZIP64, byte order, data
   descriptors, member order, CRC, offsets/alignment, ordinary load and mmap.
   Record successful and rejected methods; do not assume the framework accepts a
   method because Python `zipfile` does. A failed storage-DEFLATE gate removes that
   candidate from the proposal's implementation slice.
2. Classify a supported modern checkpoint using complete ZIP framing and an allowlisted
   record layout/version. Do not extract or execute `data.pkl`. Preserve its bytes
   and all storage/version/byteorder/serialization-ID bytes, member names/order,
   required header attributes and relationships. Reject ambiguous records, duplicate
   paths, encryption, signatures, TorchScript layouts and unknown layout extensions.
   Static format identification must not import arbitrary Python globals.
3. Default `preserve-mmap` accepts only tested source layouts and retains STORED tensor
   data, the declared alignment and mmap-compatible native-reader behavior. It can
   compress metadata members only if native reader gates prove that method/layout
   compatible. The resulting benefit may be small or zero; that is a valid outcome.
4. Explicit `load-only` may change storage member compression only when the tested
   target-reader matrix supports it. Report loss of mmap compatibility before writing
   via inspection/plan output and in the final result; do not rename the checkpoint
   format or change dtype/shape/strides/sharing. `--lossy`, `--allow-grow`, a high
   effort level or ordinary archive recursion never selects this mode implicitly.
5. Production verification passively compares complete decoded member bytes, integrity
   and supported layout under bounds; a separate read-only ZIP parser checks candidate
   framing. Native tensor/alias/stride/mmap checks are performed on trusted release
   fixtures, not arbitrary user checkpoints. Neither `weights_only=True` nor a
   subprocess alone is treated as a general safe arbitrary-input deserializer.
6. Dedicated checkpoint policy precedes generic ZIP handling for recognized content,
   including recognized unsupported checkpoint variants. An enclosing archive's
   ordinary member recursion must use this policy or copy that member unchanged.
   It must not recompress a checkpoint through generic ZIP options that bypass mmap policy.

## Risks / Trade-offs

- Default useful gains may be negligible because tensor payloads remain STORED.
  Report that clearly; a no-writer feasibility result is preferable to an untested claim.
- Tensor bytes can be incompressible even in a load-only profile. Measure a diverse
  real corpus and include unchanged/failing files and reader cost in the denominator.
- Compatible container methods depend on framework versions and reader implementations.
  An enabled profile has a concrete version floor and support matrix, not all-reader compatibility.

## Migration Plan

Complete phase zero before runtime writer registration. Enable only passing profiles,
keeping default mmap preservation and explicit load-only selection independent.
If none yields beneficial compatible real files, retain classification/inspection
and document the negative result; do not mark unsupported writer tasks complete.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.
