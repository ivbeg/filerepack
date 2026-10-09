## 1. Implementation

- [x] 1.1 Define normalized logical member identity and a tested platform-independent pattern matcher with per-archive scope.
- [x] 1.2 Add repeatable exclusion/category controls and depth settings to CLI/library option validation.
- [x] 1.3 Enforce selection during archive and virtual-asset traversal with stable skipped reason records.
- [x] 1.4 Propagate controls through covers, XML/SVGZ data URIs and PDF walkers without forced image re-enabling.
- [x] 1.5 Validate unchanged excluded payloads and required metadata in each rebuilt archive/package.
- [x] 1.6 Document matching syntax, quoting, depth boundaries, deny precedence and legacy compatibility.

## 2. Verification and documentation

- [ ] 2.1 Test dotfiles, Unicode, spaces, option-like names, directory exclusions, `*`/`**`/`?`, literal ZIP backslashes, and nested archive roots on POSIX/Windows.
- [x] 2.2 Compare hashes and metadata of excluded members before/after outer compression; retain hidden/empty entries and required package layout.
- [x] 2.3 Verify independent media/category choices, legacy no-images precedence and embedded cover/XML/PDF option propagation.
- [x] 2.4 Test depth 0/1/n boundaries and confirm optimizer selection never relaxes security budgets, protection gates or structural validation.
- [x] 2.5 Parse outcome/audit records for durable skipped identities and selection reasons.
- [x] 2.6 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.7 Validate this change with `openspec validate add-archive-member-selection --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
