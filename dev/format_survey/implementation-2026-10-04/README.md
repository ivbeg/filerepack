# Implementation evidence, 2026-10-04

The seven proposals were approved by the user's implementation request. Runtime
code, options, transactions and trusted tests now exist for all seven workstreams.
MAT and existing ZSAV remain explicit experiments. The original change checklists
also contain release/corpus/platform gates that are still open; they must not all
be marked complete on the strength of the implementation alone.

## Reproducible inputs and methods

- [Pilot outcomes and native readers](pilot-results.json): the original complete
  checksummed Dataverse/Hugging Face sample; all attempts and bounded-out inputs
  remain in the denominator. Eight R sources have R 4.6.1 read-back in both wrapper
  profiles. SAV pairs were checked through ReadStat/pyreadstat 1.3.6. Only the reviewed
  pure-tensor BAAI checkpoint was additionally loaded natively; two numpy-bearing
  checkpoint origins remain passive-only measurements.
- [Additional HDF5/NetCDF/TIFF outcomes](scientific-results.json): 12 complete pinned
  public repository inputs from h5py, Unidata, xarray-data, rasterio and imageio.
  SHA-256, exact URL, repository commit and access conditions are recorded per input.
- [Complete Zarr key manifests](store-manifests.json): two complete pinned repository
  stores, 4 and 437 keys, 1,519 and 2,998,861 stored bytes. These are interoperability
  examples/fixtures, not two independent observational datasets or the earlier
  partial 5.572 GB Hugging Face store. Their full key sets were downloaded and verified.
- [Zarr all-attempt outcomes](store-results.jsonl) and [corrected upgrade attempt](store-upgrade-retry.json):
  ordinary native Zarr read-back passed. One upgrade attempt caught a real supervisor
  race between inventory and atomic chunk rename; missing transient names are now
  tolerated, a deterministic regression covers it, and the retry passed. The failed
  attempt remains recorded rather than being removed from costs/coverage.
- [Checkpoint method feasibility](checkpoint-method-gate.json) and
  [older Torch reader gate](checkpoint-reader-2.2.2.json): trusted tensor/view fixtures.
- [Final passive checkpoint framing checks](checkpoint-passive-final.json): all three
  original sources pass complete ZIP/ZIP64 validation in both profiles after stricter
  local-header/extra-field checks. This rerun does not load native user objects.
- [Additional complete SPSS origins](spss-extra-results.json): pinned Roche/pyreadstat,
  tidyverse/haven, jamovi and JASP inputs. A raw SAV and two already-bytecode SAVs
  had useful same-kind candidates with ReadStat read-back. Unknown multiple-response
  extensions and a nonstandard missing-value representation were refused. One real
  ZSAV interoperability sample passed and saved four bytes; this does not establish
  independent observational ZSAV corpus coverage.
- [Exact local dependency versions](environment.json). Rscript 4.6.1 and Homebrew
  h5repack/libhdf5 were used on macOS 26.5.1 arm64/APFS. `h5repack` has explicit earliest
  low/high library bounds; a backend default previously raised the superblock version.
  Current Python adapters used the bundled libhdf5/netcdf-c in their installed wheels.

Reproduce the passive pilot (its cache is in the earlier survey's ignored `runs`):

```bash
python -m pip install -e '.[dev,scientific,zarr]' scipy pandas pyreadstat
python dev/format_survey/implementation-2026-10-04/measure.py --output /tmp/format-candidates
python dev/format_survey/implementation-2026-10-04/download.py --output /tmp/pinned-corpus
python -m pytest -q test/test_scientific_formats.py
```

The pinned download script caps each file at 8 MiB and total bytes at 64 MiB and
checks SHA-256. Public unauthenticated access is not a blanket redistribution license;
consult each pinned repository/dataset license before redistributing its inputs.
No binary research corpora or generated checkpoints are added to the package.

## Observed gains and costs

Size acceptance below keeps the original size for every unchanged, larger, bounded-out
or unsupported input. Independent profiles are measured against originals, not chained.

| Sample / policy | Attempts | Smaller | Input bytes | Accepted output bytes | Saving |
|---|---:|---:|---:|---:|---:|
| Original R, preserve wrapper | 10 | 6 | 15,277,932 | 15,198,691 | 0.52% |
| Original R, explicit XZ | 10 | 8 | 15,277,932 | 14,076,464 | 7.86% |
| Original MAT, experimental existing envelope | 2 | 0 | 5,720,645 | 5,720,645 | 0% |
| Original PT, preserve mmap | 3 | 3 | 2,311,261 | 2,292,909 | 0.79% |
| Original PT, explicit load-only | 3 | 3 | 2,311,261 | 2,086,808 | 9.71% |
| Original SAV, same-kind bytecode | 2 | 0 | 274,464 | 274,464 | 0% |
| Additional SAV/ZSAV, including two refused representations | 7 | 4 | 119,223 | 104,411 | 12.42% |
| Additional H5, including undefined-fill NASA file | 3 | 0 | 7,748,955 | 7,748,955 | 0% |
| Additional NC, including two classic CDF skips | 3 | 1 | 303,028 | 286,218 | 5.55% |
| Additional TIFF | 6 | 1 | 3,343,626 | 3,192,595 | 4.52% |
| OME example store, preserve | 1 | 1 | 1,519 | 1,386 | 8.76% |
| Interoperability store, preserve | 1 | 1 | 2,998,861 | 2,969,454 | 0.98% |
| OME example store, compatible-upgrade | 1 | 1 | 1,519 | 966 | 36.41% |
| Interoperability store, compatible-upgrade retry | 1 | 1 | 2,998,861 | 2,858,173 | 4.69% |

R's two large decoded inputs still exceed the 32 MiB buffer profile. To reproduce
all eight eligible inputs, the pilot's cumulative node budget was explicitly raised
from 100,000 to 2,000,000; default limits reject some large character tables. RData
XZ attempts totalled 9.35 s; PT attempts totalled 1.15 s (default) and 1.53 s (load-only).
These figures include complete worker validation but exclude an ordinary-file staging
copy/publication. Source sizes are retained for all failed attempts.

Post-fix scientific worker measurements report sampled peak RSS and wall time:
about 37–65 MB sampled RSS for successful additional native inputs. These are 20 ms
supervisor samples, not exact allocation maxima. Zarr operations including full
copy, verification and publication took approximately 1.2–4.0 s per successful
attempt; the failed ~3.1 s upgrade attempt is retained. Native reader timings for R,
SAV and the reviewed BAAI checkpoint appear in pilot outcomes. These small-fixture
read costs are not a storage throughput benchmark. Peak scratch **allocation** and
cold-cache full-read cost for representative large observational datasets remain
release evidence to collect; cumulative scratch writes are enforced in runtime.

## Reader and profile decisions

R: go for bounded XDR v2/v3 envelopes after eight complete real-source native checks
and 16 combinations of version/workspace/source-envelope trusted fixtures. Both
serialized bytes and envelope integrity are verified passively. Native runtime R
object loading is absent. Reader proof is R 4.6.1; encoded older reader requirements
are preserved, not claimed to have been retested on every historical R release.

Checkpoint: go for two explicit profiles. Python Torch 2.2.2 and 2.14.1 read the
trusted fixture and reviewed BAAI source/candidates with tensor bits/dtype/stride/
sharing preserved. Default storage remains STORED/aligned, metadata may DEFLATE,
and native mmap works. Explicit storage DEFLATE works with ordinary load; mapped
loading is deliberately excluded. No general guarantee for all intermediate/future
Torch releases, every model object, TorchScript or standalone LibTorch application
is claimed. The Python reader exercises its C++ ZIP reader; this is one framework
lineage rather than an independent LibTorch application test.

SAV: go for the tested IEEE raw-to-bytecode/existing-bytecode algorithm; positive
trusted raw/bytecode fixtures include both endian forms and exact signed-zero/NaN
literal retention. The two real sampled files were already efficiently compressed,
so no savings are claimed for that original subset. A subsequently acquired
Roche raw SAV shrank 27,895 → 20,431 bytes; jamovi bytecode SAV shrank 69,475 →
62,483 bytes and JASP bytecode SAV 9,129 → 8,777 bytes, with native values/labels
preserved. ReadStat/pyreadstat is one reader lineage.
ZSAV: experimental only; native generated fixtures pass, but multiple independent observational ZSAV origins and proprietary SPSS version coverage remain absent.

HDF5/NetCDF/TIFF: preserving native profiles replace the former generic writers.
Native dataset/reference/user-block, same NetCDF model/raw packing/unlimited-dimension,
classic/BigTIFF/high-depth/SubIFD tests pass. Unsupported source semantics are refused;
the NASA HDF5 file's undefined fill state is intentionally retained. The extra H5
sample had no useful candidates; NetCDF and LZW TIFF each had a smaller real example.
TIFF optimization is deliberately restricted to a fully accounted image-data suffix,
with unchanged tag/IFD addresses. COG and unknown private metadata are refused, and
separate GeoTIFF/COG profile qualification remains open.

MAT: code exists for existing Level-5 compressed envelopes and separately detected
v7.3 HDF5. SciPy and synthetic v7.3 preservation checks pass; the two original MAT
inputs were unchanged. Native MATLAB is unavailable, so both profiles remain behind
`experimental_formats` and no MATLAB release gate is marked complete.

Zarr: go for bounded local offline v2, fixed-size dtypes, no filters, allowlisted
Blosc/gzip/zlib. Complete external example stores and consolidated synthetic stores
read back normally. Default codec family/cname stays; zstd upgrades require explicit
selection. macOS/APFS exclusive atomic publication, collisions, source changes,
no-benefit cleanup and cancellation gates are tested. Linux/Windows native full-store
qualification still requires CI; per-filesystem exclusive-rename probes refuse
unsupported guarantees at runtime.

## Implementation and remaining gates

New code: `format_support.py`, `format_worker.py`, `r_serialization.py`, `mat.py`,
`hierarchical.py`, `tiff.py`, `checkpoint.py`, `spss.py`, `zarr_store.py`; ordinary
file routes use shared source snapshots, candidate acceptance and publication.
Directory stores have an owned staging tree and exclusive publication contract.
CLI/bulk/library options and diagnostic outcomes are integrated. The new test suite,
scientific native CI job and optional extras are checked in.
Worker termination, abnormal exit or invalid control output closes accounting for
the root operation, preventing later nested adapters from reusing an unmeasured budget.
Scientific refusal/no-benefit results return the source path without publishing an
original-file copy over the requested destination. Budget/unsupported/no-benefit
regressions reproduced the former destination overwrite and now preserve both files.

Earlier full suite: 1,373 passed, 145 skipped. Final integrated scientific/CLI/
transaction/validator run: 423 passed, 4 skips. It includes 84 scientific tests
with one case-collision test skipped on case-insensitive APFS, the staging-copy
budget refusal, interrupted/failed-worker accounting, preservation of prior
destinations on refusal, streaming R and framing/endian/v7.3/supervisor regressions.
All three native SAV/ZSAV dictionary tests pass; inspection and refusal report
the experimental ZSAV gate.
Full repository Ruff and focused research-script Ruff pass. Mypy 1.19.1 supports
the Python 3.9 target; all 101 checked source files pass. Python 3.9 module compilation,
all seven strict OpenSpec validations and the documentation production build pass.
Native scientific CI is configured but has not run remotely in this session.

Open gates: native MATLAB; real ZSAV corpus; standalone LibTorch reader applications;
complete observational Zarr stores from independent datasets; Commons creators and
broader scientific/geospatial TIFF profiles; representative cold-read/peak-scratch
measurements and remaining backend/platform combinations. Synthetic fixtures and
repository examples do not silently close these gates. The seven change-level
`validation.md` files distinguish implemented tasks from these remaining gates.
