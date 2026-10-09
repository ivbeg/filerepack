## Context

Truncated JPEG/PDF and arbitrary MP4/Arrow content pass current validators. The signed/encrypted PDF gate protects only the pikepdf step and allows later rewrites.

This design covers R09, B2 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Separate signature recognition, structural validation, and preservation validation guarantees.
- Goal: Require a declared structural validator for every publishable writer and fail closed when it is unavailable.
- Goal: Compare decoded lossless payloads and format-specific preservation contracts.
- Goal: Apply PDF protection gates before qpdf/pikepdf/Ghostscript and choose the smallest valid candidate.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Recognizing a header is discovery, not candidate acceptance. Unknown validator keys are errors, not true.
2. Use appropriate parsers, archive CRC/test commands, or decoders; record the level established by each adapter.
3. Lossless stream rewrites compare decoded payload hashes; structured formats compare their declared logical contract and intended changes.
4. Signed/encrypted PDF default policy is unchanged source bytes for every writer; uncertain protection detection fails closed. Signature removal/decryption is outside this proposal.
5. Retain original, walked, and qpdf candidates until evaluation; linearization is a separate explicit choice from compression and cannot hide a smaller eligible candidate.

## Risks / Trade-offs

- Deep verification can be expensive; apply shared budgets and make unavailable guarantees visible.
- PDF protection detection requires real fixtures beyond fake object dictionaries.

## Migration Plan

1. Preserve qpdf default and explicit Ghostscript quality/profile selection for unprotected PDFs.
2. Replace the completed stream-walking requirement's permission for qpdf on protected inputs after baseline reconciliation.
3. Keep legacy verify_output callable as a compatibility adapter but remove permissive unknown-kind success.

## Verification

- Every accepted corpus candidate must parse/decode and satisfy its declared preservation contract.
- Assert protected PDFs never invoke rewriting tools; missing verification must produce a visible nonpublication outcome.

## Local implementation boundaries

The compatibility `verify_output` delegates to typed `ValidationResult` adapters
in `verification.py`; `candidates.commit_output` requires an explicit key and can
add source preservation before the existing guarded publication boundary. Each
writer names a structural adapter. Reader/tool failure and unknown capability
produce a warning and refusal rather than successful header recognition.

Compressed streams compare decoded SHA-256; supported raster paths compare
frames/pixels and animation timing; Arrow/Feather/ORC compare schema metadata and
ordered values. Existing archive/Parquet/DICOM/native-format proofs remain in
place. Other data/media metadata and complete fidelity contracts are still open.
No media decoded-hash adapter is advertised as complete preservation while stream,
timing and metadata comparisons are missing.

PDF inspection checks all qpdf JSON objects (or dereferenced pikepdf objects when
qpdf is unavailable), including unreferenced protection markers. Warning/recovery
conditions fail closed. Lossless comparison canonicalizes the reachable document
and custom trailer graph, preserving decoded streams and image sample size/mode/
pixels while excluding known xref/encoding fields and volatile trailer IDs.
Unknown residual stream filters refuse acceptance. qpdf 11+ JSON is required for
lossless publication; pikepdf alone provides protection inspection.

Original and walked qpdf encodings remain available until validation/selection.
The original wins ties unless the user requires a different linearization state.
`pdf_linearize=False` is appended to `RepackOptions` to preserve existing positional
field order and is forwarded by CLI, library, AI and bulk/worker entry points.
For lossy linearization, the qpdf stage must preserve the Ghostscript stage.

Verifier subprocesses have capped output and a timeout; selected parsers also have
input/decoded-byte/frame bounds. These local bounds do not complete shared resource
budgets or bound all third-party parser allocations. PDF Flate-image/nested-form
expansion and application rendering guarantees remain separate work.
