## 1. Implementation

- [x] 1.1 Add registry/alias/validator/tool completeness tests against current routing.
- [x] 1.2 Introduce typed format metadata and derive legacy tables.
- [ ] 1.3 Validate executable overrides and probe versions/read/write capabilities with timeouts.
- [x] 1.4 Expose optional Python-extra availability and format diagnostic JSON.
- [x] 1.5 Declare/test TOML fallback on Python 3.9/3.10 and config precedence/errors/cache refresh.
- [x] 1.6 Generate support/tool tables and document unavailable/experimental cases.

## 2. Verification and documentation

- [x] 2.1 Nonexistent overrides must never report ok; unsupported CAB writers remain unavailable.
- [x] 2.2 Compare derived aliases/filters with current compatibility fixtures and generated docs.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate refactor-format-capability-registry --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
