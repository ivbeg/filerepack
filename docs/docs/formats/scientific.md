---
title: Preserving scientific formats
---

These profiles compare original data and metadata before accepting a smaller candidate.
Unsupported representations return an unchanged result with a reason. Without an
accepted candidate, no destination is created or replaced; the reported file is the
original source. `--lossy`,
`--ultra` and `--allow-grow` do not expand their compatibility profiles.

Install the needed optional readers:

```bash
pip install 'filerepack[serialization]'  # R, checkpoints and SAV byte parsers + isolation
pip install 'filerepack[scientific]'     # HDF5, NetCDF and native TIFF validation
pip install 'filerepack[zarr]'           # complete local Zarr v2 stores
```

HDF5 additionally needs `h5repack`. R and Torch are used for trusted test fixtures;
runtime optimization does not load user R objects or unpickle checkpoints. MATLAB
is required to close the MAT release gate. A missing verifier preserves the source.

| Format | Enabled preserving profile | Explicit exclusions or gate |
|---|---|---|
| RDS / RDA / RData | XDR serialization v2/v3; gzip, bzip2, XZ and uncompressed envelopes; exact serialized bytes | ASCII/native-endian streams, bytecode, persistent/namespace/external-pointer records and unknown ALTREP representations |
| HDF5 | Native DEFLATE; hard-link graph/cycles, soft/external link text, typed attributes, user blocks, references and exact data; existing chunks/filter order retained | External/virtual/null datasets, unknown/lossy filters, padded compound types, unsupported reference/fill states |
| NetCDF | NETCDF4 and NETCDF4_CLASSIC with identical model, dimensions, groups, attributes, raw values and existing chunk geometry | CDF-1/CDF-2/CDF-5 conversion, NC_STRING/user-defined types, quantization and no-fill states |
| TIFF | Classic/BigTIFF; native strips/tiles with raw, LZW or DEFLATE sources, 8/16/32/64-bit samples | Opaque/private tags, JPEG/subsampled/sparse images, unsupported bit depths, COG layout; unsupported metadata/data ordering is retained |
| PT / PTH | Modern `torch.save` ZIP v3; exact record bytes and order; 64-byte-aligned STORED tensor data by default | Legacy pickle-only files, TorchScript, safetensors, unknown records/versions/alignment, encrypted/signed ZIPs |
| SAV | IEEE little/big endian `$FL2`; raw/bytecode cases, exact dictionary and case-element bytes | Non-IEEE/EBCDIC data, unknown dictionary extensions, nonstandard bias/missing representation |
| MAT | Experimental Level-5 existing `miCOMPRESSED`; separately detected experimental v7.3 HDF5 | Requires `--experimental-formats`; native MATLAB gate pending, no v4/v6 conversion or object/subsystem rewriting |
| ZSAV | Experimental existing `$FL3` block-envelope recompression with unchanged inflated bytecode/block partition | Requires `--experimental-formats`; multiple independent real ZSAV origins gate pending; no SAV-to-ZSAV conversion |

The TIFF writer retains IFD and tag payload positions. It rewrites only a fully
accounted image-data suffix and its compression/offset/count fields; earlier pages
stay intact. This removes the previous ImageMagick stripping path. Predictors,
geometry, endian, sample representation and non-storage tags stay unchanged. GeoTIFF
metadata is retained when understood, but this is not a separately qualified GeoTIFF
or COG optimization profile.

R compression preserves its original envelope by default, including meaningful gzip
metadata. Explicit wrapper conversion is refused if that metadata has no equivalent.
The serialization header and its declared minimum reader version are never changed.
Native tests used R 4.6.1; historical versions are not an asserted test matrix.

```bash
filerepack repack analysis.RDS --r-compression xz
filerepack repack model.pt --checkpoint-compatibility load-only --json
filerepack repack arrays.mat --experimental-formats --json
```

Checkpoint `preserve-mmap` compresses eligible metadata but retains STORED aligned
storage. `load-only` can DEFLATE storage and reports `mmap: false`; mapped loading is
not supported for that output. Python Torch 2.2.2 and 2.14.1 passed the tested reader matrix recorded in the linked
implementation report. Never use native object loading as a runtime validation step.

`repack` and `bulk` accept the same compatibility and resource settings. JSON outcomes
include `reason` and `details`, including unsupported/experimental states. Scientific
`--dryrun` inspects without an encoder or candidate workspace and reports the unchanged
size; it does not predict savings.

## Complete local Zarr stores

`repack-store` accepts a complete **offline** local array/group store. It publishes
`OUTPUT_PARENT/SOURCE_BASENAME`, which must be absent and disjoint from the source.
It never replaces an existing directory or overwrites the source.

```bash
filerepack repack-store ./data.zarr --output-dir ./optimized --json
filerepack repack-store ./data.zarr --output-dir ./optimized --codec-policy compatible-upgrade
```

The initial profile is Zarr storage v2, fixed-size non-object dtypes, C/F order,
missing/edge chunks, `filters: null`, and allowlisted Blosc/gzip/zlib codecs. Default
`preserve` keeps the compressor family and Blosc `cname`, raising its level when the
whole array becomes smaller. `compatible-upgrade` explicitly permits Blosc zstd.
Uncompressed arrays remain uncompressed. Chunk keys, shape, dtype/endian, geometry,
fill values, attributes and auxiliary files are retained. Existing consolidated
metadata must be consistent and is updated with each accepted compressor change;
unrelated metadata text remains intact.

Symlinks, hard links, special files, unsafe/colliding keys, unknown codecs/filters,
object/pickle dtypes and v3 stores are refused. The full staged store must pass decoded
chunk comparison. Generation checks detect source changes before publication; they
are not a live-writer snapshot protocol.

Publication uses the platform's exclusive atomic directory rename and probes it on
the destination filesystem first. Native publication was tested on macOS/APFS. Linux
and Windows primitives are implemented but their full native gates still need CI
results. Unavailable guarantees cause refusal and cleanup.

```python
from filerepack import FileRepacker, RepackOptions, repack_store

options = RepackOptions(r_compression='xz', format_max_nodes=2_000_000)
summary = FileRepacker().repack_zip_file('analysis.rds', def_options=options)
outcome = repack_store('data.zarr', 'optimized', RepackOptions(zarr_codec_policy='preserve'))
print(outcome.to_dict())
```

## Resource limits and actual evidence

The new adapters share a root-operation budget across candidate creation, verification
and nested adapter calls: 512 MiB decoded bytes, 256 MiB worker RSS, 2 GiB cumulative
scratch writes, 100,000 graph/record nodes and 120 seconds by default. Adjust them with
`--format-max-decoded-bytes`, `--format-max-memory-bytes`, `--format-max-scratch-bytes`,
`--format-max-nodes` and `--format-timeout`. These options take bytes, not `MB` strings.
Native processes run in an owned process group with sampled RSS/time/scratch supervision.
Metrics are sampled rather than a kernel memory/disk quota. Cancellation terminates only
operation-owned children. If a worker stops without reporting its resource usage, the
remaining scientific adapters in that root operation are refused. Generic archive handling
retains its existing extraction limits.

R/MAT/SAV/checkpoint passive byte parsers deliberately limit input and decoded buffers to
one eighth of the memory budget (32 MiB at defaults). Larger objects are retained;
raising decoded bytes alone does not raise this buffer limit. Dataset/chunk adapters
read bounded native segments and still have a worker RSS ceiling. Repeated verification
passes consume the decoded and node budgets; large tables may require a higher node limit.

The implementation report in `dev/format_survey/implementation-2026-10-04/README.md`
records complete checksummed inputs, all attempts, native-reader checks, costs and
remaining gates. In the original pilot denominator, R XZ saved 7.86% (two of ten files
bounded out), checkpoint defaults saved 0.79%, explicit load-only saved 9.71%, and the
two sampled SAV and two MAT files had no benefit. These are sample results, not corpus-wide
estimates. The sampled large HDF5 file was refused due to undefined fill state; ordinary
native fixtures prove preservation without implying benefit for every scientific file.
