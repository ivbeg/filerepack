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

HDF5 and NetCDF need `h5repack` and `nccopy`:

```bash
filerepack repack model.h5
filerepack repack grid.nc
```

## Fonts

```bash
pip install 'filerepack[fonts]'
filerepack repack icon.woff2
```

WOFF/WOFF2 also work via `woff2_compress` / `woff2_decompress` when fonttools
is missing.

## Compressed streams

gzip, xz, bz2, zst, brotli, lz4, lzip, lzma, lzo, and Unix `.Z` are recompressed
with the matching CLI (`pigz` is preferred for gzip). If the payload is a tar,
the tarball is walked first — see [Archives](/use-cases/archives).

```bash
filerepack repack dump.json.gz
```

See [Formats](/formats/) and [Installation extras](/getting-started/installation#optional-extras).
