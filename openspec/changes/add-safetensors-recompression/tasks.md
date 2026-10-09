## 1. Feasibility and corpus

- [ ] 1.1 Collect complete Safetensors samples from independent projects and record provenance, sizes, versions, and resource limits.
- [ ] 1.2 Measure baseline payload/header composition and candidate same-format rewrites without changing tensor values or representation.
- [ ] 1.3 Record unchanged, unsupported, failed, and resource-limited attempts; stop writer work if no useful profile passes the release gate.

## 2. Inspection and preservation

- [x] 2.1 Implement bounded, content-based header and tensor-range inspection without loading model tensors.
- [x] 2.2 Reject malformed headers, duplicate names, invalid dimensions, overlapping or out-of-bounds ranges, and unsupported variants safely.
- [ ] 2.3 Compare all tensor bytes and metadata mappings before and after any candidate rewrite.

## 3. Qualified writer, if feasible

- [ ] 3.1 Implement only the measured profile and register only its exact supported variants.
- [ ] 3.2 Verify outputs with independent Safetensors readers and structural checks.
- [ ] 3.3 Integrate with shared size acceptance, resource budgets, transactional publication, and protected archive routing.
- [x] 3.4 Document reader/version coverage and inspection-only behavior for unqualified files.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
