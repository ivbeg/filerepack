## 1. Implementation

- [x] 1.1 Add outcome/exit-code matrix tests for corrupt, missing-tool, disabled, protected, rejected, and predicted work.
- [x] 1.2 Introduce typed requests/outcomes and preserve legacy result adapters.
- [x] 1.3 Record durable source/destination/member identities, timing, and actual/predicted publication.
- [x] 1.4 Include all outcomes and reconcile summary totals and outer-vs-inner archive changes.
- [x] 1.5 Make JSON/CSV stdout parseable at every verbosity and reset logging per invocation.
- [x] 1.6 Document status/reason schema and exit-code migration; test repeated CliRunner calls.

## 2. Verification and documentation

- [x] 2.1 Parse plain JSON/CSV without --quiet under success, failure, dry-run, progress, and skips.
- [x] 2.2 Verify legacy mapping/API tests and exact summary reconciliation.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate update-repack-outcomes --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.

## Human completion labels — 2026-10-08

Human repack/bulk output now explicitly shows SUCCESS, ERROR, SKIPPED or
CANCELLED, including successful no-benefit/dry-run results and errors under
quiet mode. Optional record recompression skips are informational. Overall
completion labels account for report/checkpoint/scan failures and interruption.
JSON/CSV schemas and existing exit-code policies are retained.

Validation: 251 distinct CLI/outcome/OLE-diagnostic/logging/audit/resume/progress/
output-safety tests passed in the project Python 3.13 environment. Changed-module
Ruff/Mypy, strict OpenSpec validation (105 items) and the ownership/audit check
passed. Public CLI checks on the reported XLS return SUCCESS/status 0 with an
identical source hash; a corrupt gzip under --quiet returns ERROR/status 1.
