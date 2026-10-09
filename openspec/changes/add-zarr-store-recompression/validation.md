# Implementation validation — 2026-10-04

## Implemented and tested

repack-store, typed library options/outcome, complete-v2 inventory, per-array codec decisions, exact chunks, lexical metadata/consolidation updates, generation checks and exclusive owned directory publication are implemented. Two complete external interoperability stores and consolidated native fixtures pass; both codec policies have measured benefit.

Integration includes CLI/bulk/library validation, unchanged reasons and JSON profile details,
shared ordinary-file candidate/source/destination transactions, isolated native workers,
cumulative decode/node/scratch/time accounting, sampled RSS supervision and cancellation.
Scientific dry-run does not encode or create candidate workspaces.

## Evidence

- [Full reproducible report and all-attempt artifacts](../../../dev/format_survey/implementation-2026-10-04/README.md).
- [Runtime profile contracts](../../../docs/docs/formats/scientific.md).
- [Trusted native and adversarial tests](../../../test/test_scientific_formats.py).

The earlier full suite passed (1,373 tests, 145 skips); the final focused integration suite passed 423 tests with 4 skips.
This includes 84 scientific tests with one filesystem-dependent skip, root-accounting closure after worker failure and preservation of prior destinations on scientific refusal.
Full repository Ruff/mypy, Python 3.9 module compilation, seven strict OpenSpec validations and the documentation production build pass.
Native CI is configured but its remote runs are not claimed as completed.

## Open qualification gates

The external stores are examples/fixtures rather than independent observational datasets. Full native Linux/Windows publication qualification, more scientific datasets and representative cold-read/peak-scratch costs remain open. macOS/APFS is tested; each filesystem primitive is probed before use.

This validation note records actual work without declaring every broader task in
`tasks.md` complete. No change is archived or represented as universally qualified.

## Current integrated reconciliation — 2026-10-07

The [completion audit](../../../dev/quality/completion-2026-10-07.md) records
current runtime/installation checks, qualification scope and open gates.
`tasks.md` now distinguishes implemented tasks from unmet whole-corpus,
historical/native reader and platform requirements. The dated evidence above
is retained as its original experiment record; no release/deployment is asserted.
