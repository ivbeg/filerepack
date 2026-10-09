## Context

Interrupted large jobs repeat completed compression work. Resume must distinguish genuine completed publication from stale outcomes caused by changed sources, outputs, effective options, toolchains, or policy versions, including the special case where successful in-place processing changes the source itself.

This design covers N03 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add `--manifest FILE` checkpointing and `--resume` for bulk jobs.
- Goal: Reuse completed outcomes only after source/output content and effective execution fingerprints match.
- Goal: Publish checkpoints atomically, protect manifest destinations, and make stale/corrupt state observable.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Use a local versioned manifest with one coordinator writer and atomically replaced checkpoints on the manifest filesystem. Record run-root/path identity, before/after source digest and size, output digest/destination, terminal outcome, publication/validation state, normalized effective options, and tool/capability/preservation-policy versions.
2. For in-place success, reuse only when the current source matches the stored verified post-publication digest. For distinct-output success, require the unchanged original source and the stored output to match. Inode/mtime alone are hints and cannot prove identity after atomic replacement or equal-size edits.
3. Reusable completed outcomes are replaced and verified unchanged, including a published unchanged copy when requested. Failed, cancelled, predicted, unsupported, policy-skipped, or incomplete operations are re-evaluated rather than cached as successful work.
4. Fingerprint effective options deterministically including destination, fidelity, metadata, validation, resource/selection policies and schema versions. Include the resolved tool paths/versions and relevant capability/probe results; later profile support adds profile definition version/effective settings to the same fingerprint.
5. On invalidated entries re-plan processing from current bytes and emit the invalidation reason. Mark safely reused completion in the report without counting previously saved bytes as savings achieved in the current run.
6. Validate schema, run roots and manifest path before writes; a malformed/unsupported manifest fails before processing. An interrupted atomic update may leave an older valid checkpoint; entries missing from it are processed again through normal source/destination collision checks.
7. Reserve the manifest separately from reports, source/output and backups, exclude checkpoint/temp paths from discovery, and lock against concurrent writers. `--resume` requires an existing compatible manifest; dry-run can read one but does not persist completion. Manifest errors fail the invocation without claiming processing rollback.

## Risks / Trade-offs

- Digest verification costs read I/O but prevents stale success from equal-size/time changes; use streaming hashing under the shared resource policy.
- A publication can complete before checkpoint persistence; an older checkpoint must cause safe reprocessing/conflict handling, never blind output overwrite.
- Manifest paths/digests disclose local filesystem information; document the manifest as private local state distinct from redacted reports.

## Migration Plan

1. Introduce a versioned manifest contract and fingerprint canonicalization before enabling reuse.
2. Add checkpoint writing without resume, then reuse only verified eligible terminal states.
3. Document in-place post-state verification, invalidation reasons, output collision handling after crashes, and supported schema versions.

## Verification

- Interrupt a batch and resume; verify completed matching inputs do not re-encode while incomplete ones are processed.
- Change bytes without changing size/time, effective options, tool version/path, policy version, and output destination; verify each invalidates reuse.
- Test in-place post-publication identity and distinct-output deletion/modification; prevent stale success or unrelated overwrite.
- Inject checkpoint replacement failure/crash and simultaneous writers; preserve a valid prior manifest and safe normal collision behavior.
- Cover malformed/unsupported manifests, aliases to inputs/outputs/reports, dry-run read-only behavior, and reconciled resumed accounting.
