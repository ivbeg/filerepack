---
title: "Python library"
description: "Call FileRepacker from Python with RepackOptions and format helpers"
slug: /library
---

# Library API

```python
from filerepack import FileRepacker, PackResult, RepackOptions, RepackSummary

rp = FileRepacker()
summary = rp.repack("slides.pptx", options=RepackOptions(dryrun=True))
print(summary.total_insize, summary.total_outsize, summary.total_savings_pct)
for item in summary.results:
    print(item.filepath, item.savings_pct)
```

`repack` is an alias of `repack_zip_file`. `RepackSummary` still supports the
0.1.x mapping:

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
    jpeg_quality=None,      # set to enable lossy JPEG (also PDF images)
    png_quality=None,       # 'high'|'medium'|'low' enables pngquant
    pdf_profile=None,       # 'screen'|'ebook'|'printer'|'prepress'|'default'
    lossy=False,            # PDF uses Ghostscript /ebook unless pdf_profile is set
    wmv_lossless=False,
    convert_container=True,
    keep_if_larger=True,    # True discards output that is not smaller
    keep_meta=False,        # True keeps JPEG/PNG EXIF/ICC
    min_savings=None,
    max_extract_bytes=None,  # None = 8GiB default; 0 disables
    max_extract_ratio=None,  # None = 100× archive size
    ultra=False,            # Parquet zstd 22, zopflipng, mp3packer -z
    quiet=False,
    debug=False,
)
summary = rp.repack("data.parquet", options=options)
```

Pass `on_progress` to observe archive stages (`extract`, `files`, `file`,
`write`) or a standalone pack (`standalone`):

```python
def on_progress(event, *, current=0, total=0, name=""):
    print(event, current, total, name)

summary = rp.repack("slides.pptx", on_progress=on_progress)
```

A plain `dict` is still accepted as `def_options=`.

`keep_if_larger=True` is the CLI default (reject output that did not shrink).
`--allow-grow` sets it to `False`. `ultra=True` is Parquet zstd level 22, an
extra `zopflipng` PNG candidate, and `mp3packer -z`. Cover-art walking needs
`pip install 'filerepack[media]'`; lossless PDF image streams need
`pip install 'filerepack[pdf]'`.

## Format helpers

```python
from filerepack.formats import identify_filename
from filerepack.repack import pack_gzip, pack_pdf, pack_jpg, pack_mp4
from filerepack.codecs import pack_sqlite, pack_jxl, pack_dcm, pack_xml, pack_json, pack_ogg

kind = identify_filename("slides.pptx")
print(kind.family, kind.key)          # zip, pptx

result = pack_sqlite("notes.sqlite")
if result:
    print(result.insize, result.outsize, result.replaced)
```

`pack_images(path, recursive=True)` walks a directory of standalone
images/videos. Format coverage: [Formats](/formats/).

## Tool paths

```python
from filerepack.tools import resolve_szip, doctor_rows, install_instructions

print(resolve_szip())
for row in doctor_rows():
    print(row['tool'], row['status'], row['path'], row['install'])

print(install_instructions())
```
