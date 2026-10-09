## 1. Reviewable feasibility work

- [x] 1.1 Review primary OfficeArt/DOC/XLS/PPT specifications and existing changes.
- [x] 1.2 Acquire pinned redistributable EMF/WMF examples for all three hosts.
- [x] 1.3 Build a checksum-bound development codec and host relocation experiments.
- [x] 1.4 Independently compare decoded content, surrounding bytes, references,
  directory metadata and rendered pages; measure compaction separately.
- [x] 1.5 Add corruption and reference fault tests, document measured limitations
  and validate this proposal before requesting runtime approval.

## 2. Runtime implementation after proposal approval

- [x] 2.1 Implement a bounded common OfficeArt parser/EMF/WMF encoder with a
  complete preservation fingerprint, independent of the development allocator.
- [x] 2.2 Qualify DOC Data/PICF discovery from complete character formatting,
  including piece/style inheritance, reference aliases and binary/OLE distinctions.
- [x] 2.3 Qualify XLS drawing-group/CONTINUE parsing, audited host record versions
  and all affected BoundSheet/Index/ExtSST/other file pointers.
- [x] 2.4 Qualify PPT live drawing-group references and Pictures record placement;
  define composition with the existing embedded-storage rewrite.
- [x] 2.5 Extend and independently qualify native root-stream replacements.
- [x] 2.6 Register a separate verifier and bounded worker; compare every candidate
  to the verified compaction baseline and route all Office aliases consistently.
- [x] 2.7 Integrate detailed diagnostics and document supported/unsupported cases.

## 3. Runtime qualification and delivery

- [x] 3.1 Test malformed envelopes, nested lengths, stale/duplicate/missing
  references, CFB metadata changes and unrelated stream/record changes.
- [x] 3.2 Test protection/macros/unknown records, optional encoders/backends,
  budgets, cancellation, dry-run, thresholds, output safety and nested archives.
- [x] 3.3 Run renderer/local native, source/artifact and required static/
  documentation/specification checks; extend native platform CI coverage and
  report the measured supported subset and unexecuted platform checks.

## 4. Deferred follow-on raster image qualification

This section is outside the approved initial EMF/WMF runtime delivery.

- [x] 4.1 Define and measure lossless PNG chunk/pixel and JPEG coefficient,
  metadata, color and UID/reference preservation contracts on parsed BLIPs.
- [x] 4.2 Obtain approval for the concrete image contract before enabling it;
  reuse the common adapters only where those contracts are qualified.

## Feasibility evidence

- Four exact real originals plus encoding-only zlib 0/1 controls, two encoders:
  24/24 intended-content/CFB comparisons and 24/24 equal rendered page sets.
- Original embedded DOC and mixed-image XLS each save 1,024 additional physical
  bytes beyond strict compaction. Original vector DOC/PPT save 74/149 stream
  bytes with Zopfli but no additional file allocation.
- 108 new development tests passed, including corrupt envelopes, encoder output,
  UID/geometry changes, unrelated streams/metadata, stale pointers and valid
  pointers to the wrong sheet. Both one/two-UID codec layouts are exercised;
  only real single-UID layouts have renderer evidence.
- Combined new/previous development and five native OLE regression modules:
  358 passed. Focused Ruff/Mypy and strict validation of this and both completed
  OLE changes passed. Source fixture SHA-256 values remain unchanged.
- The pre-approval stage changed no runtime, CLI, dependency or native helper.
  Its evidence remains separate from the runtime qualification below.


## Initial runtime delivery evidence (2026-10-04)

- Common production codec, three discovery/relocation adapters, independent
  `officeart` verifier and fixed native root-stream replacement modes are enabled
  through the existing opt-in option. Native helper is 0.3.0; production imports
  no development/test allocator or checksum-bound fixture code.
- 125 runtime tests pass both with qualified Zopfli and with Zopfli absent.
  Real originals, encoding-only controls, aliases, wrappers/UIDs/geometry,
  references/host record families, unrelated content/CFB metadata, optional
  capabilities, root budgets, cancellation, interruption cleanup, archives,
  output/backup policies and verbose/JSON/bulk diagnostics are exercised.
- Public API renderer report: 12/12 preservation and RGB page-set comparisons,
  source fixture checksums unchanged. Actual worker usage and separately measured
  strict compaction are recorded in `dev/ole/qualification-officeart-runtime.json`.
- Full source: 1,618 passed / 156 skipped. Fresh wheel: 781 passed / 22 skipped;
  fresh sdist: 1,618 passed / 156 skipped. Artifact import provenance, exports,
  fixtures/native sources, CLI and license gates passed. Ruff, focused Mypy
  (ten runtime/CLI/worker/verifier modules), native fmt/release/Clippy,
  documentation build and strict validation of this/earlier OLE changes passed.
  Full Mypy retains four existing `mat.py` operand errors; no new errors.
- Local platform: macOS arm64. Linux/macOS/Windows native CI includes the new
  runtime suite; remote CI execution and Microsoft Office repair/renderer behavior
  are not claimed as locally observed results.
- Original embedded DOC and mixed-image XLS each save 1,024 physical bytes beyond
  compaction. Original vector DOC retains compaction despite smaller metafile
  streams; original PPT selects its existing smaller embedded-storage candidate.
- Supported record/reference boundaries are documented explicitly; broadening
  populated XLS pointer families or PNG/JPEG rewriting needs further qualification.
- Project-local `venv` contains the current editable CLI, recompression extras and
  native writer 0.3.0. Activate it to avoid the older system CLI found during smoke
  checks. No source corpus file was rewritten by these checks.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.

The raster follow-on tasks are fulfilled by the separately approved and implemented
[add-officeart-raster-recompression](../add-officeart-raster-recompression/proposal.md)
contract and its qualification records; the historical initial vector delivery
scope above is preserved.
