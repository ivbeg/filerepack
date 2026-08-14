# filerepack — Improvement Plan

> **Date:** 2026-08-14 (updated same day after implementation)
> **Status:** Implemented in **0.2.0**. P0 data-loss paths, lossless defaults, `--jobs`, `doctor`, extra formats, extract-size limits, Info-ZIP OOXML rewrite, ruff, and docs split are in the tree.
> **Scope:** Full review of the current tree (v0.1.4 + large unreleased work, then 0.2.0)

The sections below are the review that drove 0.2.0. They describe the *pre-0.2.0* working tree unless marked done.

---

---

## Executive summary

filerepack is a capable multi-format recompressor with a real CLI, nested-archive walking, and a useful format list (Office/OOXML, ZIP/7z/RAR, gzip/xz/bz2, Parquet, PDF, images, video). Unreleased work already fixed the February 2026 blockers: `os.system()` is gone, `os.chdir()` is gone, tests exist, CI is GitHub Actions, packaging has `pyproject.toml`, and `repack.py` dropped from ~2,157 to 1,189 lines.

The remaining risk is **correctness and safety**, not missing breadth. The tool still deletes originals before a successful rewrite, can drop video output on container conversion, advertises lossless behaviour that is lossy, and skips JPEG/PNG in `bulk`. Features like `--jobs`, config files, and new formats should wait until replace-is-atomic and “keep original if larger” are in place.

**Recommended sequence:** freeze new formats → fix data-loss paths → make compression honest (lossless vs lossy) → finish the library/CLI contract → then add parallelism and extra formats.

---

## Current state (what is already done)

Do **not** re-open the 11 OpenSpec changes under `openspec/changes/`. They describe work that is already in the tree and should be archived after the next release.

| Area | Status |
|------|--------|
| Shell injection (`os.system` + interpolated paths) | Fixed — `_run_command()` uses `subprocess.run` argv lists |
| Process-global `os.chdir()` | Fixed — `cwd=` on subprocess |
| Mutable default `options={...}` | Fixed |
| Duplicate `pack_jpg_re` definition | Fixed (one unused copy remains) |
| Test suite | Present — utils, consts, models, CLI smoke, zip integration (~60 tests) |
| Type hints on `repack.py` | Present |
| `PackResult` / `RepackSummary` | Present; packers return `PackResult`; `FileRepacker` still returns dicts/lists |
| GitHub Actions (3.9–3.12) + flake8/mypy | Present |
| `pyproject.toml` PEP 621 | Present; `setup.py` still duplicated |
| `bin/filerepack.py`, `README.rst`, `.travis.yml` | Removed |
| Packer dispatch map | Partial — `_dispatch_packer` + a second `standalone_packers` dict |

**Metrics (2026-08-14):**

| Metric | Value |
|--------|-------|
| `filerepack/repack.py` | 1,189 lines |
| Package Python | ~2,013 lines |
| Tests | ~469 lines |
| Supported extensions in `SUPPORTED_EXTS` | 60+ |
| Version on PyPI / `__version__` | 0.1.4 (large unreleased delta) |

---

## 1. Correctness and data safety (do first)

### 1.1 Archive rewrite deletes the original before the new archive exists

In `_repack_archive` / `_repack_rar`, the output path (often the original file) is `os.remove`d, then 7zz/rar is invoked. `_run_command` swallows failures. `repack_zip_file` then `rmtree`s the extracted temp tree with no `try/finally` that restores the original.

**If 7zz fails or is missing:** original gone, temp tree deleted or leaked, user data lost.

**Fix:** write the new archive to a temp path → verify it opens and is non-empty → optional size-guard → atomic `replace` onto the original. Keep the extract dir until replace succeeds. Never unlink the original first.

### 1.2 WMV / AVI / ASF conversion deletes the compressed file

`_pack_video_ffmpeg` `move`s the new MP4 onto the original path (still named `.wmv`/`.avi`/`.asf`). `pack_wmv` / `pack_avi` / `pack_asf` then `os.remove(filepath)` and try to rename a path that no longer exists.

**Result:** original deleted, compressed MP4 deleted, `PackResult` points at a missing `.mp4`.

**Fix:** write ffmpeg output to a temp `.mp4`, then `replace` onto `stem.mp4` and remove the original only after that succeeds. Better: keep the original container unless the user passes an explicit `--convert-container` flag.

### 1.3 `--min-savings` mutates then “skips”

Bulk and single-file apply the savings threshold **after** compression. If savings are below the threshold, the file is reported skipped but already rewritten. Only the `--output-dir` copy is removed.

**Fix:** compress to a temp file; replace only if savings ≥ threshold (and, separately, if the new file is smaller).

### 1.4 `bulk` never sees JPEG or PNG

`SUPPORTED_EXTS` lists `gif`, `webp`, `svg`, `tif`, `tiff` but **not** `jpg`, `jpeg`, or `png`. Nested images inside archives still go through `_dispatch_packer`. Standalone `filerepack bulk ./photos` skips every JPEG/PNG.

**Fix:** add those extensions to `SUPPORTED_EXTS`. Add a test that `bulk` collects `.jpg`/`.png`.

### 1.5 “Lossless” claims that are not lossless

| Path | Docs / comments | Actual behaviour |
|------|-----------------|------------------|
| JPEG | Often grouped with image “optimization” | `jpegoptim -m85` — lossy |
| PNG | `pack_png` docstring: “Lossless” | `pngquant` — lossy palette quantization |
| PDF | README: “lossless optimization” | Ghostscript `-dPDFSETTINGS=/prepress` — can resample/re-encode |
| Video default | High quality | ffmpeg CRF 18 — lossy; WMV/AVI/ASF also change container |

This is a product-trust issue, not just wording. Office documents with embedded JPEGs will be visually degraded at quality 85 with no opt-in.

**Fix:** default JPEG/PNG/PDF paths to truly lossless tools (`jpegoptim` without `-m`, `oxipng`/`optipng`, qpdf stream recompress). Keep pngquant / jpeg quality / gs `/prepress` behind explicit `--lossy` (or existing `--jpeg-quality` / `--png-quality`). Say so in CLI help and README.

### 1.6 JPEG/PNG packers ignore tool failure

`pack_jpg` / `pack_jpg_re` / `pack_png` do not check `_run_command`’s return value. A missing `jpegoptim` still returns a `PackResult` with unchanged sizes, which the CLI reports as success.

**Fix:** return `None` on non-zero exit or missing binary (same pattern as `pack_gif`).

### 1.7 Parquet uses the DuckDB **CLI**, not the imported Python module

`pack_parquet` bails if `import duckdb` fails, then runs `['duckdb', '-c', sql]`. `pip install duckdb` does not install the `duckdb` binary. Extra `parquet` is therefore not sufficient.

**Fix:** call the Python API (`duckdb.connect().execute(...)`) **or** require the CLI and drop the Python import check. Prefer the Python API.

---

## 2. Code quality

### 2.1 Two packer registries

`_EXTENSION_DISPATCH` and `_repack_standalone.standalone_packers` encode the same mapping. New formats will be added to one and forgotten in the other (this already happened for JPEG/PNG vs `SUPPORTED_EXTS`).

**Fix:** one registry: `{ext: PackerSpec(fn, kwargs_from_options, category)}`. Drive `SUPPORTED_EXTS`, dispatch, standalone, and CLI help from it.

### 2.2 Results types are half-migrated

Packers return `PackResult`. `FileRepacker.repack_zip_file` / `pack_images` still return `{'stats': [...], 'files': [...], 'final': [...]}`. CLI indexes `results['final'][2]`. `RepackSummary` is unused in production.

**Fix:** return `RepackSummary` (or a small `ArchiveRepackResult`) from `FileRepacker`. Keep a thin dict adapter for one release if needed. README already shows `result.insize` in some examples and `stats['final']` in others — pick one.

### 2.3 Dead constants and unused helpers

Unused in production code (only tests or comments): `EXT_IMAGE_MAP`, `ZIP_SENSITIVE_EXTS`, `ZIP_PATH`, `_QUIET_SUFFIX`, `pack_jpg_re` / `JPEG_RE_*`.

`ZIP_SENSITIVE_EXTS` used to force the system `zip` tool for OOXML. All ZIP-based formats now go through `7zz -tzip`. That is simpler, but 7-Zip ZIP extra fields have historically broken some Office files. After atomic replace is in, add an OOXML round-trip test (open with `zipfile` + optional `lxml` `[Content_Types].xml`) and consider `zip` as fallback for `ZIP_SENSITIVE_EXTS`.

### 2.4 Duplicated packer bodies

- `pack_gzip` / `pack_xz` / `pack_bz2` — same decompress-to-memory → optional CLI → rewrite pattern
- `pack_wmv` / `pack_avi` / `pack_asf` — identical rename logic (and the same bug)
- `pack_pdf` / `pack_tif` — primary tool + fallback + temp move
- CLI `repack` vs `bulk` option lists — ~20 duplicated Typer options

**Fix:** one `_pack_stream_codec(...)` for gzip/xz/bz2 (and later zstd); one `_pack_with_fallback(...)`; Typer callback or shared option decorator for CLI flags.

### 2.5 Memory and robustness

- gzip/xz/bz2 `read()` the whole decompressed payload. Multi-GB logs will OOM.
- `_expand_globs` runs on **every** argv token. A filename containing `*`, `?`, or `[` is expanded as a glob.
- `_run_command(..., text=True)` can raise `UnicodeDecodeError` on non-UTF-8 tool output (Windows).
- No zip-bomb / max-extract-size limit on nested archives.
- `create_backup` to `--backup-dir` uses `basename` only — two files named `report.docx` in different folders overwrite one backup.
- Temp extract dirs are not cleaned if `getsize` raises after a failed rewrite.

### 2.6 CLI contract bugs

| Issue | Detail |
|-------|--------|
| `--jobs auto` | Option type is `int`; the `jobs.lower() == 'auto'` branch is dead |
| `bulk --csv` | `output_csv` expects list-of-lists; bulk passes dicts → `KeyError` |
| `--json` / `--csv` | Mutually exclusive in code (`if/elif`) but both flags can be passed |
| `--log-file` | Configures `logging`, but user output is `typer.echo` — log file stays empty |
| Global `_verbose_level` | Process-global; blocks clean parallel `--jobs` even after cwd fix |
| `--jobs` help | Still documents parallel jobs; body always sequential |

### 2.7 Tests are a start, not coverage of the risk

Present: `parse_size`, consts membership, dataclass properties, CLI `--help` / missing path, glob expand, zip dry-run smoke.

Missing: atomic replace, video rename, JPEG in bulk, CSV bulk output, min-savings restore, packer failure → `None`, OOXML validity, missing-tool behaviour, gzip large-file streaming (mocked).

Integration tests that need `7zz` will fail in CI unless the workflow installs p7zip (today CI only `pip install -e ".[dev]"`).

---

## 3. Features (after safety)

### 3.1 Make existing flags real

1. **`--jobs N`** — `ProcessPoolExecutor` (external tools release the GIL; processes avoid shared `FileRepacker` state). Requires: no globals, atomic replace, per-file temp dirs.
2. **Keep original if larger** — default on; `--allow-grow` to override.
3. **`--exclude-dir`** — skip `.git`, `node_modules`, `__pycache__` by default.
4. **Tool path config** — `~/.config/filerepack/config.toml` + `FILEREACK_7ZZ` (and friends). Resolve `7z` if `7zz` is missing.
5. **`filerepack doctor`** — print which binaries are on PATH, versions, and which formats are enabled.
6. **Integrity check before replace** — `zipfile.is_zipfile`, PDF `%PDF` header, image magic, `gzip` header. Fail closed.

### 3.2 Honest compression modes

- `--mode lossless` (default) vs `--mode lossy`
- JPEG: lossless strip-metadata by default; `--jpeg-quality` implies lossy
- PNG: `oxipng` / `optipng` default; pngquant only with `--png-quality` or `--lossy`
- PDF: qpdf object-stream recompress default; Ghostscript `/prepress` as `--pdf-profile prepress`
- Video: do not change container unless asked; `--wmv-lossless` is a misleading name for all video

### 3.3 UX

- Replace `--progress` interval prints with `rich` progress (optional extra)
- `filerepack repack file.docx --json` should write a single object; bulk a document with `summary` + `files`
- Exit codes: `0` ok, `1` usage/error, `2` some files failed (`--continue-on-error`)
- `--dryrun` should never create/delete user-visible files (including backups)

### 3.4 Formats worth adding (P2, after the registry)

High value, low drama: `.zst`, `.br`, `.webp` already present, AVIF/HEIC via `magick`, FLAC recompress, `mkv`/`webm` via ffmpeg.

Skip until asked: arbitrary “convert WAV→FLAC” (format change, not repack). Same rule as WMV→MP4.

### 3.5 Library API

Today the public API is `FileRepacker().repack_zip_file(...)` with a dict of options. A stable library would look like:

```python
from filerepack import Repacker, RepackOptions

r = Repacker(tools=ToolPaths.from_env())
summary = r.repack("file.docx", RepackOptions(dry_run=True, mode="lossless"))
```

Keep CLI as a thin Typer layer over that.

---

## 4. Project hygiene

| Item | Action |
|------|--------|
| 11 OpenSpec changes | Archive them (`openspec archive … --skip-specs --yes` if specs were never the source of truth) so the next real proposal is visible |
| Dual `setup.py` + `pyproject.toml` | Single source: `pyproject.toml`; keep `setup.py` only if you still need `long_description = README + CHANGELOG` (move that into a hatch/setuptools hook) |
| `Makefile` | Points at `tests` (dir is `test`), `coverage run setup.py test`, `sphinx-apidoc` with no `docs/` |
| README (~1,000 lines) | Split: short README + `docs/cli.md` + `docs/tools.md`. Remove `easy_install`. Ubuntu section currently runs `brew install unrar`. |
| Version | Ship **0.2.0** after P0 safety fixes; still `Pre-Alpha` in classifiers is honest until then |
| CI | Install `p7zip-full jpegoptim pngquant` on Ubuntu; add 3.13; pin Codecov or drop the upload if no token |
| Lint | `ruff` instead of flake8; mypy on `test/` too |
| `CONTRIBUTING.rst` | Missing or unreadable in tree; replace with a short `CONTRIBUTING.md` |
| Logging | One logger; CLI verbose levels map to it; `--log-file` then works |

---

## 5. Priority roadmap

### Phase A — stop losing data (P0, small diffs, high urgency)

1. Atomic archive replace (temp file → verify → `os.replace`)
2. Fix WMV/AVI/ASF output path (no delete-then-rename)
3. Compress-to-temp for `--min-savings`; restore/skip without mutating source
4. Add `jpg` / `jpeg` / `png` to `SUPPORTED_EXTS`
5. Treat missing/failed jpegoptim/pngquant as failure (`None`)
6. Use DuckDB Python API for Parquet

### Phase B — honest behaviour + one registry (P1)

1. Default lossless JPEG/PNG/PDF; lossy only when requested
2. Keep original if `outsize >= insize`
3. Single packer registry driving extensions + dispatch
4. `FileRepacker` returns dataclasses; fix `bulk --csv` and `--jobs auto`
5. Stream gzip/xz/bz2; stop glob-expanding non-glob args
6. Tests for A+B; CI installs `p7zip-full`

### Phase C — features that are already promised (P1/P2)

1. `--jobs` via process pool
2. `filerepack doctor` + tool-path config + `7z` fallback
3. `--exclude-dir` and default skip of VCS/vendor dirs
4. Integrity checks before replace
5. `rich` progress; consistent JSON schema; exit codes

### Phase D — growth (P2/P3)

1. zstd / brotli / AVIF; optional audio
2. Clean library API
3. README split, Makefile, drop duplicate setup metadata
4. Release 0.2.0 with CHANGELOG; archive OpenSpec deltas

---

## 6. What not to do yet

- Do not add more formats until Phase A is done (each format copies the unsafe replace pattern).
- Do not implement `--jobs` on the current globals + in-place unlink.
- Do not treat the 11 existing OpenSpec folders as a backlog — they are completed work awaiting archive.
- Do not default Ghostscript `/ebook` or lower JPEG quality for “better numbers”; savings that destroy documents will tank trust.

---

## 7. Suggested first implementation slice

One PR, no new formats:

1. `_atomic_replace(src, dest)` + archive/video/standalone packers write to temp
2. `SUPPORTED_EXTS` += jpg/jpeg/png
3. Registry consolidation (can be a follow-up if the PR is large)
4. Tests: failed 7zz does not delete fixture zip; bulk lists `photo.jpg`; wmv rename does not `unlink` the only copy (mock ffmpeg)

That slice removes the class of bugs that make the tool unsafe to run on real documents.
