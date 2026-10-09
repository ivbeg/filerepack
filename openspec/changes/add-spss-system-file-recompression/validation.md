# Implementation validation — 2026-10-04

## Implemented and tested

IEEE SAV header/dictionary/case framing, exact raw-to-bytecode candidates and existing bytecode re-encoding are implemented. Both endian forms, signed zero/NaN literal retention and ReadStat/pyreadstat native checks pass. Original SAV samples are unchanged with zero savings; subsequently pinned Roche, jamovi and JASP SAVs have smaller native-reader-verified candidates. One complete external ZSAV sample saved four bytes, without closing broader independent-origin coverage. Existing ZSAV envelope code is explicitly experimental.

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

No multi-origin observational ZSAV corpus or proprietary SPSS matrix is available. Wider dictionaries/codepages/long strings/weights/multiple-response and native reader lineages need coverage; ZSAV release is not complete.

This validation note records actual work without declaring every broader task in
`tasks.md` complete. No change is archived or represented as universally qualified.

## Current integrated reconciliation — 2026-10-07

The [completion audit](../../../dev/quality/completion-2026-10-07.md) records
current runtime/installation checks, qualification scope and open gates.
`tasks.md` now distinguishes implemented tasks from unmet whole-corpus,
historical/native reader and platform requirements. The dated evidence above
is retained as its original experiment record; no release/deployment is asserted.
