# Repository improvement OpenSpec roadmap

Source: [Repository review and improvement plan](../dev/docs/repository-review-and-improvement-plan.md).

This roadmap converts the review into **22 changes**, **27 capability delta files**, **72 requirements**, and **160 scenarios**. It covers all findings R01–R15, delivery slices A1–A7/B1–B6/C1–C6, and new features N01–N06. Every change includes `proposal.md`, `design.md`, `tasks.md`, and requirement deltas under `specs/`.

## Status and specification baseline

**Current reconciliation (updated 2026-10-08):** the implemented runtime now includes
typed outcomes, bounded bulk coordination, inspection, audit/report evidence,
content-verified resume, named profiles, member selection, recursive Flate PDF
walking, preserving web fonts, CAR and tracev3. The current canonical baseline
is populated with 180 reviewed requirements in 48 capabilities; the
[baseline audit](baseline-audit.json) covers 281 historical/active source blocks.
Live requirement ownership is unique and tested by `dev/check_spec_ownership.py`.
[Current completion evidence](../dev/quality/completion-2026-10-07.md) and the
change-level checklists supersede the dated implementation summaries below.
External reader/corpus, full resource, remote platform and deployment gates
remain separate. No change has been archived.

The following dated paragraphs preserve the earlier delivery history.


The user authorized implementation on 2026-10-02. Six changes are implemented and verified locally: [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md), [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md), [fix-markup-preservation](changes/fix-markup-preservation/proposal.md), [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md), [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md) and [fix-distribution-test-support](changes/fix-distribution-test-support/proposal.md). Their implementation/verification tasks are checked, while integration and deployment remain open. Early A6 is partially implemented through [update-data-format-preservation](changes/update-data-format-preservation/proposal.md) (Parquet) and [update-container-format-policies](changes/update-container-format-policies/proposal.md) (ODF/EPUB). These broader changes retain open tasks for other data writers, SQLite, resource policies, container audits and capability/application evidence. The local implementation of [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md) is complete: shared staging/acceptance/publication and subprocess interfaces, source/metadata/link/durability policies, family relocation, compatibility exports and core/worker typing are in use. The overall change remains partial pending Linux/Windows, actual second-filesystem evidence and rollout. The remaining execution and capability proposals retain open implementation checklists. No deployment or archival is asserted.

Local checks on 2026-10-03: **857 tests passed, 3 skipped** with DICOM dependencies, including **63 new archive preservation cases**, **76 new markup preservation cases**, **116 new output-safety cases**, **66 new DICOM safety cases**, **29 new Parquet cases**, **62 new ODF/EPUB package cases**, **49 transaction cases** (47 passed, 2 second-filesystem skips on macOS) and **92 family/compatibility/scratch cases** (all passed). Without DICOM dependencies, **821 passed, 39 skipped**. Ruff and mypy passed; all **26** present changes passed strict OpenSpec validation; the Docusaurus documentation and wheel builds succeeded. All **91 A6 cases** passed with the minimum PyArrow 19.0.1; primary full checks used PyArrow 21. Installed-wheel smoke checks verified Parquet/ODF/EPUB preservation, distinct output, dry-run and a real Parquet CLI rewrite on PyArrow 19; the wheel contains the new modules and dependency metadata. Prior wheel checks also established collision refusal and real DICOM encoder/decoded-pixel verification. Full checks ran on macOS/Python 3.9 with pydicom 2.4.4; a separate Python 3.11/pydicom 3.0.2 environment previously passed all **93 DICOM tests**. Broader platform/extra coverage remains C2 work. Package tests use standards-shaped fixtures and do not establish complete ODF/EPUB conformance or application rendering. Parquet reads bounded row batches one source group at a time, but large groups/backend buffers still need the remaining operation resource policy. Video/RAR destination tests use controlled codec fixtures and do not establish real codec fidelity. DICOM tests use real GDCM/DCMTK encoders on synthetic images; clinical IOD, cryptographic signature and color-image guarantees remain unestablished.

A7 artifact validation independently passed on macOS/Python **3.9 and 3.13**: each installed wheel passed **40 API/CLI/progress tests**, each installed sdist collected successfully and passed **653 tests, 38 explicit optional skips**, with no checkout import fallback. The fresh development-only environments intentionally omit Parquet/DICOM extras. The minimum setuptools **77.0.3** passed source/wheel content, entry-point and SPDX license checks on Python 3.9. Artifact fault checks rejected missing support, test leakage into the wheel and incorrect license metadata. Source distributions now include all test support/configuration; runtime wheels retain only application contents. Ubuntu artifact CI jobs are configured on Python 3.9/3.13 but have not run remotely. `python dev/validate_distribution.py` or `make check-dist` repeats the installed-artifact checks.

B1 publication evidence: permission mode/mtime and native macOS binary xattrs/resource forks survive direct and library publication; source/output changes, stale verification, metadata/copy/replace failures and early scratch-allocation/encoder failures retain original bytes and clean owned scratch. Controlled EXDEV tests enforce destination-local replacement. Actual `/dev/shm` cross-filesystem cases skip on this host; the existing Ubuntu CI matrix will exercise them when available, but no remote Linux/Windows result is asserted. Atomic visibility is supported; crash-durability requests fail before writes. Ownership/native ACLs/Windows alternate streams and the short final-check race remain documented limitations. Conversion cleanup retains a source changed after output publication and reports a conflict. Candidate acceptance and family implementations now live outside the orchestrator; 69 existing helper contracts and 79 registry routes match the captured baseline. PNG sidecars, WOFF2 directories, SQLite candidate journals and failed archive candidates are cleaned without claiming other operations' files.

The final B1/C5 artifact snapshot passed fresh installations on Python **3.9 and 3.13**: **132 wheel API/CLI/progress/compatibility/fault tests** and **792 sdist tests, 40 explicit skips** per interpreter. The source artifact includes the pre-move API fixture and new fault tests, while the wheel includes every extracted runtime family. These development-only environments omit optional data/DICOM extras and exercise extracted test support against installed application code. Ruff/mypy checked **67 source files**, documentation built and all **26** present OpenSpec changes passed strict validation. The additional format-expansion proposal is outside the original 22-change review roadmap and this B1/C5 implementation slice.

B2 local slice on **2026-10-04** is implemented through [add-structural-output-validation](changes/add-structural-output-validation/proposal.md): every publishable encoder declares a structural validator; unknown/missing validation and malformed output fail closed. Decoded streams, supported raster frames and Arrow/Feather/ORC logical content are compared. Whole-file PDF protection gates qpdf/pikepdf/Ghostscript and AI wrappers; original/walked/qpdf alternatives are retained through selection, and `--pdf-linearize` is explicit across CLI/library/bulk/workers. Complete remaining data/media/image metadata and fidelity contracts remain open, so B2 is **partial**. [Evidence and limits](changes/add-structural-output-validation/evidence.md) record **1217 checkout tests passed, 44 skipped**, **106 structural cases**, **109 PDF cases**, successful Ruff/mypy (**79 files**), documentation and **26** strict OpenSpec checks. Final fresh artifact installations on Python **3.9 and 3.13** each passed **344 wheel tests, 3 skips** and **1144 sdist tests, 89 skips**, with no checkout-runtime fallback. Optional skips and local macOS results do not establish wider format/platform/deployment guarantees.

Before the 2026-10-07 reconciliation, `openspec list --specs` reported no canonical specifications. The completed active changes [add-chisel-parity](changes/add-chisel-parity/proposal.md), [add-dicom-support](changes/add-dicom-support/proposal.md), and [improve-lossy-pdf-compression](changes/improve-lossy-pdf-compression/proposal.md), together with historical archives, remain intact. Their completed checklists alone do not prove every promised behavior exists in code.

Six MODIFIED requirement blocks use named requirements from those completed active changes as their reviewed historical baseline:

| New change | Capability | Replaced requirement |
| --- | --- | --- |
| [fix-markup-preservation](changes/fix-markup-preservation/proposal.md) | `xml-json` | JSON Identification and Minification; XML Identification and Minification |
| [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md) | `dicom` | Unsafe DICOM Instances Are Skipped; DICOM Output Verification |
| [add-structural-output-validation](changes/add-structural-output-validation/proposal.md) | `nested-assets` | Lossless PDF Stream Walking |
| [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md) | `encoder-quality` | Keep Metadata Flag |

Audit actual implementation and deployment status through the C6 portion of [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) before integrating or archiving these deltas. Establish only the implemented current baseline; record broader reader, resource and platform gaps explicitly. The PDF Flate branch is implemented in the current working tree. Reconcile each MODIFIED block against that baseline, and confirm that ADDED requirement names are still new when integration occurs. Canonical `openspec/specs/` must not be populated with unimplemented roadmap requirements.

The baseline audit can start early. The complete quality-gates change depends on distribution support for its installed-artifact CI work; this does not prevent an earlier read-only C6 baseline audit.

## Change catalog

Priority comes from the reviewed risk/value; dependencies determine implementation order. P0 focuses on confirmed preservation/overwrite hazards, P1 on trustworthy execution and near-term improvements, P2 on maintenance and growth, and P3 on later PDF expansion. A change spanning several slices can be delivered incrementally; for example the Parquet metadata and ODF package fixes are early A6 work, while broader data streaming and registry work belong to C.

| Change | Scope | Priority | Plan slices | Prerequisite changes |
| --- | --- | --- | --- | --- |
| [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md) | Preserve complete archive member sets | P0 | A1 | None |
| [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md) | Rebuild compressed tar archives with exactly one tar payload | P0 | A2 | None |
| [fix-markup-preservation](changes/fix-markup-preservation/proposal.md) | Preserve XML text and JSON lexical values during minification | P0 | A3 | None |
| [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) | Protect destinations and honor standalone library output paths | P0 | A4 | None |
| [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md) | Inspect complete DICOM datasets and verify lossless output | P0 | A5 | None |
| [update-data-format-preservation](changes/update-data-format-preservation/proposal.md) | Preserve data-file schema, metadata, framing, and SQLite snapshots | P0 | A6, C4 | None |
| [update-container-format-policies](changes/update-container-format-policies/proposal.md) | Preserve specialized package structure and protected container integrity | P1 | A6, B2, C1 | [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md), [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md) |
| [fix-distribution-test-support](changes/fix-distribution-test-support/proposal.md) | Include complete test support in source distributions | P1 | A7 | None |
| [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md) | Centralize typed candidate transactions and destination-local publication | P1 | B1, C5 | [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) |
| [add-structural-output-validation](changes/add-structural-output-validation/proposal.md) | Require structural validators and protect PDFs before every rewrite path | P1 | B2 | [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md), [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md), [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md), [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md) |
| [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) | Expose typed outcomes and clean machine-readable CLI output | P1 | B3, C5 | None |
| [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md) | Bound bulk scheduling and account for cancellation and conflicts | P1 | B4 | [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |
| [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md) | Enforce cumulative decode, nesting, scratch, and process budgets | P1 | B5 | [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md), [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md) |
| [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md) | Make media fidelity explicit and preserve all supported streams and frames | P1 | B6 | [add-structural-output-validation](changes/add-structural-output-validation/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |
| [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md) | Unify format metadata and validate tool and extra capabilities | P2 | C1, C5 | [update-container-format-policies](changes/update-container-format-policies/proposal.md), [add-structural-output-validation](changes/add-structural-output-validation/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |
| [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) | Verify preservation, platforms, extras, and the canonical specification baseline | P2 | C2, C3, C6 | [fix-distribution-test-support](changes/fix-distribution-test-support/proposal.md) |
| [add-inspection-command](changes/add-inspection-command/proposal.md) | Add bounded read-only file inspection and operation planning | P1 | D — inspection | [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md), [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md) |
| [add-audit-reports](changes/add-audit-reports/proposal.md) | Add persistent versioned audit reports for every processing outcome | P2 | D — audit | [update-repack-outcomes](changes/update-repack-outcomes/proposal.md), [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md), [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) |
| [add-resumable-bulk](changes/add-resumable-bulk/proposal.md) | Add safe checkpoint manifests and resumable bulk processing | P2 | D — resume | [add-audit-reports](changes/add-audit-reports/proposal.md), [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md), [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) |
| [add-optimization-profiles](changes/add-optimization-profiles/proposal.md) | Add versioned optimization profiles and predictable execution budgets | P2 | D — profiles | [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md), [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md), [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md), [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) |
| [add-archive-member-selection](changes/add-archive-member-selection/proposal.md) | Add archive-member exclusions, optimization depth and category selection | P2 | D — member selection | [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md), [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md), [update-container-format-policies](changes/update-container-format-policies/proposal.md), [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md), [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |
| [extend-lossless-pdf-stream-walking](changes/extend-lossless-pdf-stream-walking/proposal.md) | Complete lossless PDF Flate-image handling and traverse nested form resources | P3 | D — PDF stream expansion | [add-structural-output-validation](changes/add-structural-output-validation/proposal.md), [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md), [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |

## Delivery order and gates

1. **A — preservation fixes:** deliver complete member manifests, explicit compressed-tar layers, lexical markup safety, collision-safe destinations, full DICOM inspection, the Parquet/ODF fixes, and complete source-distribution tests. Retain a regression fixture for each confirmed defect. No candidate may publish missing content, unintended value/text changes, broken protection, or unrelated overwrites.
2. **B — execution contracts:** establish the shared transaction and typed outcome boundaries, then structural/preservation validation, bounded batch lifecycle, shared resource budgets, and the explicit media fidelity migration. Every known input must reconcile to a terminal outcome, and interrupted workers must leave usable originals and accounted partial results.
3. **C — maintainability:** consolidate tested capability metadata, executable/config diagnostics, platform/extras/artifact CI, data batch/snapshot policy, typed codec boundaries, benchmark/coverage evidence, and the canonical specification baseline. Begin independent baseline/fixture work earlier when useful; gate advertised support on real writer evidence.
4. **D — features:** inspection follows capability/outcome/budget work; reports follow outcome/batch work; resume follows reports; profiles follow preservation/resource/benchmark contracts; member selection follows manifest/protection/context contracts; deeper PDF walking follows protection and image/whole-file verification. The catalog's prerequisite lists are authoritative rather than a blanket requirement that all C work finish before all D work.

A valid dependency order for individual proposals is:

1. [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md)
2. [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md)
3. [fix-markup-preservation](changes/fix-markup-preservation/proposal.md)
4. [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md)
5. [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md)
6. [update-data-format-preservation](changes/update-data-format-preservation/proposal.md)
7. [update-container-format-policies](changes/update-container-format-policies/proposal.md)
8. [fix-distribution-test-support](changes/fix-distribution-test-support/proposal.md)
9. [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md)
10. [add-structural-output-validation](changes/add-structural-output-validation/proposal.md)
11. [update-repack-outcomes](changes/update-repack-outcomes/proposal.md)
12. [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md)
13. [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md)
14. [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md)
15. [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md)
16. [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md)
17. [add-inspection-command](changes/add-inspection-command/proposal.md)
18. [add-audit-reports](changes/add-audit-reports/proposal.md)
19. [add-resumable-bulk](changes/add-resumable-bulk/proposal.md)
20. [add-optimization-profiles](changes/add-optimization-profiles/proposal.md)
21. [add-archive-member-selection](changes/add-archive-member-selection/proposal.md)
22. [extend-lossless-pdf-stream-walking](changes/extend-lossless-pdf-stream-walking/proposal.md)

This is one topological order, not a delivery date or a claim that independent items cannot run concurrently. Read each design's migration plan before a change that alters defaults or fidelity: output collisions, SQLite replacement, protected containers, candidate validation, and video defaults include explicit compatibility decisions.

## Review-to-spec traceability

| Source finding, slice, or feature | Proposals |
| --- | --- |
| R01 | [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md) |
| R02 | [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md) |
| R03 | [fix-markup-preservation](changes/fix-markup-preservation/proposal.md) |
| R04 | [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) |
| R05 | [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md) |
| R06 | [fix-markup-preservation](changes/fix-markup-preservation/proposal.md), [update-data-format-preservation](changes/update-data-format-preservation/proposal.md) |
| R07 | [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) |
| R08 | [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md) |
| R09 | [update-container-format-policies](changes/update-container-format-policies/proposal.md), [add-structural-output-validation](changes/add-structural-output-validation/proposal.md) |
| R10 | [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md) |
| R11 | [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |
| R12 | [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md) |
| R13 | [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md) |
| R14 | [update-container-format-policies](changes/update-container-format-policies/proposal.md), [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md) |
| R15 | [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md), [fix-distribution-test-support](changes/fix-distribution-test-support/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md), [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md), [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) |
| A1 | [fix-archive-member-preservation](changes/fix-archive-member-preservation/proposal.md) |
| A2 | [fix-compressed-tar-roundtrip](changes/fix-compressed-tar-roundtrip/proposal.md) |
| A3 | [fix-markup-preservation](changes/fix-markup-preservation/proposal.md) |
| A4 | [fix-output-destination-safety](changes/fix-output-destination-safety/proposal.md) |
| A5 | [fix-dicom-safety-validation](changes/fix-dicom-safety-validation/proposal.md) |
| A6 | [update-data-format-preservation](changes/update-data-format-preservation/proposal.md), [update-container-format-policies](changes/update-container-format-policies/proposal.md) |
| A7 | [fix-distribution-test-support](changes/fix-distribution-test-support/proposal.md) |
| B1 | [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md) |
| B2 | [update-container-format-policies](changes/update-container-format-policies/proposal.md), [add-structural-output-validation](changes/add-structural-output-validation/proposal.md) |
| B3 | [update-repack-outcomes](changes/update-repack-outcomes/proposal.md) |
| B4 | [update-bulk-execution-lifecycle](changes/update-bulk-execution-lifecycle/proposal.md) |
| B5 | [add-operation-resource-budgets](changes/add-operation-resource-budgets/proposal.md) |
| B6 | [update-media-preservation-policy](changes/update-media-preservation-policy/proposal.md) |
| C1 | [update-container-format-policies](changes/update-container-format-policies/proposal.md), [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md) |
| C2 | [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) |
| C3 | [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) |
| C4 | [update-data-format-preservation](changes/update-data-format-preservation/proposal.md) |
| C5 | [refactor-repack-transactions](changes/refactor-repack-transactions/proposal.md), [update-repack-outcomes](changes/update-repack-outcomes/proposal.md), [refactor-format-capability-registry](changes/refactor-format-capability-registry/proposal.md) |
| C6 | [update-quality-and-specification-gates](changes/update-quality-and-specification-gates/proposal.md) |
| N01 | [add-inspection-command](changes/add-inspection-command/proposal.md) |
| N02 | [add-audit-reports](changes/add-audit-reports/proposal.md) |
| N03 | [add-resumable-bulk](changes/add-resumable-bulk/proposal.md) |
| N04 | [add-optimization-profiles](changes/add-optimization-profiles/proposal.md) |
| N05 | [add-archive-member-selection](changes/add-archive-member-selection/proposal.md) |
| N06 | [extend-lossless-pdf-stream-walking](changes/extend-lossless-pdf-stream-walking/proposal.md) |

## Review and validation workflow

1. Open a proposal, its design, tasks, and all capability delta files. Review dependencies, breaking behavior, failure paths, and preservation scenarios.
2. Confirm the current code/spec baseline and resolve overlap with other active deltas. Shared capabilities deliberately have distinct new requirement names; only the validation change owns the replacement of **Lossless PDF Stream Walking**, while the later PDF expansion adds detailed requirements.
3. Review the current proposal before implementation as required by [OpenSpec project instructions](AGENTS.md). The user's instruction to start applying this roadmap authorizes implementation; resolve any later scope changes against that instruction without asking for the same approval again.
4. Implement the approved tasks with the specified regression/real-format/fault-injection checks, preserving legacy CLI/library entry points where stated.
5. Run `openspec validate <change-id> --strict` and applicable code, artifact, platform, and benchmark checks. Mark implementation checkboxes only when actual work has passed its checks.
6. Archive only after deployment status is confirmed and the canonical baseline is reconciled; validate the resulting current specifications.

For the proposal set, run:

```sh
openspec validate --all --strict --no-interactive
```

Strict OpenSpec validation checks proposal/delta structure. It does not establish runtime preservation, platform support, performance, or deployment; those checks remain explicit implementation tasks.
