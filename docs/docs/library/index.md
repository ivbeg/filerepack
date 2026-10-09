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

## Output destinations

DICOM processing requires `filerepack[dicom]` and a supported external encoder.
For direct verification, use
`verify_output(candidate, "dcm", source_path=original)` from `filerepack.utils`;
`dicom` and `dic` use the same check. Keep an unchanged original for comparison.
Calls without `source_path` return false because they cannot establish attribute
and pixel preservation. `has_dicm_magic` remains available in `filerepack.dicom`
for identification alone.

```python
summary = rp.repack(
    "notes.json",
    outfile="out/notes.json",
    options=RepackOptions(backup=True, backup_dir="backups"),
)
print(summary.filepath)  # effective output path
```

A distinct `outfile` preserves source bytes for standalone and archive inputs.
If no improved candidate is accepted, it receives an unchanged copy verified
by byte identity. Use a source-compatible filename for this fallback. An
accepted video/RAR conversion changes the effective extension to `.mp4`/`.7z`,
and `summary.filepath` reports that destination. Source aliases, including
relative paths and filesystem links to the same file, are treated as an
in-place request at the source entry. Such a request refuses a file-symlink
source or multiple hard links. Linked sources remain readable for distinct
outputs.

Different existing destinations raise `FileExistsError`. Set
`RepackOptions(overwrite=True)` to explicitly replace a requested output or
conversion target. Required backups remain protected even with overwrite;
backup failure raises an error before encoding. A backup directory alone does
not enable backups. `dryrun=True` creates no output or backup artifacts and
sets result `replaced=False` while measuring staged candidates.

`RepackOptions` and dictionary requests share validation. Invalid ranges,
non-finite thresholds and unknown quality/profile values raise `ValueError`
before filesystem mutation. Active reservations coordinate filerepack
operations. The source snapshot and any existing output are rechecked after
staging, including content hashes and stat generations; changes raise a
conflict instead of replacing the file.

Permission mode, mtime and supported Linux/macOS xattrs are retained by the
library and direct format helpers. Native ACLs, ownership and Windows alternate
streams are outside the policy. `durability="atomic"` describes atomic
visibility; requests for crash durability raise `ValueError` before writes.
See [Safety](/getting-started/safety) for platform limits and the final-check race.

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
    pdf_linearize=False,   # require linearized output; separate from compression
    ole_recompress=False,  # opt-in qualified OLE payload encoding
    ole_embedded_recompress=False,  # audited DOC/XLS child files
    ole_deduplicate_images=False,  # identical shared XLS/PPT images
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
    overwrite=False,       # distinct existing outputs/conversion targets conflict
    backup=False,          # required before processing when enabled
    backup_dir=None,       # selector only; needs backup=True
    durability="atomic",  # atomic visibility; crash durability is unsupported
)
summary = rp.repack("data.parquet", options=options)
```

Parquet requires `filerepack[parquet]` or `[data]` with PyArrow 19+; accepted
candidates preserve schema, metadata and ordered values through batch verification.
ODF/EPUB control files are excluded from nested edits and their package structure
is validated before publication. Unsupported contracts retain the source; a
distinct output follows the unchanged-copy policy described above.

Pass `on_progress` to observe archive stages (`extract`, `files`, `file`,
`write`) or a standalone pack (`standalone`):

```python
def on_progress(event, *, current=0, total=0, name=""):
    print(event, current, total, name)

summary = rp.repack("slides.pptx", on_progress=on_progress)
```

A plain `dict` is still accepted as `def_options=`.

For legacy Office, `rp.repack("report.doc", options=RepackOptions(ole_recompress=True))`
enables qualified OfficeArt EMF/WMF/PNG/JPEG, PPT wrappers and HWP streams.
`ole_embedded_recompress=True` selects qualified DOC/XLS children;
`ole_deduplicate_images=True` selects identical shared XLS/PPT images. Install the `ole-recompress` extra and native
writer 0.4.0+. The isolated mode shares `format_max_*` budgets and `format_timeout`
with nested archives; its overall deadline is 120 seconds. Results include payload
counts, encoders, stream/file savings and fallback reasons. See
[eligibility and preservation](/use-cases/office-documents/#recompress-officeart-pictures).

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

Existing helper imports from `filerepack.repack` and `filerepack.codecs` remain
supported after the implementations moved into format-family modules. Keyword
defaults, savings thresholds, dry-run behavior and `PackResult` are preserved.
The helpers share candidate verification/publication and operation-owned scratch
cleanup, including PNG encoder sidecars and WOFF2 tool directories.

## Tool paths

```python
from filerepack.tools import resolve_szip, doctor_rows, install_instructions

print(resolve_szip())
for row in doctor_rows():
    print(row['tool'], row['status'], row['path'], row['install'])

print(install_instructions())
```
