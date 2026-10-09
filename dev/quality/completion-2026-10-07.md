# Implementation reconciliation — 2026-10-07, updated 2026-10-08

The original backlog had 318 unchecked items across 41 of 55 active changes.
This continuation completes **246 additional items**: **33 changes now have
fully checked implementation lists**, while **22 changes retain 72 items**.
The remaining work includes implementation and external qualification; it is
not all a deployment dependency. No change has been archived and no release,
push or deployment is claimed.

## Delivered and integrated

- Typed terminal outcomes, parseable JSON/CSV and reconciled outer/member accounting.
- Bounded bulk scanning/submission, central destination/backup reservations,
  drain on interruption, scan/dispatch failure and persistence failure.
- Root and aggregate worker resource grants, owned process supervision,
  isolated standard-stream decode/encode and bounded peeking.
- Read-only inspection, schema-v1 JSON/JSONL audits with bounded tool/library/
  validator evidence and recoverable partial files.
- Content-verified resume, converted-output identity checks, explicit filters,
  runtime/profile/tool/Python-library fingerprints and corrupt-state refusal.
- Versioned profiles with explicit false/default overrides and fixed-corpus
  measurements; member/category/depth controls inherited through nested helpers.
- Preserving Arrow/Feather/ORC/Avro and SQLite snapshot/offline paths, recursive
  PDF Flate/Form walking, presentation metadata, stream-copy media inventory,
  isolated preserving web fonts, native CAR and archived tracev3 profiles.
- Configured platform/optional/native CI, measured shared-core coverage floors,
  current contributor documentation and a reconciled canonical specification baseline.
- PNG bit-depth/color-type checks before candidate selection, bounded JPEG/JPX
  encoded-precision checks, and preservation checks on the shared ImageMagick,
  AVIF/HEIC/JXL lossless publication paths.

These bullets describe implemented subsets. The following evidence and open
items establish their actual scope.

## Verification

| Check | Result and scope |
| --- | --- |
| Current full checkout | 2,361 passed, 3 skipped in 281.29 s, with line/branch coverage |
| Final contract/media subset | 95 passed after final fingerprint/audit additions and Mutagen provisioning |
| Full installed wheel | 1,076 passed, 24 explicit optional skips |
| Full installed sdist | 2,133 passed, 167 explicit optional skips |
| Latest wheel and sdist contract subset | 238 passed, 3 optional skips in each fresh environment |
| Native raster/PDF subset | 45 passed; expanded raster/media/structural subset 427 passed |
| Static checks | Ruff passed; mypy passed on 169 source files, including provisioned Mutagen types |
| Documentation | Docusaurus production build passed |
| OpenSpec | All 103 current changes/specifications passed strict validation |
| Ownership | 180 canonical requirements, 245 unique live deltas, 281 historical/active blocks audited |

The current full run covers the final runtime, including fingerprint/audit,
cover typing and raster precision changes. Its three skips are one case-colliding
store-key fixture unsupported by APFS and two unavailable second-filesystem
cases. Mutagen 1.48.1 is provisioned and its integration tests pass. Earlier full
artifact suites preceded the latest raster fixes; rebuilt artifacts exercise
those fixes through the expanded contract subset and import-provenance checks.
Their two ONNX-extra skips and one absent-Mutagen integration do not establish
qualification of those families.

Measured full-run line coverage is **76.12%**, branch coverage **62.44%**.
Shared line coverage is transactions 95.48%, candidates 92.39%, destinations
94.37%, option validation 93.18%, reports 90.14%, verification 83.64%.
The enforced floors are 90/90/90/85/85/70%; the broad verifier target is 90%.
Child interpreter/native-worker execution is not automatically reflected in
parent coverage. Preservation and independent-reader assertions remain required.

Machine-readable evidence: [checks](checks-2026-10-07.json).

## Fixed-corpus measurements

All four profile runs use the same 20 hashes from ten available format families,
10,713,328 input bytes and pinned tool/runtime receipts. Fast/balanced/preserve
save 3,850,463 independently verified final bytes; maximum saves 3,850,510.
Elapsed times are 6.598/6.237/6.364/8.348 seconds respectively. Maximum adds
47 bytes for about 34% more time than balanced on this sample. The stricter PNG
contract saves 11,320 fewer bytes than the earlier default result, retaining
its encoded depth/color type. All eight public PNG output headers were compared
independently against the preserved input hashes.

Each profile retains two failed attempts, one independently unverifiable SVG
rendering comparison and one budget-limited WebP in its denominator, with zero
verified savings. No independently comparable case has a preservation mismatch.
Actual accepted rewrites are 12/12/12/13; verified smaller files are 11/11/11/12.
Inner candidate savings (13,048 per profile) are separate from final publication.
100 ms sampling can miss brief RSS peaks; work-directory size includes input,
output and owned scratch. This sample does not qualify every format or predict
population-wide speed. See [current profile receipts](profiles-2026-10-08.json).
The [earlier receipts](profiles-2026-10-07.json) retain their frozen runtime hash;
elapsed-time differences between dates are not an isolated speed comparison.

WARC qualification covers four pinned complete warcio captures plus thirteen
controlled record/boundary cases, normal and ultra, for 34 attempts. Normal saves
6,853 bytes and ultra 7,285 from 1,942,763 bytes per mode, taking 2.902/9.755 s
with sampled peak RSS 38,699,008/106,332,160 bytes. Every attempt has identical
record hashes and satisfies publication/unchanged-source checks. The retained
non-chunked original keeps its pre-existing multi-record gzip member. Zopfli is
limited to 15 iterations and 512 KiB per complete framed record; a 512 KiB
payload exceeds the cutoff once framing is added. 20 ms sampling can miss brief
peaks; input/final files are included in work size. See [WARC receipts](../warc/selection-2026-10-07.json).

CAR uses six temporary real-catalog copies, saving 82,560 bytes, with 975 native
rendition descriptions and 953 CSI block digests checked. Five catalogs pass
native validation; SSHProxy retains its pre-existing native failure. Sources
stay unchanged. See [CAR receipts](../car/qualification-2026-10-07.json).

Scientific provenance and all-attempt results remain in the
[earlier reproducible report](../format_survey/implementation-2026-10-04/README.md).
Generated/library-authored fixtures are identified separately from observational
sources. PDF raster checks use Poppler 26.05.0 at 72 dpi and equal pixels for the
qualified nested-form/color/mask/high-depth fixtures. Font checks compare exact
native decoded tables, metadata/private bytes and protected DSIG behavior.

DCT 8-bit Gray/RGB/CMYK and JPX unsigned unsampled 8-bit Gray/RGB/RGBA now
have controlled native accepted-candidate, mask/alpha/host-attribute and page
comparisons. Standalone OpenJPEG 2.5.4 confirms component precision; genuine
16-bit JPX mislabeled as 8-bit and mismatched host dimensions are refused.
These cases use removable comments/free boxes, not a broad observational PDF
corpus. Other image codecs' encoded-depth proof remains open. See
[raster qualification](raster-qualification-2026-10-08.json).

## Baseline reconciliation

[baseline-audit.json](../../openspec/baseline-audit.json) records 156 verified,
24 narrowed/corrected historical contracts, 92 pending broader requirements and
nine superseded overlap blocks. All 27 archived requirement blocks were audited;
archives themselves are preserved. Canonical specifications describe verified
working-tree behavior, with release/deployment status separate.

The six original overlap blocks are now owned by their later deltas. Three CPIO
MODIFIED blocks were moved into their actual CPBZ2 capability. Superseded original
text remains beside its original change; the legacy CPBZ2 filter contract remains
active. Verified ADDED deltas were rebased to MODIFIED against the named current
baseline. The ownership checker also verifies source/baseline requirement hashes
against the reviewed audit, preventing unaudited wording from appearing as proven.

## Remaining work

The [remaining-item inventory](remaining-2026-10-07.json) and change checklists
retain the full scope of 72 tasks. In particular:

- Finish cumulative accounting/isolation across every legacy parser, image/data
  buffer and validator; validate all nested effort/thread propagation.
- Qualify actual backend create/read capabilities and broader ZIP aliases,
  CAB/WIM policy and application-produced ODF/EPUB read-back.
- Expand independent data readers, large-group/backend-buffer measurements,
  other image codecs' encoded-depth proof and complete writer corpus coverage.
- Obtain real positive OfficeArt duplicate-image and extended DOC/XLS fixtures.
- Complete model-format corpus/native-reader feasibility before any writer;
  Safetensors/GGUF/ONNX/DCP remain inspection-only and DCP completeness remains unknown.
- Preserve the explicit scientific gates for MATLAB, historical R/standalone
  LibTorch readers, real independent ZSAV/Zarr origins, TIFF/GeoTIFF/COG and
  representative cold-read/resource costs.x
- Execute the configured Linux/macOS/Windows lanes, establish actual
  second-filesystem/native-store evidence and confirm deployment before archive.

## Reproduction

```bash
python -m pytest -q -ra --cov=filerepack --cov-report=json
python dev/check_coverage.py coverage.json
python dev/validate_distribution.py
ruff check filerepack test dev/validate_distribution.py dev/check_coverage.py dev/check_spec_ownership.py
mypy filerepack test dev/validate_distribution.py --ignore-missing-imports
python dev/check_spec_ownership.py
openspec validate --all --strict --no-interactive
(cd docs && npm run build)
```

Install optional extras/readers needed by the selected native checks; a missing
backend must be an explicit skip or unavailable result, not an early successful
return. Test inputs used by the corpus harness are temporary copies; source
caches and generated workspaces are not redistributed as qualification evidence.
