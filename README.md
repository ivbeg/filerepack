# filerepack

Lossless-first recompression for Office documents, archives, images, PDFs, media,
databases, scientific data and compressed streams. Eligible nested files are
optimized before their container is rebuilt and verified. Unsupported variants
and rejected candidates leave the source unchanged.

Python 3.9+ · macOS, Linux, Windows.

Current release: **[0.4.0](CHANGELOG.md#040---2026-10-09)**. Support is limited to
the qualified profiles below; experimental formats and inspection-only model
formats are marked explicitly.

## Documentation

The full documentation site (Docusaurus) lives in [`docs/`](docs/) and is published at **[ivbeg.github.io/filerepack](https://ivbeg.github.io/filerepack/)**.

| Section | What it covers |
|---------|----------------|
| [Getting started](https://ivbeg.github.io/filerepack/getting-started/installation) | Install, quick start, positioning |
| [Cookbook](https://ivbeg.github.io/filerepack/getting-started/cookbook) | Task index by role |
| [CLI reference](https://ivbeg.github.io/filerepack/commands/) | Commands and shared options |
| [Formats](https://ivbeg.github.io/filerepack/formats/) | Extension matrix and nested walking |
| [External tools](https://ivbeg.github.io/filerepack/tools/) | Binaries and OS install commands |
| [Python library](https://ivbeg.github.io/filerepack/library/) | `FileRepacker` API |
| [Troubleshooting](https://ivbeg.github.io/filerepack/getting-started/troubleshooting) | Exit codes and common errors |

Source pages: [`docs/docs/`](docs/docs/). Changelog: [`CHANGELOG.md`](CHANGELOG.md). Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).

Current source guides: [inspection](docs/docs/commands/inspect.md),
[reports and resume](docs/docs/commands/reports-and-resume.md),
[scientific formats](docs/docs/formats/scientific.md),
[model weights](docs/docs/formats/model-weights.md) and
[capabilities](docs/docs/formats/capabilities.md).

## Install

```bash
pip install filerepack
```

For development from source:

```bash
git clone https://github.com/ivbeg/filerepack.git
cd filerepack
pip install -e '.[progress,validation]'
```

Choose optional extras for the formats you need. From the checkout, install them
with `pip install -e '.[pdf,data]'`; released extras use
`pip install 'filerepack[pdf,data]'`.

| Extra | Enables |
| --- | --- |
| `progress` | Rich progress bars |
| `validation` | Pillow raster verification and pikepdf inspection fallback |
| `pdf` | pikepdf image-stream walking and Pillow decoding; lossless verification also needs qpdf 11+ |
| `parquet` / `data` | PyArrow 19+ Parquet verification; `data` also supplies ORC, Avro, Feather and Arrow readers |
| `fonts` | WOFF/WOFF2 via fonttools |
| `media` | Cover-art walking in MP3, FLAC, M4A, Ogg and APE via mutagen |
| `dicom` | DICOM structure, attribute and decoded-pixel verification |
| `ole` / `ole-recompress` | Legacy Office verification and optional payload encoders; also need the native writer below |
| `serialization` | Passive R, PyTorch checkpoint and SPSS parsers with worker isolation |
| `scientific` | HDF5, NetCDF4 and native TIFF readers/verification |
| `zarr` | Complete offline local Zarr v2 stores |
| `fits` | Lossless FITS tiled-image compression via Astropy |
| `blend` | Zstandard Blender stream compression |
| `duckdb` | Verified offline DuckDB compaction |
| `tgs` | Optional Zopfli Telegram sticker compression |
| `tracev3` | Archived Apple Unified Log LZ4 chunkset recompression |
| `onnx` | Bounded ONNX inspection |

External tools are required by the selected format. Check availability and
installation hints for your OS:

```bash
filerepack doctor
```

Install commands use Homebrew or MacPorts on macOS, apt/dnf/pacman/zypper/apk on Linux, and Chocolatey/winget/Scoop on Windows. `mp3packer` and `optivorbis` are not packaged; doctor points at GitHub CLI zips. Full notes: [tools](https://ivbeg.github.io/filerepack/tools/). Override paths with `FILEREPACK_7ZZ` (and similar) or `~/.config/filerepack/config.toml`.

## Quick start

```bash
filerepack inspect document.docx --json
filerepack repack document.docx
filerepack repack document.docx --dryrun
filerepack repack document.docx --output-dir ./optimized --profile preserve
filerepack bulk ./documents --jobs auto --progress
filerepack bulk ./photos --include-ext jpg,png,webp
```

`filerepack repack` shows a progress bar on a TTY (`--no-progress` to hide it). `bulk` needs `--progress`. Install `filerepack[progress]` for a `rich` bar; otherwise progress prints every N files.

`inspect` reports eligibility, prerequisites, protection state and destination
conflicts without encoding or extraction. It does not estimate candidate savings.
`--dryrun` measures candidates for most formats; the preserving scientific
handlers inspect without encoding and report the unchanged size.

JPEG, PNG, and PDF default to **lossless** tools. Opt into lossy codecs with
`--lossy`, `--jpeg-quality`, `--png-quality`, or `--pdf-profile`. Lossy PDF uses
Ghostscript `/ebook` (150 dpi); `--pdf-profile prepress` selects print quality.
`--jpeg-quality` also affects images inside PDFs. Lossless JPEG/PNG retain
orientation and color profiles; `--keep-meta` additionally retains incidental
metadata. Output that is not smaller is discarded unless `--allow-grow`;
individual preserving profiles may still require a strict size reduction.

Video defaults to stream-copy remuxing. `--video-mode lossless` explicitly
re-encodes losslessly; `--video-mode lossy --lossy` permits lossy encoding.

`--output-dir` preserves the source and produces an unchanged copy if no
improvement is accepted. Existing different output/conversion targets require
explicit `--overwrite`. Use `--backup --backup-dir ./backups` for a required
backup; backup failure stops processing and existing backups are protected.
Preserving scientific handlers publish a distinct output only when a smaller
candidate is accepted.

```bash
filerepack repack scan.pdf --pdf-linearize
filerepack repack scan.pdf --lossy
filerepack repack scan.pdf --pdf-profile printer --jpeg-quality 75
```

## Profiles, selection and reports

`--profile fast|balanced|maximum|preserve` selects version 1 effort defaults.
Explicit flags override profile settings. `maximum` enables `--ultra`;
`preserve` retains incidental metadata. Profiles do not enable lossy encoding
or opt-in OLE content transforms. Ultra adds stronger passes such as Parquet
zstd 22, `zopflipng`, `mp3packer -z` and bounded OLE Zopfli trials.

Use repeatable `--exclude-member` patterns, `--allow-category` /
`--skip-category` and `--max-depth` to select nested work. Per-file deadlines,
memory, decoded-byte and scratch limits are documented in
[shared options](docs/docs/commands/shared-options.md). Bulk respects aggregate
resource grants, so `--jobs` is an upper bound on active workers.

```bash
filerepack repack archive.zip --exclude-member 'originals/**' --max-depth 2
filerepack repack capture.warc.gz --report run.jsonl --report-paths relative
filerepack bulk ./documents --jobs 2 --manifest run.manifest
filerepack bulk ./documents --jobs 2 --manifest run.manifest --resume
```

Local JSON/JSONL reports record terminal outcomes, tool/validator evidence and
whether nested edits were published. Reports include absolute paths by default;
`--report-paths relative|redacted` changes path disclosure. Existing report files
are refused. Resume verifies source/output content and the effective settings
and toolchain before reusing completed work. See
[reports and resume](docs/docs/commands/reports-and-resume.md).

## Formats

| Kind | Extensions |
|------|------------|
| Office / OOXML | docx, xlsx, pptx, odt, ods, odp, ott, oth, otm, sxw, stw, pages, key, kth, vsdx, vssx, … |
| Legacy Office / OLE | doc, dot, xls, xlt, xla, ppt, pot, pps, msg, vsd, pub, mpp, msi, hwp (qualified CFB v3 profiles) |
| Archives | zip, 7z, rar, tar, tar.gz/tgz, tar.xz, tar.lzo, cpio, cpbz2/cpio.bz2, cab, wim, jar, epub, apk, aab, war, nupkg, oxt, … |
| Web archives | warc, warc.gz/warc.gzip |
| Compressed | gz/gzip, xz, bz2, zst, br, lz4, lz, lzma, lzo, Z |
| Documents | pdf, ai (PDF-based), xml, json, geojson, ipynb, jsonl/ndjson, qgs, ui, xhtml, kml, gpx, fb2, … |
| Interface Builder | nib (compiled NIBArchive version 1, coder 9/10) |
| Apple assets | car (qualified compiled asset catalogs) |
| Images | jpg, png, gif, webp, svg/svgz, tif, avif, heic, jxl, jp2, exr, dng, ico, cur, icns, bmp, tga, pnm, pcx, psd/psb, ase/aseprite, dcm |
| Video | mp4, mkv, webm, mov, m4v, wmv, avi, asf, 3gp, ts |
| Audio | flac, m4a/m4b (ALAC), ogg/opus, wv, ape, tta, oga, mp3 |
| Data / projects | parquet, orc, avro, feather/arrow, sqlite, gpkg, mbtiles, qgd/qgz, hdf5, netcdf, fits/fit/fts, nrrd, blend |
| Serialization / scientific | rds/rda/rdata, pt/pth, sav; experimental mat/zsav; local Zarr v2 directories via `repack-store` |
| Application formats | mellel, vscdb/sqlitedb, duckdb, swf, tgs, map/har/topojson/gltf, rels |
| Apple logs | archived tracev3 chunk streams |
| Fonts | woff, woff2 |

WMV/AVI/ASF/3GP/MPEG-TS convert to MP4 unless `--no-convert-container`. MKV/WebM/MOV/M4V keep their container. `.tar.gz` and friends are unpacked so nested files can be optimized, then the tarball is rewritten. Raw CPIO and bzip2-wrapped `.cpbz2` / `.cpio.bz2` archives can optimize safe regular single-link members while preserving links and metadata; unsupported or unsafe archives retain their members unchanged. Signed installers (`deb`, `rpm`, `pkg`, `dmg`) and ISO/AR are not rewritten. DICOM (`.dcm` / `.dicom` / `.dic`) is lossless JPEG-LS only; `--lossy` does not apply. Needs `filerepack[dicom]` and `gdcmconv` or `dcmcjpls`; structural, attribute and decoded-pixel verification is required before publication. Nested XML/JSON inside ZIP/OOXML/ODF/EPUB is minified (text nodes kept). Cover art inside MP3/FLAC/M4A/Ogg/APE is optimized when `filerepack[media]` is installed. Lossless PDF can walk image streams when `filerepack[pdf]` is installed. Full extension list and per-format tools: [formats](https://ivbeg.github.io/filerepack/formats/).

Parquet recompression uses PyArrow 19+ and verifies physical/logical schema, metadata and ordered values in batches. Unsupported schemas or missing verification dependencies leave the input unchanged. ODF/EPUB packages retain an uncompressed first `mimetype` entry and unchanged control manifests; signed, encrypted or unsupported packages are skipped. Qualified Arrow/Feather/ORC/Avro, SQLite and scientific profiles also have preserving adapters; broader variants, package aliases and reader/corpus gates remain documented.

SQLite in-place processing requires `--sqlite-offline` and no sidecars. A
distinct output uses a consistent snapshot including committed WAL pages.
Mellel packages retain their internal payloads unchanged. DuckDB, SWF and TGS
use qualified logical or decoded-content checks.

WARC 1.0/1.1 web archives use a dependency-free record-aware gzip writer:
`.warc.gz` retains one gzip member per record and exact decoded capture bytes;
standalone `.warc` converts to `.warc.gz`. Adjacent CDX/CDXJ indexes prevent
in-place rewriting; use a distinct output and rebuild indexes for that output.
See [WARC usage](https://ivbeg.github.io/filerepack/use-cases/data-files/#web-archives-warc).

The added project/scientific formats keep their filename extensions. FITS uses
standard tiled compression with no floating-point quantization; a compressed
primary image becomes an image extension after an empty primary HDU and needs a
reader with tiled-compression support. Blender verifies the entire decoded
stream without running the application or scripts. PSB, Aseprite, attached NRRD
and QGIS have format-specific preservation checks. Native handlers have a
256 MiB file/decoded-payload limit (Blender limits its decoded stream), and JSON
Lines limits each record to 16 MiB. See [supported variants and limits](docs/docs/formats/index.md).

Compiled `.nib` files share identical stored value sequences while preserving
every object identity, reference, ordered property, scalar bit pattern and class
fallback. This uses Python alone and works with `repack`, `bulk` and archive deep
walking. Keyed-plist nibs, directory bundles, unknown versions and undocumented
trailing data are skipped. Nib parsing and verification use the cumulative
`--format-max-*` budgets; the default memory budget allows inputs up to 32 MiB,
subject to record/buffer limits. See [nib support](docs/docs/formats/index.md#interface-builder-nib).

Apple `.car` asset catalogs retain every live BOM block, asset variant, rendition
key and opaque resource. The qualified BOMStore v1 profile recompresses
DEFLATE-backed MLEC/CELM images losslessly and compacts free allocations and
unused trailing block-index slots. LZFSE/LZVN, Deepmap, palette, ASTC and other
unknown payload codecs pass through byte-for-byte; incompatible or malformed
catalogs stay unchanged. See [CAR support](docs/docs/formats/index.md#compiled-apple-asset-catalog-car).

Archived `.tracev3` files use an isolated LZ4 worker with exact decoded-block
preservation. Outputs and backups into the active macOS Unified Log store are
refused. Full `.logarchive` directory packages are outside this profile. See
[tracev3 support](docs/docs/formats/tracev3.md).

### Scientific data and model weights

RDS/RDA/RData, modern PT/PTH checkpoints and IEEE SAV have passive preserving
handlers (`serialization` extra). Runtime processing does not load R objects or
unpickle checkpoints. HDF5, NetCDF4 and native TIFF use the `scientific` extra;
HDF5 also needs `h5repack`. MAT and existing ZSAV require
`--experimental-formats` while their release evidence gates remain open.

Checkpoints preserve aligned STORED tensor storage by default.
`--checkpoint-compatibility load-only` explicitly permits storage DEFLATE and
disables mmap compatibility. Complete offline local Zarr v2 stores publish a
verified separate store and refuse existing outputs:

```bash
filerepack repack analysis.RDS --r-compression xz
filerepack repack model.pt --checkpoint-compatibility load-only --json
filerepack repack-store data.zarr --output-dir ./optimized --json
```

Scientific JSON results include compatibility details and unchanged reasons.
See [profile contracts and resource limits](docs/docs/formats/scientific.md) and
[checksummed implementation evidence](dev/format_survey/implementation-2026-10-04/README.md).

Safetensors, GGUF and ONNX currently have bounded inspection only; their files
remain unchanged. `filerepack inspect-dcp ./checkpoint --json` inventories a flat
PyTorch Distributed Checkpoint directory without parsing pickle metadata or
proving completeness. Same-format recompression for these formats remains
unqualified. See [model weight formats](docs/docs/formats/model-weights.md).

### Legacy Office / OLE

Legacy Office compaction requires `filerepack[ole]` and the optional
[`filerepack-ole` writer](tools/ole-compactor/README.md), built with Rust 1.89+.
It reclaims unused CFB allocations while preserving every live stream byte and
logical directory field, including empty objects. DOC/XLS/PPT application records
and pictures are retained. Qualified unsigned DOC/XLS and single-edit PPT VBA
projects are copied unchanged after checking host signatures and project references.
Signed/encrypted/rights-managed files, unknown VBA layouts, malformed and
unqualified files are skipped.
The supported subset is CFB v3, 128 MiB maximum, with bounded directories and
independent `olefile` verification.
The same handler runs on eligible archive members. Savings depend on unused
container space; a compact document may stay unchanged.
Use `--verbose` for the measured candidate/rejection reason and actual strategy,
including missing dependencies.

`--ole-recompress` losslessly re-encodes qualified OfficeArt EMF/WMF, PNG IDAT
and sequential JPEG images in DOC/XLS/PPT, PPT storage wrappers, and compressed
HWP 5 streams. Populated BIFF8 cells/formulas/SST and audited Word piece/style
properties, mixed PICFs and floating delayed pictures have explicit profiles.
Single-edit PPT/POT/PPS also accept audited notes pages and a notes master,
including existing shared pictures and immutable master-owned Photoshop objects.
The notes-bearing profile selects PNGs within the existing 64 MiB allowance and
retains JPEG and unselected image bytes. Notes and object data remain exact.
Unknown layouts retain verified compaction with a reason.
Audited sound-free checker and fly-from-bottom animations retain every legacy
and PPT10 timing byte, with live shape and composite-layout reference checks.

`--ole-embedded-recompress` optimizes qualified DOC/XLS Package files and direct
CFB substorages; `--ole-deduplicate-images` merges byte-identical compatible BLIPs
in fully resolved XLS/PPT stores. Both default to off. `--ultra` retains default
trials and adds bounded Zopfli50 trials for eligible EMF/WMF/PNG, without enabling
content transforms. All modes retain metadata and select by final physical size.

Install `filerepack[ole-recompress]` and native writer 0.4.0+ for the new profiles.
JPEG optimization optionally needs libjpeg-turbo 3.2.0 `jpegtran`; other versions
leave JPEG unchanged. MSG, VSD 11, PUB 2002, MPP9 and MSI database profiles receive
strict container compaction. HWP 5 has separate protection and stream gates.
Verbose/JSON reports include per-object skips, encoders and additional file savings.
See the [Office guide](docs/docs/use-cases/office-documents.md) and
[qualification evidence](dev/ole/PORTFOLIO.md). Rebuild the native writer to
receive the current memory fixes and accelerated PNG verification.

## Safety and outcomes

Writers require a structural validator before publication; missing decoders or
failed checks leave the source untouched. Raster verification needs Pillow;
media verification needs ffmpeg/ffprobe. Signed, encrypted or uninspectable PDFs
skip qpdf, pikepdf and Ghostscript. Lossless PDF comparison needs qpdf 11+;
`--pdf-linearize` is explicit. A missing `7zz`/`7z` leaves the source archive
untouched; `doctor` exits 1 when that archiver is missing.

Rewrites use destination-local staging and atomic publication. Source mode,
mtime and supported Linux/macOS extended attributes are retained, and detected
source/output changes prevent replacement. In-place symlinks and multiple hard
links are refused. `RepackOptions.durability="atomic"` describes visibility;
crash durability, ownership, native ACLs and Windows alternate streams are
outside the current preservation contract.

Human results show `SUCCESS`, `ERROR`, `SKIPPED` or `CANCELLED`. No accepted size
reduction is a successful unchanged result; `--verbose` explains skips and
rejected candidates. JSON outcomes distinguish `replaced`, `unchanged`,
`skipped`, `unsupported`, `failed`, `predicted` and `cancelled`.

## Library

```python
from filerepack import FileRepacker, RepackOptions, options_for_profile

rp = FileRepacker()
summary = rp.repack("slides.pptx", options=RepackOptions(dryrun=True))
print(summary.total_insize, summary.total_outsize, summary.total_savings_pct)

options = options_for_profile("maximum", ultra=False)
print(options.profile, options.compression_level, options.ultra)
```

Explicit `RepackOptions` values override profile defaults, including `False`.
`repack_store` and `inspect_distributed_checkpoint` are also exported. See the
[library guide](docs/docs/library/index.md) for outcomes and compatibility.

## License

BSD-3-Clause. See [LICENSE](LICENSE), [CHANGELOG.md](CHANGELOG.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
