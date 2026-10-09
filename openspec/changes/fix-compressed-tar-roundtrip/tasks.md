## 1. Implementation

- [x] 1.1 Add the reviewed gzip-level-zero regression and fixtures for tar.gz/tgz, tar.xz, and tar.bz2.
- [x] 1.2 Implement separate wrapper decode and tar-member extraction stages.
- [x] 1.3 Rebuild the tar payload and apply only the original outer codec.
- [x] 1.4 Audit gem/crate/unitypackage and optional stream aliases with real-format fixtures.
- [x] 1.5 Test both deep modes, failed stages, size rejection, dry-run predictions, and scratch cleanup; update format docs.

## 2. Verification and documentation

- [x] 2.1 Compare decoded member names, types, links, and preserved payloads before and after each wrapper.
- [x] 2.2 Explicitly skip optional-codec tests when tools are absent.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate fix-compressed-tar-roundtrip --strict`.

## 3. Integration and rollout

- [x] 3.1 Reconcile the canonical baseline and confirm deployment before archiving; local implementation is not deployment evidence.

Local verification covers both deep modes across gzip/bzip2/xz/LZMA/zstd/Brotli/LZ4/lzip/lzop/Unix-compress wrappers and their aliases, a real RubyGems-built package, representative crate/unitypackage wrapper fixtures, wrong wrappers, rejected stages and cleanup. Links are explicitly unsupported and retain source bytes; package application semantics remain a separate container-policy change.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
