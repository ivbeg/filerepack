## 1. Implementation

- [x] 1.1 Define profile version 1 and a typed deterministic option resolver tracking explicit overrides.
- [x] 1.2 Expose CLI/library profile selection and resource flags while retaining legacy no-profile and ultra behavior.
- [ ] 1.3 Route thread/deadline/temp limits through shared root contexts and batch scheduler allocations.
- [x] 1.4 Add profile version/effective-setting fields to typed outcomes and available planning/report/resume consumers.
- [x] 1.5 Benchmark all profiles on the fixed quality-gate corpus and document actual trade-offs and unsupported adapter controls.

## 2. Verification and documentation

- [x] 2.1 Check the exact profile version 1 settings and precedence for explicit false/default-valued CLI and library overrides.
- [x] 2.2 Verify none of the profiles alone selects lossy video/image/PDF paths and preserve retains requested metadata or explicitly skips incapable writers.
- [ ] 2.3 Exercise nested option inheritance and cumulative worker/tool-thread/temp/deadline enforcement.
- [x] 2.4 Record elapsed time, peak memory/scratch, accepted candidates and final bytes saved for the same corpus/tool versions.
- [x] 2.5 Ensure changes to profile definitions or adapters invalidate execution fingerprints where resume is available.
- [x] 2.6 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.7 Validate this change with `openspec validate add-optimization-profiles --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
