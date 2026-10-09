## 1. Implementation

- [x] 1.1 Add fault injection for EXDEV, failed verification/publication, source changes, permissions, and cleanup.
- [x] 1.2a Extract typed filesystem publication/source snapshots and subprocess interfaces; adapt existing packers while retaining public helper signatures and encoding/acceptance defaults.
- [x] 1.2b Complete operation-owned staging for tool sidecars, move acceptance into the shared core and replace dynamic codec/markup back-imports with typed dependencies.
- [x] 1.3 Stage final publication on the destination filesystem and retain documented filesystem metadata.
- [x] 1.4 Implement source-generation, symlink/hardlink, and explicit durability policies (atomic visibility supported; stronger requests rejected before writes).
- [x] 1.5 Move proven archive/image/media/data helper families with compatibility re-exports.
- [x] 1.6 Tighten core/worker annotations and remove broad Any coupling and obsolete helper options after compatibility review; retain heterogeneous legacy option adapters and public quiet parameters.

## 2. Verification and documentation

- [x] 2.1a Test local staging, source/output generations, source metadata and failures on macOS; exercise real native xattrs/resource forks, controlled EXDEV and Linux API adapters.
- [ ] 2.1b Establish Linux/Windows and actual second-filesystem publication evidence; the `/dev/shm` cases skip explicitly on the current macOS host.
- [x] 2.2 Run import/API compatibility, dry-run, lint/type, and focused codec regressions for the implemented boundary.
- [x] 2.3 Run the focused/full test suites and lint/type/artifact/docs checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate refactor-repack-transactions --strict`.
- [x] 2.5 Fix false macOS publication refusal for creation-time native provenance absent from the source; verify strict source/other attribute retention, bounded exceptions, direct original-PPT output and private in-place/backup publication on local Python 3.9/3.13.

## 3. Integration and rollout

- [ ] 3.1 Complete remaining implementation/platform checks, reconcile the canonical baseline, integrate and record deployment before archival.
