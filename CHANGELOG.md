# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-09

Support is limited to the qualified profiles documented below. Experimental
formats and pending platform/reader gates remain explicitly marked.

### Added

- Read-only `filerepack inspect PATH --json` for eligibility, format capabilities,
  prerequisites, protection state, effective settings and destination conflicts.
  Directory inspection emits JSONL items and a completion summary without
  encoding, extraction or candidate-savings estimates.
- Version 1 optimization profiles: `fast`, `balanced`, `maximum` and `preserve`.
  Explicit CLI/library settings override profile defaults, including false and
  default-valued options. Profiles do not enable lossy encoding or OLE content
  transforms; `options_for_profile` is exported for library callers.
- Explicit nested selection through repeatable `--exclude-member`,
  `--allow-category`, `--skip-category` and `--max-depth`, with supported archive,
  XML/PDF image and cover-art adapters applying the selection policy.
- Local version 1 JSON/JSONL audit reports via `--report`, independent of stdout
  JSON/CSV. Records include terminal outcomes, publication-aware member events
  and bounded tool/library/validator evidence. Relative and redacted path modes
  are available; persistence failures cause a non-success exit and preserve
  recoverable outcomes/spools.
- Content-verified bulk checkpoints via `--manifest` / `--resume`. Reuse requires
  matching source/output SHA-256 identities, effective settings and execution
  fingerprints, including toolchain and optional-reader versions. Only completed
  replaced/unchanged work is reusable; checkpoints use locks, checksums and
  atomic replacement.
- Root-operation deadlines and memory, decoded-byte, scratch, node and depth
  budgets, with supervision of operation-owned command process trees. Bulk
  scheduling reserves aggregate memory, scratch and CPU grants; `--jobs` limits
  rather than guarantees concurrent workers. Full cumulative accounting for
  every legacy adapter remains a qualification task.
- Dependency-free WARC 1.0/1.1 recompression with one verified gzip member per
  record and exact decoded capture bytes. Choose the smallest valid original or
  level-9 member per record; ultra adds bounded optional Zopfli trials. Plain
  standalone WARC converts to `.warc.gz`, nested WARC retains its name, and
  adjacent CDX/CDXJ indexes guard in-place rewriting.
- Raw CPIO and bzip2-wrapped `.cpbz2` / `.cpio.bz2` recompression. Shallow mode
  verifies exact decoded CPIO bytes; deep mode optimizes safe regular single-link
  members while retaining order, names, metadata and link relationships.
  Standard-library bzip2 is available without an external encoder.
- `.gzip` aliases, including `.tar.gzip`, `.warc.gzip` and gzip-wrapped
  R serialization filenames.
- Dependency-free `.nib` compaction for fully parsed NIBArchive version 1,
  coder 9/10. Identical stored value sequences can be shared while object
  identities, references, property order, exact scalar/data bytes and class
  fallbacks are preserved. Keyed-plist nibs, bundles and unknown/trailing
  structures are skipped under cumulative format limits.
- Qualified Apple `.car` asset catalog optimization: lossless DEFLATE MLEC/CELM
  rendition recompression and BOMStore free-space/index compaction. Live blocks,
  variants, keys, metadata and opaque codecs are retained and independently
  fingerprinted before publication.
- Optional isolated `.tracev3` LZ4 chunkset recompression via the `tracev3` extra.
  Preserve decoded block bytes/boundaries and opaque chunks; refuse outputs or
  backups in the active macOS Unified Log store. Complete `.logarchive` directory
  packages remain outside the profile.
- Extension-preserving PSB, GeoJSON, Jupyter notebooks, JSON Lines/NDJSON,
  QGIS QGS/QGZ/QGD, Qt Designer UI, Blender, FITS/FIT/FTS, attached NRRD and
  Aseprite ASE/ASEPRITE profiles. Format-specific checks guard decoded content
  and metadata; JSON Lines preserves record boundaries and exact tokens.
  Optional `fits` and `blend` extras supply Astropy and Zstandard. FITS never
  quantizes floating-point data; compressed primary images require a reader
  supporting the documented tiled-compression layout.
- Audited Mellel packages, offline SQLite `.vscdb`/`.sqlitedb`, DuckDB tables,
  FWS/CWS SWF and Telegram TGS animations. Mellel retains internal payloads;
  other profiles require logical/decoded preservation. JSON `.map`, `.har`,
  `.topojson`, `.gltf` and XML `.rels` aliases use conservative markup handlers.
  Optional `duckdb` and `tgs` extras supply their readers/encoders.
- Passive preserving RDS/RDA/RData, modern PT/PTH ZIP checkpoint and IEEE SPSS
  SAV profiles, with isolated workers supplied by `serialization`. Runtime
  processing does not load R objects or unpickle checkpoints. R preserves its
  compression envelope by default; `--r-compression` permits qualified changes.
  Checkpoints retain 64-byte-aligned STORED tensor data by default;
  `--checkpoint-compatibility load-only` explicitly permits DEFLATE storage and
  disables mmap compatibility.
- Qualified HDF5, NetCDF4 and native TIFF preservation through the `scientific`
  extra. HDF5 additionally needs `h5repack`; unsupported graphs, filters, types,
  fill states and image layouts remain unchanged. TIFF retains IFD/tag positions
  and only rewrites a fully accounted image-data suffix. MAT Level-5/v7.3 and
  existing ZSAV remain gated by `--experimental-formats` and pending reader/corpus
  evidence. Scientific dry-run inspects without encoding or predicting savings.
- `filerepack repack-store` and exported `repack_store` for complete offline
  local Zarr v2 stores (`zarr` extra). Verify all decoded chunks and publish
  `OUTPUT_PARENT/SOURCE_BASENAME` through exclusive atomic directory rename.
  Existing destinations, links, object dtypes, unknown codecs/filters and v3
  stores are refused. `--codec-policy compatible-upgrade` explicitly permits
  Blosc zstd; native Linux/Windows publication gates remain pending.
- Bounded inspection-only Safetensors, GGUF and ONNX profiles, with optional
  `onnx` parsing. `filerepack inspect-dcp` and exported
  `inspect_distributed_checkpoint` inventory flat local DCP directories without
  parsing pickle metadata or claiming completeness. Same-format writers remain
  unqualified and sources remain unchanged.
- Optional CFB v3 container compaction for qualified DOC/DOT, BIFF8 XLS/XLT/XLA,
  PPT/POT/PPS and MSG/VSD/PUB/MPP/MSI/HWP hosts, including eligible nested files.
  The pinned Rust `filerepack-ole` writer and independent `olefile` verifier
  retain live streams, empty objects and logical directory metadata. Qualified
  unsigned DOC/XLS and single-edit PPT VBA projects are copied unchanged;
  protected files and unknown/history-dependent layouts are skipped.
- Opt-in `--ole-recompress` for qualified OfficeArt EMF/WMF, PNG IDAT and
  sequential JPEG pictures, PPT embedded-storage wrappers and compressed HWP 5
  streams. Independent verifiers check decoded payloads, host references,
  metadata and immutable content. Populated BIFF8, audited Word piece/style
  properties, mixed PICFs and floating delayed pictures have explicit profiles.
- Opt-in `--ole-embedded-recompress` for qualified DOC/XLS Package files and CFB
  substorages, and `--ole-deduplicate-images` for byte-identical compatible BLIPs
  in fully resolved XLS/PPT stores. Both default to off. Ultra retains default
  trials and adds bounded Zopfli50 alternatives without enabling a content mode.
  All OLE modes select by final physical file size; native writer 0.4.0+ supplies
  bounded path replacements and root-view extraction.
- Audited notes-bearing single-edit PPT/POT/PPS picture profiles, including
  notes/master links, shared picture consumers and programmable extensions.
  PNG selection stays within existing limits; notes, unselected images and
  master-owned Photoshop objects retain their bytes and independent identities.
- Audited sound-free checker/visibility and fly-from-bottom PPT/PPT10 animation
  profiles, bounded x/y keyframes, null-bullet text runs, font defaults and
  composite master/layout references. Animation bytes and live shape references
  remain exact; repeated embedded wrappers are diagnosed without sharing persist
  offsets. Supplied `openbudget.ppt` and `opengovernment_rewired.ppt` save 10.41%
  and 10.00% respectively, with identical rendered slides/notes and independent
  reader/save/reopen checks. These are fixture results; see the
  [checker](dev/ole/qualification-ppt-openbudget-animation.json) and
  [fly animation](dev/ole/qualification-ppt-opengovernment-fly-animation.json) evidence.
- Bounded PNG row-filter selection for qualified inline/floating DOC pictures
  and PPT pictures. Optional oxipng 10.2.0 trials verify exact samples and restore
  original metadata; unavailable or rejected trials retain earlier verified
  encodings. Additional Word border, pagination, revision, conditional-style
  and scalar drawing properties are qualified. Supplied `gov.doc` saves 10.82%
  with identical page pixels and independent document preservation; see
  [DOC PNG evidence](dev/ole/qualification-word-png-refilter-2026-10-08.json).
- Licensed DOC/XLS preservation/render and rejection fixtures, plus a
  checksummed 711-file Apache POI eligibility census with exact skip reasons.
  Corpus boundaries and unavailable Office/Hancom/platform checks are recorded
  in [OLE evidence](dev/ole/PORTFOLIO.md) and [the census](dev/ole/CORPUS.md).
- Distribution validation builds, inspects and installs wheel/sdist artifacts in
  fresh environments outside checkout imports, including CLI/API, license and
  extracted-source tests. Platform, optional-reader, scientific-native and
  OLE-native CI lanes, shared-core coverage ratchets and a reconciled verified
  specification baseline are configured; remote results and deployment remain
  separate qualification gates.

### Changed

- Typed terminal outcomes and stable reason codes are shared by library,
  single-file, bulk and nested operations. Human results explicitly show
  `SUCCESS`, `ERROR`, `SKIPPED` or `CANCELLED`; no size reduction is a successful
  unchanged result. Optional payload skips are informational, and failure reasons
  remain visible in quiet mode. Bulk completion reflects interruption and
  report/checkpoint failures; machine-readable outcome schemas and exit codes
  retain their contracts.
- Publication shares typed filesystem snapshots and destination-local staging
  across direct helpers and `FileRepacker`. Preserve source mode, mtime and
  supported Linux/macOS xattrs, including resource forks; refuse detected
  source/output changes, in-place symlinks and multiple hard links.
  `RepackOptions.durability="atomic"` describes visibility; unsupported crash
  durability is rejected before writes. Ownership, native ACLs and Windows
  alternate streams remain outside the preservation contract.
- Existing different output/conversion targets require `--overwrite` or
  `RepackOptions(overwrite=True)`. Required backups are never overwritten and
  backup failure stops processing; `--backup-dir` still requires `--backup`.
  Distinct outputs preserve the source, with a byte-verified unchanged copy when
  supported by the handler; scientific profiles publish only accepted smaller
  candidates. Dry-run creates no destination or backup artifacts.
- Every publishable writer requires a structural validator; missing/unknown
  validators, truncated structures and unavailable decoders cannot authorize
  replacement. Raster checks need Pillow (`validation` extra); media checks
  need ffmpeg/ffprobe. Stream verification compares decoded bytes, image checks
  compare decoded frames, and supported data adapters check schemas, metadata
  and ordered values. Wider format variants remain gated.
- Default video processing uses stream-copy remuxing. Explicit lossless/lossy
  modes verify stream inventory and required packet or decoded-content
  preservation instead of silently dropping tracks.
- JPEG/PNG retain orientation and color presentation metadata; `--keep-meta`
  additionally retains incidental metadata. Lossless PNG retains encoded depth
  and color type and chooses among independently preserving candidates.
  Lossless ImageMagick/AVIF/HEIC/JXL paths require source-content preservation.
- Signed, encrypted and uninspectable PDFs skip all qpdf/pikepdf/Ghostscript
  writers. Lossless publication needs qpdf 11+ object/stream comparison and
  selects the smallest verified original/walked/qpdf alternative.
  `--pdf-linearize` is an explicit constraint, subject to savings policy.
  Walking covers shared/nested XObjects and supported Flate predictors with
  exact decoded-stream and document checks. DCT/JPX precision and host dimensions
  are checked; unqualified high-depth/signed/subsampled JPEG2000 is refused.
- Parquet requires PyArrow 19+ (`parquet`/`data` extras); DuckDB alone no longer
  supplies a preservation verifier. Supported Arrow/Feather/ORC profiles retain
  framing, schemas and batch metadata; Avro retains encoded block data.
- SQLite retains schema and row identities. In-place processing requires
  `--sqlite-offline` and no sidecars; distinct outputs use a consistent snapshot
  including committed WAL pages. A single-file backup of a live WAL source is
  unsupported.
- ODF/EPUB packages with unsupported structure, protection or control semantics
  are skipped before extraction and nested edits.
- WOFF/WOFF2 verification compares decoded tables, metadata and private data
  in isolated native workers.
- Legacy OLE results retain actual strategies and rejection/fallback reasons
  in CLI/library/JSON/bulk output. Verbose diagnostics include payload counts,
  per-object skips, encoders and stream/file savings. An unchanged result is
  no longer labelled recompressed.
- Candidate staging, verification, savings acceptance and publication use
  `filerepack.candidates` / `filerepack.transactions`; argv execution and audio
  probes use `filerepack.commands`. Dedicated archive, stream, image, media,
  document, data and medical modules retain legacy helper imports, signatures
  and encoding defaults through `repack.py` / `codecs.py`. Typed worker/progress
  contracts replace dynamic back-imports and the relaxed mypy return override.
- Package metadata and `__license__` identify BSD-3-Clause with setuptools
  77.0.3+ SPDX/License-File support; the license text is unchanged.
- Docusaurus documentation under [`docs/`](docs/) covers commands, formats,
  use cases, tools and library APIs for GitHub Pages. README installation,
  current CLI workflows, optional extras and format limits are synchronized;
  unreleased entries are consolidated without changing historical releases.
- `filerepack[dicom]` supplies pydicom, NumPy and pyjpegls. Python 3.9 uses the
  compatible pydicom 2.4 profile; newer versions can compare frames incrementally.
  DICOM output verification requires the original source for structural,
  attribute and decoded-pixel comparison.

### Fixed

- Bulk discovery and submission are bounded; source/output/backup reservations
  prevent competing operations, cancellation drains workers, and owned process
  trees are supervised. Result-spool failures stop new work while preserving
  drained terminal outcomes in a bounded emergency tail.
- PNG quantization failures/interruption clean owned sidecars without deleting
  pre-existing files. WOFF2 uses an owned directory; SQLite tracks candidate
  journals. Archive exceptions clean candidates and extraction directories
  while preserving the source.
- Source distributions include the complete test package, helpers, fixtures,
  initialization and coverage configuration. Runtime wheels exclude development
  support. Compatibility regressions retain 69 public calling contracts and
  79 dispatch routes, including fresh-process import orders and installed-wheel
  scratch-fault checks.
- Parquet rewrites retain physical/logical schema, nullability, nested fields,
  identifiers and file/schema metadata. Batched verification checks ordered
  values and floating-point bits; unrepresentable candidates are refused.
- ODF/EPUB retains an uncompressed first `mimetype` without extra fields,
  validates package references and preserves control-file bytes across deep,
  no-deep, dry-run and distinct-output workflows.
- Archive manifests reject missing/extra members, changed unapproved payloads,
  ambiguous identities and unsupported metadata. Writers retain hidden members
  and empty directories with literal tool-specific arguments. ZIP preserves
  order, timestamps, attributes, extra fields and comments; tar preserves
  supported ownership, permissions, timestamps and PAX metadata. Unsupported
  links/sparse representations skip safely.
- ZIP metadata restoration preserves explicitly zero external attributes,
  including Mellel directories, instead of write-time 0600 defaults.
- Compressed tar decodes its outer stream and rebuilds the actual tar members
  without introducing another tar layer; deep modes and dry-run verify the
  final encoded payload. RubyGems `.gem` uses plain tar and keeps checksummed
  inner payloads; `.taz` uses Unix compress instead of gzip.
- JSON minification preserves exact number/string tokens, duplicate keys,
  member order, scalar roots and UTF-8 BOMs. Malformed/non-finite literals and
  unsupported encodings skip. Reads stop at the 256 MiB validation bound,
  including oversized HAR and source-map aliases.
- Native XML minification preserves text/tail whitespace, inherited `xml:space`,
  CDATA, entity references, namespaces, comments, processing instructions and
  declarations. Only tag syntax and known OPC indentation are compacted;
  unsupported DTD/version/encoding profiles are refused. Embedded image-URI
  optimization targets complete `href`, `xlink:href` and `src` attribute values.
- CLI, workers and `FileRepacker` validate ranges, finite thresholds, profiles
  and paths before backups/copies/encoding. Size parsing accepts K/M/G/T with
  or without B; jobs and progress intervals must be positive.
- Cooperative path/file-identity reservations and collision-refusing publication
  guard output races. Video/RAR conversions retain their source until publication
  succeeds; reported paths reflect accepted conversion extensions.
- DICOM scans after Pixel Data and inside sequence items, checking ordering,
  headers, lengths, fragments and bounded parser counts. Signature elements,
  truncation and exhausted limits stop encoding. JPEG-LS candidates must retain
  lossless transfer syntax, image/frame/identity/private/nested attributes and
  exact decoded pixels; missing/failed verification keeps the source.
- OLE compaction and content modes preserve recorded root creation/modification
  FILETIMEs. Pinned CFB simple-uppercase comparison accepts qualified root-name
  encodings and Unicode names such as `ß` without renaming objects.
- Combined OLE recompression/embedded/deduplication modes release parsed sources
  and staged picture buffers before native assembly, stream replacements and
  reuse verified sources to avoid redundant full-file memory use. Final worker
  verification is bound to exact file snapshots. Rebuild the native helper for
  these memory fixes and accelerated bounded PNG row verification.
- Qualify the first BIFF8 drawing-group continuation encoded as a second
  MsoDrawingGroup and bounded scalar tertiary worksheet fill properties;
  worksheet drawings consume the cumulative root budget. DOC checks preserve
  history/unreferenced pictures and reject hidden references, malformed property
  tables and nonempty unsupported fill defaults.
- Transaction regressions cover cross-device staging, metadata/xattr failures,
  source/output races, stale verification, links, durability validation and
  scratch cleanup. Native macOS xattrs/resource forks are exercised; real
  cross-filesystem tests run when a second device is available.

## [0.3.0] - 2026-08-14

### Added

- ZIP-family aliases: `war`, `ear`, `aar`, `nupkg`, `snupkg`, `vsix`, `xpi`, `crx`, `appx`, `msix`, `appxbundle`, `sketch`, `kra`, `ora`, `xd`, `usdz`, `ifczip`, `cbr`/`cb7`/`cbt`, OOXML siblings (`vsdm`, `vstx`, `vstm`, `vssx`, `vssm`, `sldm`, `ots`, `otg`, `odb`), ODF templates (`oth`, `otm`, `otc`, `oti`; `otf` only when the file is a ZIP, not an OpenType font), OpenOffice.org 1.x (`stw`, `stc`, `sti`, `std`, `sxg`, `sxm`), iWork templates (`kth`, `nmbtemplate`, `template`), `oxt`, `aab`, `xapk`/`apks`, `npz`, `fcstd`, `mcworld`/`mcpack`/`mcaddon`, `unitypackage`, `onepkg`, `wgt`, `ibooks`, `air`, `pk3`, `xap`, `ipsw`, `osk`, `oex`, `puz`, `rmskin`, `notebook`, `nbk`
- XML/JSON minify (including nested parts in ZIP/OOXML/ODF/EPUB): `.xml`, `.json`, `.xhtml`, `.kml`, `.gpx`, `.dae`, `.rss`, `.atom`, `.xmp`, `.xsl`, `.xslt`, `.fb2`. SVG falls back to XML minify when svgo/scour are missing; `data:` image URIs are packed
- Cover art in MP3/FLAC/M4A/MP4/Ogg/APE via optional `filerepack[media]` (mutagen)
- Lossless PDF image-stream walking via optional `filerepack[pdf]` (pikepdf); `--lossy` still uses Ghostscript
- `jpegtran` lossless JPEG pass; `zopflipng` on `--ultra` PNG; `--keep-meta` to keep JPEG/PNG metadata
- Images: BMP, TGA, PNM, PCX, APNG, CUR; JPEG aliases `jif`/`jfi`/`thm`
- Ogg Vorbis/Opus via optional `optivorbis`; `.m4b` follows the M4A path; SQLite `.db` alias
- Tarball walk: `tar`, `tar.gz`/`tgz`, `tar.bz2`/`tbz2`, `tar.xz`/`txz`, `tar.zst`/`tzst`, `tar.br`, `tar.lz4`, `tar.lzo`/`tzo`, `tar.lz`/`tlz`, plus `gem`/`crate`. Inner files are optimized, then the archive is rewritten. Compressed streams whose payload is a tar (`.gz`, `.zst`, `.lz4`, …) are detected by peeking the first 512 decompressed bytes
- Stream codecs: `lz4`, `lz` (lzip), `lzma`, `lzo`, Unix `compress` (`.Z`)
- Containers: Microsoft Cabinet (`cab`) and WIM (`wim`)
- Images: JPEG aliases (`jpe`, `jfif`), JPEG XL, JPEG 2000, OpenEXR, DNG, ICO, ICNS, `svgz`
- DICOM (`.dcm` / `.dicom` / `.dic`): lossless JPEG-LS for uncompressed or RLE image instances via `gdcmconv` or `dcmcjpls`. Signed, non-image, and already-compressed files are skipped. `--lossy` does not apply
- Video: `mov`, `m4v` (kept), `3gp`/`ts`/`mts`/`m2ts` (convert to MP4 unless `--no-convert-container`)
- Lossless audio recompress: ALAC in `m4a`, WavPack, TTA, FLAC-in-Ogg; Monkey's Audio when `mac` is installed; MP3 via `mp3packer`
- Photoshop `psd`: recompress ZIP-encoded layer/composite channels (RLE/raw channels are left unchanged)
- Adobe Illustrator `ai` when the file is a PDF wrapper (same path as `pdf`)
- `--pdf-profile screen|ebook|printer|prepress|default` for Ghostscript Distiller presets (implies lossy PDF)
- Data: SQLite `VACUUM` (`sqlite`, `gpkg`, `mbtiles`), ORC/Avro/Feather/Arrow (optional extras), HDF5 (`h5repack`), NetCDF (`nccopy`)
- Fonts: WOFF/WOFF2 via fonttools or `woff2_compress`
- Optional extras: `filerepack[data]`, `filerepack[fonts]`, `filerepack[media]`, `filerepack[pdf]`
- `filerepack doctor` prints OS-specific install commands (Homebrew, apt, dnf, pacman, Chocolatey, winget, …) for missing tools. `mp3packer` and `optivorbis` are not packaged; doctor points at their GitHub releases with macOS/Linux/Windows binaries, and [tools](docs/docs/tools/index.md) has install steps
- `filerepack repack --progress` shows a progress bar (on by default on a TTY). Archives report extract / inner-file / rewrite stages

### Changed

- Docs: full format coverage, nested walking, and extras in [formats](docs/docs/formats/index.md); `--ultra` documents PNG/MP3 as well as Parquet
- File type detection uses compound suffixes (`archive.tar.gz`) instead of only the last extension
- `--include-ext tar.gz` matches compound names; `--include-ext gz` still matches them too
- `--lossy` PDF uses Ghostscript `/ebook` (150 dpi) instead of `/prepress`, which actually downsamples scanned pages. `--pdf-profile prepress` restores the previous print-quality path. `--jpeg-quality` now also sets Distiller QFactor for images inside PDFs
- `optivorbis` install hints point at GitHub CLI zips. Cargo cannot install the CLI (`optivorbis` on crates.io is a library; `cargo install` has no `--package`)

### Fixed

- `--dryrun` on archives now includes inner-file savings in the predicted size. Previously inner packs were measured but not applied in the temp extract dir, so the rewritten archive looked larger than a real run

## [0.2.0] - 2026-08-14

### Security

- Replaced all `os.system()` calls with `subprocess.run()` using argument lists
- External tools now use `subprocess.run(cwd=...)` instead of process-global `os.chdir()`

### Fixed

- **Data loss:** archive rewrite no longer unlinks the original before 7zz/rar succeeds. New archives are written to a temp file, verified, then `os.replace`d
- **Data loss:** WMV/AVI/ASF conversion no longer deletes the compressed output while renaming
- `--min-savings` no longer mutates a file and then reports it as skipped
- `filerepack bulk` now includes standalone JPEG and PNG files
- JPEG/PNG packers return failure when jpegoptim/pngquant/oxipng are missing
- Parquet compression uses the DuckDB Python API (`pip install duckdb`) instead of a `duckdb` CLI binary
- `bulk --csv` accepts dict result rows
- `--jobs auto` is parsed as a string (`auto` or an integer)
- `--json` and `--csv` are mutually exclusive
- `--log-file` now records CLI messages
- Glob expansion only expands a bare `*` (archive contents), not filenames containing `*`
- Failed archive extraction leaves the original file untouched

### Changed

- JPEG/PNG/PDF default to lossless tools. Use `--jpeg-quality`, `--png-quality`, or `--lossy` for lossy codecs
- Results that are not smaller than the original are discarded unless `--allow-grow` is set
- `FileRepacker.repack_zip_file` returns `RepackSummary` (still supports `summary['final']` dict access)
- gzip/xz/bz2 stream through temp files instead of loading the whole payload into memory
- 7-Zip is resolved as `7zz` or `7z` (env `FILEREPACK_7ZZ`, optional `~/.config/filerepack/config.toml`)

### Added

- `filerepack doctor` — report which external tools are on PATH
- `--jobs N|auto` parallel bulk processing via `ProcessPoolExecutor`
- `--exclude-dir` plus default skips for `.git`, `node_modules`, `__pycache__`, venvs
- `--lossy`, `--allow-grow`, `--convert-container/--no-convert-container`
- `--max-extract-size` (default 8GB / 100×) to skip zip-bomb-sized archive extracts
- Zstandard (`.zst`), Brotli (`.br`), AVIF, HEIC/HEIF, FLAC, MKV, WebM
- Integrity checks (magic bytes / `zipfile.is_zipfile`) before replacing originals
- OOXML rewrite prefers Info-ZIP `zip` when available (7zz extra fields can break Office)
- `RepackOptions` dataclass and `FileRepacker.repack()` for the library API
- Optional `rich` progress bars (`pip install 'filerepack[progress]'`)
- pytest suite covering atomic replace, CLI, and packer failure paths
- GitHub Actions CI for Python 3.9–3.13 with p7zip installed
- Split docs: `docs/cli.md`, `docs/tools.md`, `docs/library.md`
- ruff instead of flake8

### Removed

- Redundant `bin/filerepack.py`, outdated `README.rst`, deprecated `.travis.yml`
- Unused `pack_jpg_re` / `EXT_IMAGE_MAP` / shell quiet-redirection suffix

## [0.1.4] - 2025-11-12

### Changed

- Added `long_description_content_type` to `setup.py` for proper Markdown rendering on PyPI

## [0.1.3] - 2025-11-12

### Changed

- Updated `requirements.txt` with typer and optional duckdb dependency
- Added `extras_require` to `setup.py` for optional parquet support (duckdb)

## [0.1.2] - 2025-11-12

### Changed

- Converted HISTORY.rst to HISTORY.md
- Updated `setup.py` to use Markdown format

## [0.1.1] - 2025-11-12

### Fixed

- Fixed issue repacking .pub and .xmind files
- Fixed issue jpeg repacking with jpeg-recompress

## [0.1.0] - 2018-01-14

### Added

- First public release on PyPI and GitHub
