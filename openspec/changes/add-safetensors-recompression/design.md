## Context

Safetensors stores a little-endian header length, a JSON header with tensor
names, dtypes, shapes and data offsets, and a contiguous tensor-data region.
The corpus is large, but the survey did not test whether rewriting the header
or payload can save meaningful space without changing the format or model.

## Goals / Non-Goals

- Goals: establish a safe content parser, test real-file savings, and prove
  accepted output with independent native readers.
- Non-goals: quantization, dtype conversion, pruning, changing model tensors,
  wrapping the file in another codec, or claiming compatibility from suffixes.

## Decisions

- Treat the file as untrusted bytes. Do not load tensors into a framework or
  execute model code merely to inspect or verify a candidate.
- Bound header size, tensor count, dimensions, integer arithmetic, offsets,
  and total work. Require each tensor range to be in-bounds and consistent
  with its declared shape and dtype before considering a candidate.
- Keep tensor payload bytes exactly identical. Preserve tensor names, dtype,
  shape, and metadata. Any changed header serialization must still express the
  same complete mapping and pass the native reader matrix.
- Run an initial feasibility benchmark on complete real files from multiple
  projects. Include unchanged, unsupported, failed, and resource-limited cases.
  If no candidate clears the existing minimum-savings policy, leave the format
  inspection-only and do not register a writer.
- Publish only through the shared verified candidate and transaction path.

## Risks

- Tensor payloads may have no useful same-format compression path; header
  rewriting alone may be too small to justify a writer.
- Large or malformed dimensions and offsets can cause excessive allocation or
  integer overflow unless all calculations are bounded.
- Reader acceptance can vary by library version; an internal parser alone is
  insufficient evidence.

## Release Gate

Enable only individually measured profiles with byte-identical tensor ranges,
successful independent-reader checks, complete structural validation, and
real-file savings. Otherwise ship no Safetensors writer capability.
