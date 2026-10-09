---
title: Quality evidence and remaining gates
---

# Quality evidence and remaining gates

Local qualification uses macOS arm64 and Python 3.13.7. The repository keeps
checksums, pinned source URLs, reader versions, all-attempt outcomes and sampling
limits in its development reports. A checked implementation task describes its
recorded fixture/profile scope. Release, remote CI and deployment are separate.

## Fixed-corpus profiles

The frozen corpus contains 20 complete public files from ten available format
families, totaling 10,713,328 bytes. Each profile processed the same hashes and
tool versions. Failed, unchanged, unavailable-verification and resource-limited
attempts stay in the denominator.

| Profile | Verified final bytes saved | Elapsed seconds | Verified smaller files | Sampled peak RSS MiB | Sampled peak work MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| fast | 3,850,463 | 6.598 | 11/20 | 247.2 | 4.31 |
| balanced | 3,850,463 | 6.237 | 11/20 | 247.5 | 4.31 |
| maximum | 3,850,510 | 8.348 | 12/20 | 247.7 | 4.31 |
| preserve | 3,850,463 | 6.364 | 11/20 | 247.5 | 4.31 |

The 2026-10-08 run follows the stricter PNG depth/color-type checks. Maximum
saved 47 additional bytes and took about 34% longer than balanced on
this corpus. Several adapters use fixed effort settings, so fast/balanced can
produce the same result. Preserve changes incidental-metadata retention.
None of these profiles enables loss by itself.

Every profile also had two failed attempts, one SVG whose independent rendering
comparison was unavailable, and one resource-limited WebP. These outcomes
contribute zero verified savings. No independently comparable case had a
preservation mismatch. One additional accepted rewrite per profile lacks that
independent SVG-rendering proof. Staged inner candidates saved 13,048 bytes per
profile; that figure is separate from final published bytes.

RSS and work space were sampled every 100 ms, so short peaks can be missed.
Work space includes input/output copies and owned scratch. This small corpus
establishes these observations, rather than population-wide performance or
coverage of every writer. The report records the frozen adapter/harness hashes.

All eight PNG results also passed independent source/output header and checksum
comparisons. Keeping their original depth/color type saves 11,320 fewer bytes
than the earlier default run. Cross-date elapsed-time differences include other
runtime/environment changes and do not establish an isolated speed improvement.

Evidence: [current profile receipts](https://github.com/ivbeg/filerepack/blob/master/dev/quality/profiles-2026-10-08.json)
and [reproduction harness](https://github.com/ivbeg/filerepack/blob/master/dev/benchmark_profiles.py).

## WARC selection and native assets

WARC qualification adds four pinned warcio captures and thirteen controlled
cases covering binary/compressible payloads, request/metadata/revisit records
and 16 KiB–1 MiB payload boundaries. The two modes process 1,942,763 source bytes
each. Normal selection saves 6,853 bytes; ultra saves 7,285 bytes. The latest
recorded runs took 2.902 and 9.755 seconds, with sampled RSS peaks of 36.9 and
101.4 MiB. All 34 attempts preserve decoded record hashes and satisfy the
publication contract. A non-chunked original retained on size grounds keeps
its original multi-record gzip member intact.

Zopfli trials use at most 512 KiB per complete framed record and 15 iterations.
The 512 KiB payload controls exceed this cutoff once framing is included, and
therefore skip that trial. The measured benefit remains small on this corpus;
large incompressible data uses source/zlib selection. Twenty-millisecond RSS
and work-space sampling can miss brief peaks and includes final/input files.
Evidence: [WARC selection report](https://github.com/ivbeg/filerepack/blob/master/dev/warc/selection-2026-10-07.json).

CAR qualification used six temporary copies of installed catalogs and saved
82,560 bytes in total. Apple's assetutil descriptions matched across 975
renditions, and 953 complete allocated CSI block digests matched their native
reported values. Five catalogs passed native validation; SSHProxy retained its
existing native validation failure. Original catalogs stayed unchanged.
Evidence: [CAR native report](https://github.com/ivbeg/filerepack/blob/master/dev/car/qualification-2026-10-07.json).

PDF fixtures cover shared/nested Forms, cycles, transparency, masks, ICC/Indexed
colors and 16-bit Flate gray samples. DCT 8-bit Gray/RGB/CMYK and JPX unsigned
unsampled 8-bit Gray/RGB/RGBA cases verify host dimensions, depth, decode/mask/
alpha semantics and native decoded samples. Poppler 26.05.0 rendered before/after
pages at 72 dpi with identical pixels. Standalone OpenJPEG 2.5.4 confirms component
precision, and mislabeled genuine 16-bit JPX is refused. These compressed-image
cases use controlled native files and removable comments/free boxes. Other
image codecs' complete encoded-depth proof remains open.
Evidence: [raster qualification](https://github.com/ivbeg/filerepack/blob/master/dev/quality/raster-qualification-2026-10-08.json).

WOFF/WOFF2 fixtures use fontTools 4.66/Brotli 1.2
and compare decoded table bytes, metadata and private payloads. These fixture
checks retain their stated formats and reader limits.

## Coverage and configured CI

The recorded full checkout run on 2026-10-08 passed 2,361 tests with three
filesystem-related skips. Its measured line coverage was 76.12%, with 62.44%
branch coverage. These are dated results, not a claim about every subsequent
checkout; see the [check receipts](https://github.com/ivbeg/filerepack/blob/master/dev/quality/checks-2026-10-07.json).
Coverage excludes work performed in isolated child interpreters unless a child
coverage configuration is explicitly supplied. The checker enforces 90% line
coverage for shared transactions/candidates/destinations, 85% for option
validation/reports and 70% for the broad verifier. The verifier target remains
90%; numeric coverage does not replace preservation assertions.

CI retains core Python 3.9–3.13 and installed-artifact 3.9/3.13 checks. Configured
Linux/macOS/Windows lanes exercise process/filesystem contracts; optional-reader,
scientific-native and OLE-native lanes exercise real integrations. These remote
job results are not established by the linked local evidence. A new Python version becomes
qualified after its core/artifact/representative-reader checks pass.

## Open qualification

Full cumulative accounting across every legacy parser/validator and native
buffer, actual backend create/read capability probing, broad package-alias
policy and application-produced ODF/EPUB reader evidence remain open. The
scientific reports retain gates for MATLAB, historical R/standalone LibTorch
readers, independent real ZSAV/Zarr origins, broader TIFF/GeoTIFF/COG and
representative cold-read/resource measurements. Safetensors, GGUF, ONNX and
DCP have passive inspection; qualified compression writers are absent.

The complete working-tree status and individual remaining items are in the
[completion audit](https://github.com/ivbeg/filerepack/blob/master/dev/quality/completion-2026-10-07.md).
