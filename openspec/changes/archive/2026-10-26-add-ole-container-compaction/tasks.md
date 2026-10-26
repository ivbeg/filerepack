## 1. Feasibility and design

- [x] 1.1 Inspect current format routing, candidate lifecycle and related pending proposals.
- [x] 1.2 Check primary documentation for CFB writers and Office compressed records.
- [x] 1.3 Define the initial compaction scope, preservation contract and later recompression stages.

## 2. Backend qualification

- [x] 2.1 Collect real, redistributable DOC/XLS/PPT fixtures with provenance and protected/unsupported cases.
- [x] 2.2 Compare pinned OpenMcdf and Rust cfb candidates against complete independent manifests; record licenses and platform/distribution requirements.
- [x] 2.3 Choose one production writer after metadata, allocation/tree validity, resource bounds and application compatibility checks.
- [x] 2.4 Measure actual compaction savings and costs separately from header-based estimates.

## 3. Implementation after proposal approval

- [x] 3.1 Add bounded CFB structural inspection and complete logical manifests.
- [x] 3.2 Add DOC/XLS/PPT profile and encryption/signature/rights-management gates, including qualified unsigned-VBA handling.
- [x] 3.3 Implement the optional compaction adapter with private candidates and unchanged live stream bytes.
- [x] 3.4 Register structural/preservation validation and the shared candidate transaction lifecycle.
- [x] 3.5 Register qualified Office aliases and standalone/archive-member routing; expose missing-backend and unsupported reasons.
- [x] 3.6 Document the qualified subset, compaction semantics and optional dependency installation.

## 4. Verification and delivery

- [x] 4.1 Test allocation cycles/overlaps/orphans, invalid names, incomplete reads, metadata mutation, missing streams and independent-reader disagreement.
- [x] 4.2 Test free regular/mini sectors, threshold edges, empty storages/streams, property sets, unknown streams and supported aliases.
- [x] 4.3 Test protected/unknown/unsupported skips, dry-run, size thresholds, interruption, nested archive preservation and filesystem metadata.
- [x] 4.4 Validate representative before/after documents with pinned applications and without repair prompts, with macros disabled.
- [x] 4.5 Run relevant project/platform/package checks and publish measured supported-subset evidence.

## Initial-stage execution evidence and boundaries

- Native OLE regressions: 73 passed on macOS arm64 with the configured Rust writer.
- Full source and installed-sdist suites: 1,288 passed, 108 skipped. Installed-wheel
  compatibility/validation/OLE subset: 488 passed, 22 skipped.
- Wheel/sdist build, source writer/lock/license inclusion and isolated artifact
  runtime checks passed. Documentation build and strict OpenSpec validation passed.
- Focused OLE Ruff/Mypy, Cargo fmt and Clippy passed. Repository-wide Ruff/Mypy
  report unrelated errors in other shared-working-tree modules; see dev/ole/README.md.
- Backend/application evidence is in dev/ole/qualification.json. All nine eligible
  real originals render identically with the pinned LibreOffice/Poppler pair.
  Headless export was qualified; interactive Microsoft Office repair dialogs and
  Linux/Windows rendering were not tested. Native platform CI is configured.
- The initial stage of task 3.2 skipped every VBA-bearing file. Section 5 records
  the subsequent unsigned-DOC/XLS qualification under the same conditional gate.
- Task 2.4 measures candidate sizes and single-run writer durations. Peak-memory
  benchmarking is not performed; fixed structural/file/time limits are tested.

## 5. Continued unsigned-VBA qualification (authorized follow-up)

- [x] 5.1 Check authoritative DOC/Office property-set signature locations.
- [x] 5.2 Add bounded StwUser and DocumentSummaryInformation index/protection checks.
- [x] 5.3 Qualify canonical unsigned DOC/XLS projects, retaining every project byte.
- [x] 5.4 Extend real corpus, hidden-signature/unknown-layout regressions and native CI.
- [x] 5.5 Render qualified before/after fixtures with macros disabled and record evidence.
- [x] 5.6 Update supported-subset docs and run source/artifact/static/spec checks.

Continued-stage checks: 120 native OLE tests passed. Full source and installed-sdist
suites each passed 1,342 tests with 109 skipped; the installed-wheel subset passed
542 tests with 22 skipped. Isolated wheel/sdist runtime, source/lock/license
inclusion, documentation build, focused Ruff/Mypy and strict OpenSpec checks
passed. The expanded corpus retained 26/26 manifests and 13/13 render pairs;
three original fixtures contain qualified unsigned VBA projects. Repository-wide
Ruff/Mypy still report unrelated shared-working-tree errors listed in
`dev/ole/README.md`. Other-platform rendering and interactive Microsoft Office
validation remain outside the local evidence.

## 6. Continued PPT unsigned-VBA qualification (authorized follow-up)

- [x] 6.1 Verify PPT VBAInfo/project storage and host-signature specifications.
- [x] 6.2 Validate canonical single-edit PPT project references and bounded storage decoding.
- [x] 6.3 Independently inspect the nested project and preserve its original encoded bytes.
- [x] 6.4 Add real PPT/POT/PPS and corrupt/protected/ambiguous-reference regressions.
- [x] 6.5 Record before/after renderer and complete-manifest evidence with macros disabled.
- [x] 6.6 Update scope documentation and validate source, artifacts, static checks and specs.

PPT-stage checks: 161 native OLE tests passed. Full source and installed-sdist
suites each passed 1,383 tests / 109 skipped; the installed-wheel subset passed
583 / 22 skipped. Both isolated artifact installations and source packaging
checks passed, including the new PPT module/tests. Documentation build, focused
OLE Ruff/Mypy, repository-wide Ruff and strict OpenSpec checks passed.
Repository-wide Mypy still reports four unrelated errors in `mat.py`.
The new report retains 29/29 full manifests and 15/15 renderer pairs, including
a fixture-derived uncompressed-wrapper variant. All render exports disable
macros. Interactive Microsoft Office and other-platform rendering remain
unqualified; native platform CI includes the new tests.

## 7. DOC no-op diagnostic correction (user-reported bug)

- [x] 7.1 Reproduce equal-size DOC candidates and missing-backend behavior.
- [x] 7.2 Retain OLE eligibility/backend/verification skip reasons in PackResult,
  library summaries and bulk jobs; retain shared size/minimum-savings reasons.
- [x] 7.3 Show reasons, actual strategies and PPT-only option scope with verbose
  CLI/bulk output, including when log output is enabled; retain parseable JSON.
- [x] 7.4 Add real DOC CLI/API/worker regressions for zero savings, dependencies,
  protection, log files, quiet output and serial/parallel bulk processing.
- [x] 7.5 Clarify DOC/XLS container-only compaction in documentation and check
  source/static/docs/spec tests; include the regressions in platform/artifact CI.

Reproduction found five eligible real DOC originals, all with zero free regular
sector estimates and equal measured candidate sizes. Protected and unsupported
files are explicitly distinguished. The existing controlled DOC holes tests
still demonstrate physical compaction savings; application stream bytes remain
unchanged. The local native helper was built but absent from PATH, another
independent reason for no rewrite until an explicit tool path is supplied.

Diagnostic regressions: 14 passed. Focused OLE/CLI/transaction/destination checks:
398 passed / two skipped. Full source suite: 1,492 passed / 156 skipped.
Repository-wide Ruff, focused Mypy for three changed source modules, documentation
build and strict OpenSpec checks passed. The wider typed-outcome/status/exit-code
proposal remains separate; this correction changes diagnostics and leaves
transformation eligibility and publication rules intact.

Final isolated artifact checks also passed: installed-wheel subset 655 passed /
22 skipped; installed-sdist full suite 1,492 passed / 156 skipped. The fresh CLI
and API provenance checks include the diagnostic regression module.
