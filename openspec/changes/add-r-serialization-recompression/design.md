## Context

RDS contains one serialized object; RData/RDA has an additional workspace header.
Recreating objects through R or a dataframe converter can change serialization,
attributes, reference identity, or package-specific values. Recompressing the same
stream avoids that conversion. Native R supports several wrappers, but a wrapper
change can raise reader requirements even when the serialization version stays fixed.

## Goals / Non-Goals

- Goals: preserve decoded bytes, reader requirements by default, and source safety.
- Non-goals: resaving objects, serialization-version upgrades, zstd, ASCII/native-endian
  serialization in the first release, repairing invalid objects, or evaluating packages.

## Decisions

1. Detect the envelope and then inspect the decoded header. The initial profile accepts
   XDR version 2/3 RDS and matching RDX2/RDX3 workspace streams. Validate the complete
   supported serialization grammar with a passive parser: lengths, nested records,
   reference indexes, declared encodings, and complete consumption. Unknown record
   types, including unsupported ALTREP representations, produce a reasoned skip.
   Do not infer full-file validity from a serialization-version header or `infoRDS`.
2. Decode and compare in bounded streaming passes. Retain every serialization byte,
   including the workspace header; never call `readRDS`, `load`, `pickle`, or an
   object constructor on user input during packing or verification. Native R is an
   integration-test reader for trusted fixtures only.
3. `preserve` retains the source wrapper, including an uncompressed source. Explicit
   `gzip`, `bzip2`, or `xz` opts into that wrapper's documented reader requirements.
   Record the source/target codec and tested reader floor. `--lossy` and `--allow-grow`
   do not select a codec or relax preservation. An uncompressed input in preserve
   mode can be recognized and returned unchanged.
4. For gzip-to-gzip preserve filename, comment, timestamp and other understood
   non-derived header fields; recompute integrity fields. Reject unsupported header
   extensions or trailing/concatenated envelopes in the initial profile. Switching
   away from gzip must preserve meaningful header metadata through an equivalent
   supported representation; otherwise skip, even with explicit codec selection.
5. Evaluate bounded encoder candidates, independently decompress each, compare exact
   streams, and apply the shared size/minimum-savings policy. Decoded equality includes
   signed zero, NaN payloads, encoding marks, attributes and reference records by
   construction. It does not establish that arbitrary source objects can be executed.

## Risks / Trade-offs

- A passive parser is more work than a header probe; a narrow supported grammar and
  explicit skips avoid claiming universal R support.
- XZ may cost substantial memory/time; encoder dictionary memory and the verification
  pass must share the operation budget. Never silently retry with unlimited settings.
- Native-reader tests do not make untrusted deserialization safe; keep them confined
  to fixtures with recorded provenance and no unknown package hooks.

## Migration Plan

First reproduce the pilot with native R and multiple wrapper sources. Add the parser
and envelope writer behind experimental registration, then enable only verified
profiles. Missing verification support leaves the source untouched. Rollback removes
registration without changing previously accepted R object bytes.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.
