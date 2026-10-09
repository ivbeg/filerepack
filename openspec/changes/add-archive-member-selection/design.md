## Context

Deep walking currently offers broad controls that make it difficult to avoid expensive member subtrees or target one asset family. Selection must operate on stable logical identities, preserve excluded payload bytes, and propagate to embedded assets without bypassing container integrity or security limits.

This design covers N05 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add repeatable `--exclude-member PATTERN` exclusions using documented normalized logical paths.
- Goal: Add independent image/audio/video/document/data allow/skip category selectors and an optimization depth limit.
- Goal: Report selection reasons and preserve excluded member payloads while continuing safe outer container compression.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Match case-sensitive normalized POSIX logical member names relative to each archive root. `*` matches within one segment, `**` spans segments, `?` matches one non-separator character, and matching covers the whole relative path. Directory exclusions ending `/` exclude that directory and its descendants. Apply the same patterns at every nested archive root; root-qualified cross-archive expressions are deferred.
2. Keep a separate stable host chain for reporting, such as structured archive/member components rendered `outer.zip!/inner.zip!/image.png`; never derive identity from extraction paths. Normalize format-defined separators without treating legitimate ZIP backslash characters as path separators. Windows/native extraction ambiguity is a safety skip, not a pattern rewrite.
3. Use repeatable `--category image|audio|video|document|data` as an optional allowlist and `--skip-category` as a denylist, with denies winning. Container traversal/compression is structural and remains permitted to reach selected descendants unless the member/depth policy excludes the container itself.
4. Preserve existing `--no-images`/`pack_images=false` compatibility: it disables image/audio/video processing according to legacy behavior, including cover/image extraction. It wins over positive category selection. New selectors let users disable only video or audio without that legacy broad effect.
5. Define `--max-depth` as the maximum optimization nesting depth: the top-level input is depth 0, direct members/assets depth 1, and each nested container/host adds one. A member at the limit can be optimized without opening its descendants. This only restricts optimization; extraction/decode/validation security depth and root budgets still apply.
6. Excluded members retain decoded payload bytes and required member metadata. Recompression of outer archive storage is allowed when package rules permit it; selection cannot authorize signature breakage or checksum inconsistency. For containers unable to rebuild without changing excluded payloads, skip the unsafe rewrite.
7. Every nested adapter receives selection, metadata, fidelity, quality and resource policies. A disabled embedded image remains untouched even when a surrounding XML/audio/PDF codec step is permitted.

## Risks / Trade-offs

- Shell glob expansion can consume patterns before the program sees them; document quoting and use explicit matcher fixtures on all platforms.
- Some container serializers change members incidentally; manifest validation must reject changes to excluded payloads.
- Optimizing a selected child can invalidate package-level integrity; existing specialized protection gates remain authoritative.

## Migration Plan

1. Introduce pure logical-path matching and category/depth resolution after manifest/protection and operation-context contracts exist.
2. Expose CLI/library controls and propagate through all archive and virtual asset walkers.
3. Document matching scope, root/depth semantics, deny precedence and legacy no-images behavior with real examples.

## Verification

- Test dotfiles, Unicode, spaces, option-like names, directory exclusions, `*`/`**`/`?`, literal ZIP backslashes, and nested archive roots on POSIX/Windows.
- Compare hashes and metadata of excluded members before/after outer compression; retain hidden/empty entries and required package layout.
- Verify independent media/category choices, legacy no-images precedence and embedded cover/XML/PDF option propagation.
- Test depth 0/1/n boundaries and confirm optimizer selection never relaxes security budgets, protection gates or structural validation.
- Parse outcome/audit records for durable skipped identities and selection reasons.
