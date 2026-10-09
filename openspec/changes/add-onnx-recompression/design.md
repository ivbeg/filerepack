## Context

An ONNX model is a protobuf graph whose tensors may store raw bytes inline or
reference external data files by relative location, offset, and length. Large
models can therefore be a multi-file bundle. Re-serializing protobuf fields
can affect unknown fields or metadata, while following external paths creates
filesystem safety risks.

## Goals / Non-Goals

- Goals: identify safe model variants, test lossless same-format savings,
  preserve graph/tensors, and qualify standard ONNX readers.
- Non-goals: execute model operators, optimize or rewrite graphs, alter opsets,
  convert tensor types, quantize weights, or package models in another format.

## Decisions

- Inspect model structure passively under byte, recursion, tensor-count,
  allocation, and time limits. Never execute the graph as part of routine
  inspection or candidate verification.
- Separate self-contained models from external-data bundles. Treat external
  references as untrusted: reject absolute paths, traversal, escaping symlinks,
  and unresolved files. Do not rewrite or publish a bundle piecemeal.
- Preserve the graph, opsets, functions, metadata, tensor names/types/shapes,
  and tensor payload bytes. Verify both structural validity and reader loading
  using qualified ONNX tooling; use path-based validation for large external
  models where required by the reader.
- Benchmark complete real files and bundles. A single-file writer may be
  enabled independently if it passes. External-data support stays unchanged
  until whole-bundle verification and transactional publication pass.
- If no same-format rewrite yields accepted real-file savings, provide
  inspection-only results and do not register a writer.
- Publish model bundles atomically through a staged directory transaction and
  the shared resource/size policies.

## Risks

- Tensor payloads may be incompressible in the ONNX representation; graph
  reserialization alone may not yield useful savings.
- Unknown protobuf fields may be lost by a parser/writer that does not retain
  them, even if a basic checker accepts the model.
- External-data references can enable traversal or unintended reads/writes
  unless every path component and link is checked.

## Release Gate

Qualify self-contained and external-data profiles separately. Require exact
tensor payloads, preserved model structure/metadata, ONNX reader checks, accepted
real-file savings, bounded execution, and complete transactional publication.
