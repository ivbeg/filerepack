## 1. Implementation

- [x] 1.1 Retain failing xml:space/CDATA and high-precision/duplicate-key JSON reproductions as tests.
- [x] 1.2 Implement lexical JSON validation/minification covering scalar roots and rejecting non-finite literals.
- [x] 1.3 Implement context-aware XML preservation and deterministic hardened parsing.
- [x] 1.4 Test inherited xml:space, mixed content, namespaces, entities, declarations, comments, and encodings.
- [x] 1.5 Exercise OOXML/ODF/EPUB nested parts and update minification guarantees.

## 2. Verification and documentation

- [x] 2.1 Compare XML text/tail and protected lexical regions and JSON token sequences exactly.
- [x] 2.2 Verify malformed/unsupported input does not replace sources.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate fix-markup-preservation --strict`.

## 3. Integration and rollout

- [x] 3.1 Reconcile the implemented canonical baseline through `update-quality-and-specification-gates` before integrating/archiving the delta; record deployment status separately.

Local verification on 2026-10-03: **445 passed, 1 skipped**, including **76 new markup preservation cases**. Ruff, mypy, all 25 strict OpenSpec validations, documentation and wheel builds passed. The wheel includes the updated markup module. Platform and package-specific guarantees beyond the exercised part-preservation paths remain separate roadmap work.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
