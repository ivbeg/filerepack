## 1. Implementation

- [x] 1.1 Add realistic PDF fixtures for Flate predictors, nested forms, shared XObjects, cycles, masks, ICC/indexed colors and unsupported chains.
- [x] 1.2 Implement bounded recursive resource discovery and once-per-object optimization accounting.
- [x] 1.3 Implement eligible Flate sample decode/recompression with PDF-compatible filter/parameter updates.
- [x] 1.4 Add decoded sample/semantic checks and whole-document candidate validation before publication.
- [x] 1.5 Propagate selection/fidelity/metadata/resource context and emit explicit unsupported/skipped image reasons.
- [x] 1.6 Document supported Flate cases, optional dependencies, protection behavior, and remaining limitations.

## 2. Verification and documentation

- [x] 2.1 Verify exact decoded image samples, masks, color/decode semantics, dimensions and bit depth for accepted Flate/DCT/JPX candidates.
- [x] 2.2 Render real before/after pages with a pinned renderer/settings and compare pixels for nested forms, transparency and color fixtures.
- [x] 2.3 Verify shared streams encode once, references remain intact and resource cycles/deep graphs stay within limits.
- [x] 2.4 Test protected/uncertain PDFs, missing pikepdf, lossy selection, unsupported filter chains and larger rebuilt candidates; originals stay intact when ineligible.
- [x] 2.5 Check per-object work accounting versus whole-file savings and rerun the original completed parity PDF scenarios under the updated protection contract.
- [x] 2.6 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.7 Validate this change with `openspec validate extend-lossless-pdf-stream-walking --strict`; reconcile the canonical baseline before archive and record deployment status separately.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.

## Additional qualification — 2026-10-08

DCT Gray/RGB/CMYK and JPX Gray/RGB/RGBA controlled native files now
exercise accepted smaller streams, exact decoded samples, host dimensions/
depth/Decode/soft-mask/alpha semantics, full object graph and Poppler 26.05.0
page comparisons at 72 dpi. Standalone OpenJPEG 2.5.4 confirms each component
precision; a genuine 16-bit stream mislabeled as 8-bit in the PDF is refused
before publication. Broader high-depth/signed/subsampled JPX profiles remain
unavailable. The three implementation requirements are reconciled into the
canonical baseline; deployment remains unconfirmed.
