> Implementation and current evidence: [validation.md](validation.md). The checklist
> remains open until its full corpus/reader/platform requirements are met.

## 1. Establish source and backend coverage

- [x] 1.1 Acquire bounded real H5/NC files from multiple projects; record complete source
  identity, licenses/access conditions, sizes and backend versions.
- [ ] 1.2 Measure native candidates, all unchanged/unsupported inputs, memory/time and
  representative read cost without inferring gain from declared corpus bytes.
- [x] 1.3 Prepare graph/reference/user-block, datatype/attribute/order and all NetCDF-kind fixtures.

## 2. Extend HDF5

- [x] 2.1 Add bounded graph and typed-data manifests with reference-target comparison.
- [x] 2.2 Add backend capability checks, user-block retention and explicit unsupported-feature skips.
- [x] 2.3 Generate per-dataset lossless candidates without implicit type or reader-floor upgrades.
- [x] 2.4 Integrate semantic validation, budgets and shared transactional publication.

## 3. Extend NetCDF

- [x] 3.1 Detect source kind/model and constrain writer output to that same kind/model.
- [x] 3.2 Add raw typed value, dimension, group, attribute and fill/packing metadata comparison.
- [x] 3.3 Preserve verified storage geometry and reject quantization, unsupported types or no-fill states.
- [x] 3.4 Return an explicit unchanged reason for classic CDF formats requiring conversion.

## 4. Verify and document

- [x] 4.1 Exercise hard-link cycles, soft/external links, region references, committed
  types, NaN payloads, vlen data, unknown filters and corrupted/truncated inputs.
- [ ] 4.2 Verify trusted scientific-reader fixtures with auto transformations disabled;
  cover every advertised model and supported optional tool/platform combination.
- [x] 4.3 Exercise budgets, cancellation, changed source, missing verifier, larger
  candidates and destination failures; document narrowed support and measured results.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
