## 1. Feasibility and corpus

- [ ] 1.1 Identify complete DCP checkpoints and obtain samples from independent projects beyond the current two-project inventory.
- [ ] 1.2 Record metadata/shard layouts, PyTorch versions, storage backends, reader/reshard behavior, and resource use.
- [ ] 1.3 Measure bounded same-format candidates across complete sets and document unchanged, unsupported, failed, and limited cases.
- [x] 1.4 Stop writer work if complete-set compatibility or accepted real-file savings cannot be demonstrated.

## 2. Whole-set inspection and safety

- [ ] 2.1 Define content-based identification of supported DCP directory layouts and complete shard inventories.
- [x] 2.2 Implement passive metadata inspection without unpickling arbitrary checkpoint objects or invoking user code.
- [ ] 2.3 Add tests for missing/extra shards, rank mismatch, malformed metadata, unsupported versions, and resource limits.

## 3. Qualified whole-set writer, if feasible

- [ ] 3.1 Implement only a full-directory writer profile proven to preserve state representation and shard identity.
- [ ] 3.2 Validate complete outputs with controlled DCP load and reshard tests for documented versions/topologies.
- [ ] 3.3 Integrate protected routing, shared acceptance/budgets, and atomic directory publication.
- [x] 3.4 Document supported store layouts and ensure individual `.distcp` files remain excluded from generic compression routing.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
