# Change: Add archive-member exclusions, optimization depth and category selection

## Why

Deep walking currently offers broad controls that make it difficult to avoid expensive member subtrees or target one asset family. Selection must operate on stable logical identities, preserve excluded payload bytes, and propagate to embedded assets without bypassing container integrity or security limits.

## What Changes

- Add repeatable `--exclude-member PATTERN` exclusions using documented normalized logical paths.
- Add independent image/audio/video/document/data allow/skip category selectors and an optimization depth limit.
- Report selection reasons and preserve excluded member payloads while continuing safe outer container compression.

## Impact

- Priority: **P2**. Roadmap slice: **D — member selection**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); N05.
- Affected capabilities: `member-selection`.
- Affected code: `filerepack/models.py:RepackOptions`, `filerepack/__main__.py:_build_options/repack/bulk`, `filerepack/repack.py:_deep_walk/_process_walk_item/pack_images`, `filerepack/containers.py:pack_members`, `filerepack/markup.py`, `filerepack/covers.py`, `filerepack/pdf_streams.py`, `filerepack/formats.py`.
- Status: proposed; no implementation or deployment is asserted.

## Dependencies

- [fix-archive-member-preservation](../fix-archive-member-preservation/proposal.md)
- [fix-compressed-tar-roundtrip](../fix-compressed-tar-roundtrip/proposal.md)
- [update-container-format-policies](../update-container-format-policies/proposal.md)
- [add-operation-resource-budgets](../add-operation-resource-budgets/proposal.md)
- [update-media-preservation-policy](../update-media-preservation-policy/proposal.md)
- [update-repack-outcomes](../update-repack-outcomes/proposal.md)

## Validation

- Test dotfiles, Unicode, spaces, option-like names, directory exclusions, `*`/`**`/`?`, literal ZIP backslashes, and nested archive roots on POSIX/Windows.
- Compare hashes and metadata of excluded members before/after outer compression; retain hidden/empty entries and required package layout.
- Verify independent media/category choices, legacy no-images precedence and embedded cover/XML/PDF option propagation.
- Test depth 0/1/n boundaries and confirm optimizer selection never relaxes security budgets, protection gates or structural validation.
- Parse outcome/audit records for durable skipped identities and selection reasons.

## Approval and rollout

Review this proposal and its complete requirement scenarios before implementation. Implementation tasks remain unchecked. Preserve existing public entry points unless the breaking behavior above explicitly changes their contract; document migrations for those changes.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
