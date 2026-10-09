---
title: "Model weight formats"
description: "Inspection limits and writer status for Safetensors, GGUF, ONNX, and PyTorch DCP"
---

# Model weight formats

filerepack recognizes Safetensors, GGUF, and ONNX files and reports bounded
structural details during `repack`. These profiles are inspection-only: no
lossless same-format writer has passed the native-reader and real-file savings
gates. The source is left byte-for-byte unchanged. Quantization, dtype changes,
graph optimization, model conversion, and wrapping files in another codec are
not performed.

Safetensors inspection reads only its bounded JSON header and checks tensor
names, known dtypes, shapes, offsets, non-overlap, and payload coverage. It does
not load or hash the model weights.

GGUF inspection reads a bounded prefix and validates supported versions,
metadata framing, common tensor types, tensor ranges, and alignment. GGUF
quantization types outside the inspected table remain unchanged with an
unsupported reason. Tensor payloads are never loaded or decoded.

ONNX inspection requires the optional `onnx` extra. It parses models up to the
configured in-memory inspection limit and runs the ONNX checker only for
self-contained files; it does not execute the graph. External tensor locations
are checked for path traversal, symlinks, missing files, and invalid ranges,
without loading sidecar bytes or claiming reader validation. Large models beyond
the limit, unsupported sidecar layouts, and models without the optional
dependency remain unchanged. Install the reader with:

```bash
pip install 'filerepack[onnx]'
```

PyTorch Distributed Checkpoint (DCP) is a directory-level format. Inspect a
flat local filesystem checkpoint without deserializing its metadata:

```bash
filerepack inspect-dcp /path/to/checkpoint --json
```

The command inventories `.metadata` and rank shard files as opaque files. It
does not parse the pickle-based metadata or claim that the shard set is
complete. Nested layouts, symlinks, special files, individual `.distcp` shards,
and DCP recompression are unsupported. Do not use this inventory as a native
load or checkpoint-integrity check.

The current corpus and compatibility evidence do not qualify same-format
writers for these four formats. Recompression will be enabled only after full
real models/checkpoint sets demonstrate accepted savings, exact tensor/state
preservation, independent native-reader success, and the required whole-set
publication guarantees.
