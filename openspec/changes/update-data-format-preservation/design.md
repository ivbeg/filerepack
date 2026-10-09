## Context

A real Parquet rewrite discarded custom metadata. Other data writers do not establish full schema/metadata/framing preservation and SQLite replacement has no offline/WAL policy.

This design covers R06, A6, C4 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Preserve Parquet metadata alongside logical rows and schema.
- Goal: Define fidelity contracts for ORC, Avro, Feather, Arrow, HDF5, and NetCDF.
- Goal: Retain Arrow file-versus-stream framing unless conversion is explicit.
- Goal: Use bounded record batches and safe SQLite snapshot/offline policies.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Deliver the reproduced Parquet metadata fix first; implement remaining writer contracts and streaming in separate follow-up slices.
2. Choose a writer that can preserve the input contract; reject unsupported metadata/schema cases rather than silently discard them.
3. Read/write record batches where supported; formats needing whole-file work must advertise resource requirements.
4. SQLite snapshot output is distinct from replacing a live file; reject known WAL/SHM or active-writer cases in place and require explicit offline acknowledgment. Do not claim all open connections can be detected.

## Risks / Trade-offs

- Schema metadata is format-specific; compare logical schemas and declared required metadata rather than raw compression layout.
- VACUUM can affect implicit row identities; preserve application-visible identifiers or skip cases whose contract cannot be established.

## Migration Plan

1. Keep existing extension and extra names and public helper imports.
2. Document the SQLite policy and distinguish snapshot outcomes from in-place replacement.

## Verification

- Use independent readers to compare values/schema/metadata and file-vs-stream form.
- Test SQLite WAL/writer snapshots and no in-place replacement of known live inputs.

## Early A6 implementation notes (2026-10-03)

Parquet now uses PyArrow 19+ instead of DuckDB COPY. The original physical and
logical schemas (including nullability, nested field names and identifiers),
file/schema/field metadata and ordered values must compare before publication.
The writer keeps the source format version and restores footer key/value metadata
with [ParquetWriter.add_key_value_metadata](https://arrow.apache.org/docs/19.0/python/generated/pyarrow.parquet.ParquetWriter.html),
including the original serialized `ARROW:schema`. Merely injecting that key into
the writer's logical schema creates unwanted decoded metadata, so footer metadata
is restored through the dedicated API. A source without `ARROW:schema` may gain it.
Floating-point comparisons use integer views to retain NaN bits and signed zero;
nested lists/maps/structs are checked recursively without timestamp conversion to
Python/pandas objects.

Writing and verification read one row group at a time with at most 65,536 rows
per batch and no parallel reader prefetch. Verification aligns batches even when
row-group boundaries differ. Row-group/page layout and derived statistics can be
rebuilt. External column chunks and sorting declarations are unsupported; physical
schema mismatches (for example INT96 timestamps and integer-backed decimals)
reject the candidate. Missing verification dependencies leave the source intact.
The existing extra names and helper imports remain; DuckDB remains a legacy extra
dependency and supplies an independent reader in local tests.

A fixed synthetic corpus has an int64 ID and a 128-byte repeated string, stored
uncompressed without dictionaries. Fresh Python 3.9/PyArrow 21 processes on macOS
measured peak RSS of 70,729,728 bytes for 100,000 rows (14,011,566-byte input) and
71,467,008 bytes for 1,000,000 rows (140,112,469-byte input), both with 10,000-row
source groups. The 1,000,000-row file stored as one group reached 283,934,720 bytes.
These are local corpus measurements, not general memory guarantees: large source
column chunks, wide/nested rows and backend buffers still require an operation
byte budget in the remaining C4/resource-policy work. No whole-table path is used.
Other data writers, IPC framing and SQLite policy remain unimplemented in this slice.
