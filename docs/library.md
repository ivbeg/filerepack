# Library API

```python
from filerepack import FileRepacker, PackResult, RepackOptions, RepackSummary

rp = FileRepacker()
summary = rp.repack("slides.pptx", options=RepackOptions(dryrun=True))
print(summary.total_insize, summary.total_outsize, summary.total_savings_pct)
for item in summary.results:
    print(item.filepath, item.savings_pct)
```

`repack` is an alias of `repack_zip_file`. `RepackSummary` still supports the 0.1.x mapping:

```python
summary['final']   # [insize, outsize, savings_pct]
summary['files']   # list of [path, in, out, pct]
summary['stats']   # [inner_count, inner_insize, inner_outsize]
```

## Options

```python
options = RepackOptions(
    dryrun=False,
    deep_walking=True,
    pack_images=True,
    pack_archives=True,
    compression_level=9,
    jpeg_quality=None,      # set to enable lossy JPEG
    png_quality=None,       # 'high'|'medium'|'low' enables pngquant
    lossy=False,
    wmv_lossless=False,
    convert_container=True,
    keep_if_larger=True,
    min_savings=None,
    max_extract_bytes=None,  # None = 8GiB default; 0 disables
    max_extract_ratio=None,  # None = 100× archive size
    ultra=False,
    quiet=False,
    debug=False,
)
summary = rp.repack("data.parquet", options=options)
```

A plain `dict` is still accepted as `def_options=`.

## Format helpers

```python
from filerepack.repack import pack_gzip, pack_pdf, pack_jpg, pack_mp4

result = pack_pdf("document.pdf")
if result:
    print(result.insize, result.outsize, result.replaced)
```

`pack_images(path, recursive=True)` walks a directory of standalone images/videos.

## Tool paths

```python
from filerepack.tools import resolve_szip, doctor_rows

print(resolve_szip())
for row in doctor_rows():
    print(row['tool'], row['status'], row['path'])
```
