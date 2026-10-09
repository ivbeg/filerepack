---
title: "Data files"
description: "Recompress Parquet, SQLite, ORC, Avro, HDF5, NetCDF, and fonts"
---
# Data files

## Parquet

```bash
pip install 'filerepack[parquet]'    # or filerepack[data]
filerepack repack data.parquet
filerepack repack data.parquet --ultra   # zstd level 22
```

Recompression uses PyArrow 19+ with zstd level 19 (22 with `--ultra`).
Before publication, the candidate must retain physical and logical schema,
nullability, nested field names, field identifiers, file/schema/field metadata,
ordered values and floating-point bit patterns, including NaN and signed zero.
Existing `ARROW:schema` bytes are retained; a missing Arrow schema may be added.
Row-group boundaries, compression pages and statistics may be rebuilt.

Writing and verification use batches of at most 65,536 rows. This is a row limit,
not a byte memory budget: large source row groups, wide rows, nested values and backend buffers can require
more memory. External column chunks, sorting declarations and schemas whose
physical representation cannot be retained (for example legacy INT96 timestamps
or integer-backed decimals) are skipped with a reason. Missing PyArrow or failed
verification also leaves the input unchanged. Install the updated `parquet` or
`data` extra even if DuckDB is already installed.

These checks currently apply to Parquet. Preservation/framing contracts for the
other data writers and an explicit SQLite offline/snapshot policy remain planned
work.

## SQLite and spatial containers

`VACUUM` on SQLite. `.db` still requires the `SQLite format 3` header.

```bash
filerepack repack notes.sqlite
filerepack repack map.gpkg
filerepack repack tiles.mbtiles
```

## Columnar and scientific

```bash
pip install 'filerepack[data]'
filerepack repack table.orc
filerepack repack events.avro
filerepack repack frame.feather
```

HDF5 needs `h5repack`; NetCDF4 uses its native Python writer. Both need the `scientific` extra:

```bash
filerepack repack model.h5
filerepack repack grid.nc
```

## Scientific and project files

```bash
pip install 'filerepack[fits,blend]'
filerepack repack observation.fits
filerepack repack volume.nrrd
filerepack repack scene.blend
filerepack repack project.qgz
filerepack repack auxiliary.qgd
filerepack repack events.ndjson
filerepack repack analysis.ipynb
```

These keep their extensions and verify their supported decoded content. FITS
uses lossless tiled compression and can move a primary image to HDU 1 behind an
empty primary HDU; use a reader with tiled-compression support. NRRD supports
attached raw/gzip/bzip2 arrays. Blender verifies the full decoded stream without
launching Blender. QGZ retains unrelated assets and validates the QGS project and
QGD auxiliary database. JSON Lines keeps record boundaries and number/string
spellings; notebook cells and outputs are retained.

Native input/decoded-payload limits and unsupported variants are described in
[Native format policies and limits](/formats/#native-format-policies-and-limits).

## Fonts

```bash
pip install 'filerepack[fonts]'
filerepack repack icon.woff2
```

WOFF/WOFF2 also work via `woff2_compress` / `woff2_decompress` when fonttools
is missing.

## Compressed streams

### Web archives (WARC)

```bash
filerepack repack archive.warc.gz
filerepack repack archive.warc
filerepack repack archive.warc.gz --dryrun
filerepack bulk ./captures --include-ext warc
filerepack repack archive.warc.gz --output-dir ./recompressed
```

The dependency-free writer supports WARC 1.0/1.1 with CRLF framing, valid header
field names and unique, nonempty `WARC-Type`, `WARC-Record-ID`, `WARC-Date` and
`Content-Length` fields. Each record becomes a separate level-9 gzip member,
keeping random access. Whole-file gzip and records spread across gzip members
are accepted as inputs and rewritten into this layout when savings policy permits.
Use `--allow-grow` if a record-based layout is required even when it is larger.
The full decoded bytes are verified: WARC and HTTP headers, encoded payloads,
digests, unknown fields, folded headers, revisit references and record order stay
exact. Gzip wrapper metadata can change. ARC conversion, payload optimization,
header repair, missing-digest generation and Zstandard are outside this profile.

Standalone plain `.warc` converts to `.warc.gz`; the original is removed only
after successful publication. Use `--output-dir` to retain it, or
`--no-convert-container` to disable conversion. Plain WARC members inside another
container are skipped so member names and types remain intact; nested
`.warc.gz` members can be recompressed. Ordinary size and minimum-savings policies
apply, so an existing optimized archive may remain unchanged.

Compressed offsets and lengths change after recompression. In-place requests
with adjacent `.cdx`, `.cdxj`, `.cdx.gz` or `.cdxj.gz` files are skipped. A distinct
unindexed output is allowed while retaining the source and its indexes.
Indexes in other directories or external catalogues cannot be detected and must
be regenerated for the result. Filerepack does not rewrite index files.
Distinct WARC outputs are created only for accepted candidates; `--allow-grow`
also permits writing a verified output when the input is already optimized.

Reads use bounded chunks and headers are limited to 1 MiB total and 64 KiB per
line. The existing `--format-max-decoded-bytes`, `--format-max-memory-bytes`,
`--format-max-scratch-bytes`, `--format-max-nodes` and `--format-timeout` limits
apply cumulatively to parsing, encoding and verification. A successful rewrite
reads the decoded bytes four times, so the default 512 MiB decoded-byte budget
allows roughly 128 MiB of capture bytes. Raise the budget for larger archives:

```bash
filerepack repack large.warc.gz --format-max-decoded-bytes 8589934592 --format-timeout 600
```

Truncated records, invalid lengths, malformed framing, damaged gzip trailers or
exhausted budgets leave the source unchanged.

### Other compressed streams

gzip (`.gz` or `.gzip`), xz, bz2, zst, brotli, lz4, lzip, lzma, lzo, and Unix
`.Z` are recompressed with the matching CLI (`pigz` is preferred for gzip). If
the payload is a tar, the tarball is walked first — see [Archives](/use-cases/archives).

```bash
filerepack repack dump.json.gz
filerepack repack dump.json.gzip
```

See [Formats](/formats/) and [Installation extras](/getting-started/installation#optional-extras).

See [preserving scientific formats](../formats/scientific.md) for RDS/RData,
HDF5/NetCDF, TIFF, checkpoints and SAV. Complete offline Zarr v2 stores use
`repack-store STORE --output-dir OUTPUT_PARENT`; MAT and ZSAV remain explicitly experimental.
