## Context

Candidates are created in system temp storage, inode replacement changes permissions, and codec modules reach into repack.py through dynamic Any imports. Publication and subprocess policy need one portable typed lifecycle.

This design covers R10, B1, C5 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Move staging, command execution, validation/acceptance, and publication behind shared typed internal interfaces.
- Goal: Publish verified candidates using destination-local staging and retain declared filesystem metadata.
- Goal: Detect source changes and define symlink/hardlink and crash-durability policies.
- Goal: Split codec families incrementally while preserving public import paths.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Use operation-owned scratch storage for encoding and a verified destination-local candidate for final os.replace; never implement EXDEV fallback as destructive direct copying over the original.
2. Preserve source permission bits and modification time by default; preserve supported extended attributes or report inability under a requested preservation policy. Security-sensitive ownership changes are not silently attempted.

2026-10-08 bug-fix qualification: macOS may assign protected
`com.apple.provenance` when the destination-local stage is created. Its absence
from the source no longer makes publication fail solely because the system label
cannot be removed. Before copying the candidate, publication captures the newly
created stage's native value. On macOS only, that exact value may remain when
the source has no provenance. Every original attribute remains exact; no other
additional attribute is admitted, and source provenance takes precedence.
Different source provenance, later-added or changed stage labels and ignored
source-attribute writes still refuse publication. Permission, mtime, candidate
digest, source-generation and destination guards remain in use.

Nine controlled boundary cases and native public original-PPT plus private
in-place/backup qualification pass. Shared filesystem/candidate/output contracts
pass 186 tests with two second-filesystem skips on local Python 3.9.6 and 3.13.7.
See `dev/ole/qualification-ppt-macos-publication.json` and the documented policy in
`docs/docs/getting-started/safety.md`. This fixes intended platform publication
behavior; it does not assert remote platform results or deployment.
3. Reject file-symlink and multiply linked in-place sources unless a separately explicit supported policy defines the result; never follow a symlink merely to satisfy a size check.
4. Recheck source identity/generation immediately before publication; concurrent changes produce a conflict.
5. Do not claim crash durability without explicit file/directory flush support; report the supported publication guarantee.
6. Move helpers first, then codec families with compatibility re-exports and stronger typing; avoid a plugin framework.

## Risks / Trade-offs

- Filesystem guarantees vary by platform; test them and distinguish atomic visibility from crash durability.
- Large module moves obscure behavior changes; retain a pre-move API/dispatch snapshot and keep lifecycle fixes separately described. No commits have been created during local implementation.

## Migration Plan

1. Preserve FileRepacker/pack_* import compatibility and legacy result access.
2. Treat custom scratch location separately from destination-local publish staging.
3. Replace dynamic _r()->Any coupling incrementally and remove relaxed return-type checking once the interfaces are typed.

## Verification

- Test destination-local atomic publication and source preservation on failures across supported filesystems.
- Run import/API compatibility, dry-run, lint/type, and focused codec regressions.

## Implemented publication boundary (2026-10-03)

- `transactions.py` owns typed `FileSnapshot`/`FileMetadata`, SHA-256 comparison, per-helper source scopes, scratch allocation tracking and destination-local publication. Public helpers capture before encoding; `FileRepacker` captures before destination inspection. Nested helpers on the same source share its scope, while extracted assets have isolated scopes. Scope cleanup covers failures before a packer's own try/finally, including initial encoder copying and a second allocation failing. `candidate_scope` is shared by guarded standalone helpers and archive work. PNG derived sidecars and SQLite candidate journals are registered before tools can write them; WOFF2 tools and archive extraction use exclusively allocated directories. Unexpected encoder/validator exceptions clean those paths while retaining the source. Pre-existing sidecars are never claimed.
- `PathReservation` captures source and existing-output generations. After copying and checking the local stage, publication rechecks content hashes and device/inode/size/mode/mtime/ctime/link/ownership generations. Overwrite authorization permits only the inspected output; newly appearing outputs still use no-clobber linking. Conversion cleanup rechecks the original before deleting it. If an outside writer changes the source after the converted output is published, that output remains and a cleanup conflict retains the new source bytes.
- Local stages receive source permission mode, mtime and all extended attributes exposed by the Linux/macOS APIs; attribute/mode/time verification fails closed. macOS uses the native xattr ABI because Python's `os` xattr functions are Linux-only. Resource forks and binary/empty values are supported. Atime can change during reads; ownership, native ACLs, birth time, filesystem flags and Windows alternate streams are outside the declared policy.
- Atomic visibility is the only supported guarantee (`RepackOptions.durability="atomic"`). Crash-durability requests fail validation before scratch, output or backup creation; no fsync guarantee is asserted. There remains a short check-to-rename/unlink race with non-cooperating writers. Multiple complete hash passes add I/O, which remains subject to the future operation-resource/benchmark work.
- `candidates.py` now owns allocation, format verification, savings/minimum-threshold acceptance, dry-run results and publication using typed `CommitArguments`/`PackResult`. `commands.py` holds typed argv/subprocess execution without shell evaluation or global cwd changes; audio probing retains nonzero diagnostics through `capture_command`. All packer families depend on these interfaces, while family-specific preservation checks remain in their existing validators.

## Implemented family and type boundaries (2026-10-03)

- `streams.py`, `images.py`, `media.py`, `documents.py`, `data.py` and `medical.py` own standalone implementations; `markup.py` retains lexical JSON/XML helpers. `archives.py:ArchiveRepacker` owns extraction, manifests and writers, with a typed deep-walk hook implemented by `repack.py:FileRepacker`. `dispatch.py` imports implementations directly and retains the existing 79 routes and option mappings.
- `repack.py`/`codecs.py` re-export existing helpers. The captured pre-move contract checks all 69 callable signatures/defaults, and six fresh-process import orders exercise the dependency graph. XML embedded members lazily import the typed dispatcher; SVG fallback uses a typed markup import. No codec/markup `_r()->Any` or import of the orchestrator remains.
- Filesystem interfaces, candidate results, stream readers/writers, progress events and worker request/results now have concrete annotations. The mypy `codecs` return-type relaxation and redundant markup casts are removed. Opaque option values remain only where legacy heterogeneous keyword/dictionary adapters or optional backend APIs require them; this does not claim complete removal of every `Any` in the package. Public `quiet` parameters remain accepted for compatibility; the unused private stream-helper `quiet` option was removed. Encoding flags, default quality, dispatch categories and acceptance thresholds remain unchanged.
- Worker dictionaries retain their existing runtime validation and result keys. This refactor does not implement the separate typed terminal-outcome, bounded-worker, structural-validation, media-fidelity or SQLite live-database preservation proposals. Linux/Windows, actual second-filesystem evidence and rollout remain open.

References: [Python file-operation guarantees](https://docs.python.org/3.13/library/os.html#os.replace), [copy metadata limits](https://docs.python.org/3/library/shutil.html#shutil.copy2), and Apple's native [listxattr](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/listxattr.2.html), [getxattr](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/getxattr.2.html) and [setxattr](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsetxattr.2.html) ABI documentation.

Local evidence: **47 transaction tests passed, 2 skipped** (no writable second filesystem on macOS), and all **92 family/compatibility/scratch tests passed**. The complete suite passed **857 tests, 3 skipped** with DICOM dependencies; the base environment passed **821 tests, 39 skipped**. Ruff/mypy passed (67 source files at the final check), documentation built and all **26** present OpenSpec changes validated strictly. Fresh installed-artifact checks passed on Python **3.9 and 3.13**: **132 wheel API/CLI/compatibility/fault tests** and **792 sdist tests, 40 explicit skips** per interpreter, without checkout runtime fallback. The development-only artifact environments omit optional data/DICOM integrations. The verified artifact snapshot contains all extracted families, the API fixture and complete source test support; runtime module bytes matched the checkout before validation. This is local evidence; remote CI, Linux/Windows filesystem evidence and deployment remain unasserted.
