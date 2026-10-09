---
title: "Shared CLI options"
description: "Flags shared by filerepack repack and bulk"
---
# Shared CLI options

These flags apply to `repack` and `bulk` unless noted. JPEG/PNG/PDF are lossless
unless `--lossy`, `--pdf-profile`, or a quality flag is set. Results that are
not smaller are discarded unless `--allow-grow`.

| Flag | Meaning |
|------|---------|
| `--dryrun` | Measure savings; do not modify files |
| `--quiet` / `--verbose` / `--debug` | Verbosity; verbose shows available per-file reasons, strategies and record-recompression fallback details |
| `--no-images` | Skip image, video, and audio packers (including cover art). XML/JSON/PDF still run |
| `--no-archives` | Skip nested archive rewriting |
| `--deep` / `--no-deep` | Walk inside archives and recurse through qualified OLE children (default: on); nested XML/JSON is minified |
| `--min-savings PCT` | Keep result only if savings ≥ PCT; finite range 0–100 |
| `--min-size` / `--max-size` | Size filters (`1MB`, `100KB`, …) |
| `--backup` / `--backup-dir` | Required source backup before processing; `--backup-dir` selects its directory and needs `--backup` |
| `--output-dir` | Preserve source and publish results here; unchanged-copy exceptions are listed under [repack](/commands/repack) |
| `--overwrite` | Explicitly allow replacing an existing output/conversion target; never overwrite a required backup |
| `--compression-level 1-9` | Archive compression (default 9) |
| `--jpeg-quality 1-100` | Implies lossy JPEG; also re-encodes images inside PDFs |
| `--png-quality high\|medium\|low` | Implies lossy PNG (pngquant) |
| `--pdf-linearize` | Require linearized PDF output; use `--allow-grow` if it becomes larger |
| `--ole-recompress` | Qualified OfficeArt EMF/WMF/PNG/JPEG, PPT wrappers and HWP compressed streams; default: off |
| `--ole-embedded-recompress` | Qualified DOC/XLS embedded Package/CFB files, losslessly; default: off |
| `--ole-deduplicate-images` | Merge identical compatible images in fully resolved XLS/PPT stores; default: off |
| `--pdf-profile` | Ghostscript Distiller preset: `screen`, `ebook`, `printer`, `prepress`, `default` (implies lossy PDF) |
| `--lossy` | Ghostscript PDF (`/ebook` unless `--pdf-profile` is set), jpegoptim `-m`, pngquant, lossy AVIF/HEIC |
| `--wmv-lossless` | Compatibility alias for `--video-mode lossless`: CRF 0 (or VP9 lossless for WebM) |
| `--video-mode remux\|lossless\|lossy` | Video fidelity (default: remux); lossy mode requires `--lossy` |
| `--convert-container` / `--no-convert-container` | WMV/AVI/ASF/3GP/MPEG-TS → MP4 and standalone plain WARC → `.warc.gz` (default: convert) |
| `--allow-grow` | Keep output even if larger |
| `--keep-meta` | Retain incidental metadata as well as required orientation/color metadata |
| `--max-extract-size` | Skip archive extract if uncompressed size exceeds this (`0` disables; default 8GB, also 100× the archive) |
| `--ultra` | Stronger lossless passes: Parquet zstd 22, `zopflipng` for PNG, `mp3packer -z`, bounded OLE Zopfli50 trials (requires a separately enabled OLE content mode) |
| `--json` / `--csv` | Machine-readable output (mutually exclusive) |
| `--log-file PATH` | Also write CLI messages to a file |
| `--report PATH` | Persistent local audit report; parent must exist and destination must be absent |
| `--report-format json\|jsonl` | Report encoding; inferred from `.jsonl`, otherwise JSON |
| `--report-paths absolute\|relative\|redacted` | Report path disclosure (default: absolute) |
| `--stats` | Extra timing / counts |
| `--progress` | Progress bar (`rich` if installed). `repack` is on for a TTY (`--no-progress` to hide); `bulk` needs `--progress` |
| `--progress-interval N` | Interval when `rich` is not installed (default 10) |

Lossless PNG keeps its encoded bit depth and color type as well as decoded
samples. Each optimizer candidate is checked before size selection. The current
JPEG/PNG adapters conservatively keep all metadata when presentation fields
are present; `--keep-meta` also keeps incidental metadata on other images.

Lossy PDF defaults to Ghostscript `/ebook` (150 dpi) because `/prepress` barely
shrinks scanned pages. Use `--pdf-profile prepress` for the old print-quality
Ghostscript path. Lossless PDF walks embedded image streams when
`filerepack[pdf]` is installed. Encrypted or signed PDFs skip every PDF writer,
including qpdf and Ghostscript. Compression selects the smallest verified PDF;
`--pdf-linearize` is a separate constraint. DICOM
is always lossless JPEG-LS (`gdcmconv` or `dcmcjpls`); `--lossy` does not apply.

Size arguments accept nonnegative values such as `1000`, `1K`, `1KB`, `1.5M`,
`1.5MB`, `2G`, `2GB` and `1T`. Units use powers of 1024; `1G` is 1073741824
bytes. Jobs and progress intervals must be positive integers. Invalid options
are rejected before backups, output copies or encoding.

Existing different output and conversion destinations are refused by default.
For example, `movie.wmv` cannot replace an existing `movie.mp4` without
`--overwrite`. Dry-run measures candidates in scratch space and creates no
output or backup files/directories. It still checks destination policy.

See [`repack`](/commands/repack), [`bulk`](/commands/bulk), and [Formats](/formats/).

## Preserving scientific formats

`repack` and `bulk` accept `--r-compression preserve|gzip|bzip2|xz`,
`--checkpoint-compatibility preserve-mmap|load-only`, `--experimental-formats`,
and byte/record/time limits prefixed with `--format-`. Scientific dry-run inspects
without encoding. `repack-store` requires a distinct `--output-dir` and takes
`--codec-policy preserve|compatible-upgrade`. See the [profile contracts](../formats/scientific.md).

## Profiles and root budgets

`--profile fast|balanced|maximum|preserve` selects version 1 effort defaults:

| Profile | Compression level | Ultra | Incidental metadata |
| --- | --- | --- | --- |
| fast | 3 | false | shared default |
| balanced | 6 | false | shared default |
| maximum | 9 | true | shared default |
| preserve | 6 | false | retain |

Explicit CLI options override profile values, including explicitly supplied
false or default-valued settings. Profiles do not enable loss, image quality
flags or a Ghostscript PDF profile. In Python, `RepackOptions(profile='maximum', ultra=False, compression_level=9)`
and `options_for_profile('maximum', ultra=False, compression_level=9)` both retain
explicit override provenance. Without a profile, existing effort defaults apply.

| Resource flag | Default | Meaning |
| --- | ---: | --- |
| `--format-max-decoded-bytes` | 536870912 | Cumulative decoded bytes (512 MiB) |
| `--format-max-memory-bytes` | 268435456 | Memory grant / sampled worker RSS limit (256 MiB) |
| `--format-max-scratch-bytes` | 2147483648 | Scratch writes and live scratch cap (2 GiB) |
| `--format-max-nodes` | 100000 | Cumulative graph/record visits |
| `--format-max-depth` | 16 | Security nesting depth |
| `--format-timeout` | 120 | Root deadline in seconds |
| `--file-timeout` | unset | Override `--format-timeout` in seconds |
| `--max-temp-bytes` | unset | Override `--format-max-scratch-bytes` in bytes |
| `--tool-threads` | 1 | Threads granted to each encoder |

Byte limits take integer bytes, not `MB` strings; deadlines take seconds. When
both aliases and their `--format-*` equivalents are supplied, `--file-timeout`
and `--max-temp-bytes` take precedence. The decoded/memory/node limits also
apply to supported nested adapters and owned processes. `--tool-threads` sets
native-library thread environment limits; adapters with other private thread
controls still require their documented controls. Owned external commands are
polled every 100 ms for deadline, cancellation, RSS and live scratch; a native
writer can overshoot between polls. Captured command diagnostics are capped at
1 MiB. Each active input has its own grant. Bulk scheduling also reserves aggregate
memory (2 GiB), scratch (8 GiB) and CPU threads (host CPU count); use
`--bulk-max-memory-bytes`, `--bulk-max-scratch-bytes` and
`--bulk-max-cpu-threads` to change them. `--jobs` is an upper bound: the
coordinator reduces active workers to fit these grants. The root defaults are
256 MiB memory, 2 GiB scratch, 512 MiB cumulative decoded bytes, 100,000 node
visits, depth 16 and 120 seconds. `--format-max-depth` controls security depth;
`--max-depth` controls which descendants are optimized. Some legacy validators
still use their separate bounded decoder caps; full cumulative accounting across
every legacy adapter remains an open qualification task.

## Selection and preservation

`--exclude-member PATTERN` is repeatable and case-sensitive. `*` and `?` stay
within one path component; `**` crosses components; a trailing slash selects a
subtree. `--allow-category` and `--skip-category` accept `image`, `audio`, `video`,
`document`, and `data`; explicit skips take precedence. `--max-depth N` limits
optimization depth, with the root at zero. It does not disable extraction safety
limits. Selection reaches supported XML/PDF/cover helpers and nested archives.

`--video-mode remux|lossless|lossy` selects video fidelity. The default is remux;
`--lossy` permits lossy encoding, and explicit `--video-mode lossy` requires that
permission. `--wmv-lossless` remains a compatibility alias. Conflicting modes are
refused before writes. Unsupported streams or failed content checks prevent
publication instead of silently dropping tracks.

`--sqlite-offline` asserts that an in-place SQLite source has no active users.
Sidecars still cause refusal. A distinct output is a transaction-consistent
snapshot that includes committed WAL pages. A single-file backup of a live WAL
source is unsupported. The assertion cannot establish that idle external
connections are absent; close database users before selecting it.

See [inspection](inspect.md) and [reports and resume](reports-and-resume.md) for
planning, audit schema, local path disclosure and checkpoint behavior.

Profile measurements and their corpus limits are recorded in [quality evidence](/development/quality-evidence).
