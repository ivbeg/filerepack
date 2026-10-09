# B2 local implementation evidence

The user authorized applying the reviewed roadmap on 2026-10-02 and continued the
implementation. This change remains partial while the broader preservation
contracts in `tasks.md` are incomplete. No deployment or archival is asserted.

## Implemented behavior

- Writers must declare structural validators; missing/unknown adapters, unavailable
  parsers and decoder/structural failures refuse publication and log a reason.
- Compressed streams compare decoded hashes. Supported JPEG/PNG/GIF/WebP/TIFF paths
  compare decoded frames/pixels; Arrow/Feather/ORC compare schemas, metadata and
  ordered values. Existing archive, Parquet, DICOM and native proofs remain active.
- PDF protection is inspected across the whole object table before every writer,
  including qpdf/Ghostscript, AI wrappers and direct pikepdf walking. Marker fixtures
  are structurally real PDFs; they do not establish cryptographic signature validity.
  A separate fixture uses real encryption.
- Lossless PDF selection retains original, walked and qpdf-from-original/walked
  alternatives. Failed, malformed, changed or larger qpdf output cannot discard a
  smaller verified walked candidate. Original bytes win ties/larger compression.
- Explicit `--pdf-linearize` / `RepackOptions(pdf_linearize=True)` reaches CLI,
  library, AI and bulk/workers. Lossy linearization verifies qpdf against the
  Ghostscript stage. Candidate publication rechecks preservation within its snapshot.

## Verification

Final local checks on **2026-10-04**, macOS/Python 3.9:

- Full checkout suite: **1217 passed, 44 explicit optional/platform skips**, with
  pydicom 2.4.4, NumPy 2.0.2, pyjpegls 1.5.1, PyArrow 21, Pillow 11.3 and pikepdf
  9.11. FITS/Astropy and other absent integrations remain skips, not established
  guarantees. Actual second-filesystem tests also skip on this host.
- New B2 corpus: **106 structural/preservation/process cases** and **109 PDF
  protection/selection/linearization cases**. Focused B2 plus archive/package
  regression run: **340 passed**. The full run also retains all prior API,
  transaction, archive, data and DICOM regressions.
- Ruff and mypy passed across runtime/tests/distribution tooling; mypy checked
  **79 source files**. The Docusaurus build passed. Strict validation of all
  **26** active OpenSpec changes passed.
- Fresh installed artifacts on both Python **3.9 and 3.13**: **344 wheel tests,
  3 explicit extra skips**, and **1144 sdist tests, 89 explicit optional/platform
  skips** per interpreter. Installed CLI/API/preservation smoke checks, runtime
  import provenance, complete source-test support, wheel runtime-only contents,
  entry points and SPDX/license metadata passed. Development-only artifact
  environments omit data/DICOM/FITS/font extras.
- Python 3.13 exercised pikepdf **10.16** and Pillow **12.3**. The PDF fixture now
  includes explicit page resources so the stricter parser reports no repair
  warning. Image enumeration uses the supported nonrecursive API when available;
  nested-form expansion is not implied.
- Runtime/test/config hashes matched the validated artifact build at the end of
  verification. Final artifacts are in
  `/tmp/filerepack-b2-verified-20261004-artifacts`; logs are in
  `/tmp/filerepack-b2-{full,build,docs,openspec,dist-py39,dist-py313}-20261004.log`.

Reproduce the installed checks with
`python dev/validate_distribution.py` (fresh build), or pass `--artifacts` to
validate an existing source/wheel pair. Ubuntu CI installs qpdf for artifact
checks, but no remote CI/Linux/Windows result is asserted.

## Limits and remaining work

- Complete other data/media/image fidelity and metadata contracts (task 1.3b).
  Full media decoding establishes structure, not preservation of all streams/timing.
- Local verifier bounds do not complete shared operation resource budgets or bound
  all parser allocations. Unsupported raster/depth/ICNS variants refuse acceptance.
- PDF lossless comparison needs qpdf 11+; qpdf warnings and unsupported residual
  filters fail closed. It excludes xref/encoding fields, object numbers and volatile
  trailer IDs while retaining the document/custom trailer graph and decoded streams.
- PDF Flate-image/nested-form expansion, rendering/application conformance,
  cryptographic signature authentication, Linux/Windows evidence, rollout and
  canonical-baseline reconciliation remain separate work.

Parser contracts follow [qpdf JSON](https://qpdf.readthedocs.io/en/stable/json.html),
[qpdf structural checks](https://qpdf.readthedocs.io/en/stable/cli.html),
[pikepdf parser controls](https://pikepdf.readthedocs.io/en/stable/api/main.html) and
[Pillow verification](https://pillow.readthedocs.io/en/stable/reference/Image.html).
