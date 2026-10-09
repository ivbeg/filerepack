# Change: Investigate lossless ONNX recompression

## Why

The survey found 67 `.onnx` files totaling 14,185,202,708 declared bytes
across 13 projects, but did not inspect model graphs, tensor storage, external
data, or reader compatibility. ONNX can keep tensor bytes inside its protobuf
or reference external files, so a safe feasibility study must distinguish a
self-contained model from a multi-file model bundle.

## What Changes

- Add bounded, passive identification and inspection of ONNX models without
  executing the model graph.
- Measure same-format, lossless candidates separately for self-contained files
  and models using external tensor data.
- Enable only profiles with preserved graph and tensor representation,
  qualified ONNX readers, safe bundle handling where needed, and measured real
  savings. Other recognized variants remain unchanged.
- Exclude graph optimization, operator/opset changes, dtype conversion,
  quantization, and external archive wrapping.

## Impact

- Affected specs: `onnx-recompression`.
- Affected code if feasible: ONNX inspector/writer, external-data bundle
  resolver, registry and routing, transactional directory publication,
  verification, and tests.
- Reuses resource budgets, structural-output validation, and destination safety.

## Evidence

- [Survey and file inventory](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [ONNX external data format and loading](https://onnx.ai/onnx/repo-docs/ExternalData.html).
- [ONNX external-data security guidance](https://onnx.ai/onnx/repo-docs/ExternalDataSecurity.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
