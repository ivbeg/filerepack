## 1. Pre-approval research and concrete proposal

- [x] 1.1 Audit MS-PPT storage wrappers, live-object discovery and position fields;
  record the standard revision, primary sources and scope limits.
- [x] 1.2 Measure zlib level 9 and optional Zopfli on a pinned real PPT and clearly
  labelled encoding-only controls, separating stream savings from sector savings.
- [x] 1.3 Verify exact nested bytes, surrounding records, references, complete CFB
  metadata and six before/after renderer pairs; retain the reproducible report.
- [x] 1.4 Add fault-injection tests for the fixture-bound development experiment.
- [x] 1.5 Validate the proposal and record focused regression checks.
- [x] 1.6 Obtain approval before runtime implementation.

## 2. Qualified transformation and verification, after approval

- [x] 2.1 Define the standard record/extension allowlist and expand the real fixture
  corpus before enabling a general single-edit, trailing-object profile.
- [x] 2.2 Resolve uniquely referenced embedded DOC/XLS objects; enforce host/nested
  protection, macro, history, subtype, alias and resource gates.
- [x] 2.3 Implement bounded decode/encoding, original-wrapper retention and checked
  relocation of the trailing storage/index/edit block and Current User field.
- [x] 2.4 Add an independent `ppt-ole` intended-change fingerprint/verifier without
  changing `ole` stream-byte equality.
- [x] 2.5 Add rejection tests for bad wrappers, expansion bombs, budget exhaustion,
  missed offsets, extra changes, unknown extensions and reader disagreement.

## 3. Native writer and product integration, after approval

- [x] 3.1 Extend the native helper with explicit two-stream replacement and capability
  discovery; retain bounded reads, all metadata and existing compaction arguments.
- [x] 3.2 Add the opt-in CLI/library setting and propagate it through bulk, workers
  and archive members; preserve the false default and actual-strategy reporting.
- [x] 3.3 Run the encoder in the bounded worker and qualify optional Zopfli versions
  without raising Python 3.9 requirements or adding a base dependency.
- [x] 3.4 Stage/verify/publish through existing transactions; test dry-run, zero
  savings, backup/distinct destinations, interruption and missing/old backends.

## 4. Qualification and release evidence, after approval

- [x] 4.1 Record real-file preservation/rendering and byte savings independently
  of controlled variants; retain the ordinary compaction baseline.
- [x] 4.2 Run locally available source/native/distribution tests, static checks and
  documentation build; configure supported Python/platform CI and explicitly
  record platform/application checks that could not be executed locally.
- [x] 4.3 Document option, encoder installation, verified scope, skip/fallback behavior
  and the decoded-storage contract without presenting the pilot as broad support.

## Pre-approval evidence

The development experiment passed 18 fault/preservation tests; the existing
native OLE suite passed 161 tests (179 combined). All six pilot candidates pass
independent CFB/fixture-intent checks and equal-page rendering. Focused Ruff and
Mypy for the new pilot passed. Strict OpenSpec validation passed for this proposal
and the existing compaction change. Production files, dependencies and routing
were not changed by this research stage. The approved runtime stage is recorded below.

## Approved implementation evidence and remaining qualification boundaries

Approved by the user's “Подтверждаю” on 2026-10-04. Production tasks 2–4 are
implemented in `ole_ppt_records.py`, `ole_recompress.py`, the native helper 0.2.0,
shared verification/worker/option propagation and user documentation.

- Expanded real corpus: 23 files, 15 eligible compaction profiles and eight skips.
  `qualification-ppt-runtime.json` retains 33 equal native manifests, 18 equal
  renderer pairs and 11 public-API PPT cases (four record rewrites, seven strict
  compaction fallbacks). The real embedding original saves an additional 512 bytes
  beyond compaction, with byte-identical decoded DOC/XLS objects.
- Runtime regressions: 57 tests passed with the native helper, including malformed
  wrappers/references, unknown layouts/encoders, independent readers, root metadata,
  immutable nested CFB allocation bytes, limits/cancellation/interruption, CLI,
  bulk, archive members, dry-run, backups, destinations and filesystem metadata.
  The existing 161 OLE tests and 18 development tests also passed.
- Full source check before final regressions: 1,468 passed / 156 skipped. Final
  installed-sdist full suite: 1,478 passed / 156 skipped; installed-wheel subset:
  641 passed / 22 skipped. Fresh installations verified runtime provenance, CLI,
  source/native/fixture inclusion, optional metadata and license fields. The first
  artifact attempt hit transient DNS failure fetching setuptools; subsequent
  isolated wheel and sdist validations both completed successfully.
- Repository-wide Ruff, focused Mypy with `--follow-imports=silent` for eight
  OLE/worker modules, Rust fmt/release build/Clippy, documentation build and strict
  validation of this change and the compaction change passed. Repository-wide
  Mypy still reports four pre-existing operand-type errors in `filerepack/mat.py`.
- Local execution/renderer evidence is macOS arm64 Python 3.13.7 with pinned
  LibreOffice/Poppler and Zopfli 0.4.3. Native CI is configured for Linux/macOS/
  Windows Python 3.9/3.13, including zlib-only Python 3.9; those remote jobs and
  interactive Microsoft Office have not been executed locally. These are release
  qualification boundaries, not measured successes. No broad PPT compatibility
  or general compression ratio is inferred from the single positive real layout.
