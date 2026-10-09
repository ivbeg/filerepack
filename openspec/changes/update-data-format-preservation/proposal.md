# Change: Preserve data-file schema, metadata, framing, and SQLite snapshots

## Why

A real Parquet rewrite discarded custom metadata. Other data writers do not establish full schema/metadata/framing preservation and SQLite replacement has no offline/WAL policy.

## What Changes

- Preserve Parquet metadata alongside logical rows and schema.
- Define fidelity contracts for ORC, Avro, Feather, Arrow, HDF5, and NetCDF.
- Retain Arrow file-versus-stream framing unless conversion is explicit.
- Use bounded record batches and safe SQLite snapshot/offline policies.
- **BREAKING**: In-place SQLite replacement will require an explicit documented offline policy; sidecar-backed or detected live databases will use distinct snapshots or be skipped.

## Impact

- Priority: **P0**. Roadmap slice: **A6, C4**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R06, A6, C4.
- Affected capabilities: `data-preservation`.
- Affected code: `filerepack/repack.py:pack_parquet`, `filerepack/codecs.py:pack_sqlite/pack_orc/pack_avro/pack_feather/pack_arrow/pack_hdf5/pack_netcdf`, `pyproject.toml`.
- Status: early A6 partially implemented and verified locally on 2026-10-03 (Parquet preservation and batch verification); remaining scope is open. No deployment or archival is asserted.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Validation

- Use independent readers to compare values/schema/metadata and file-vs-stream form.
- Test SQLite WAL/writer snapshots and no in-place replacement of known live inputs.

## Approval and rollout

The user authorized implementation on 2026-10-02. The early A6 tasks are tracked separately from the remaining scope in `tasks.md`. Integration and deployment remain separate work. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
