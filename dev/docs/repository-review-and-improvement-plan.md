# Repository review and improvement plan

Review date: **2026-10-02**. Baseline: commit `2d41e71` (`0.3.0`) plus the existing working-tree changes.

## 1. Assessment and recommended direction

filerepack has progressed considerably beyond the earlier improvement report. It already has atomic replacement helpers, lossless JPEG/PNG/PDF defaults, dataclass results, process-based bulk jobs, configurable tool discovery, extraction-size checks, progress reporting, a documentation site, and a substantial test suite. These are useful foundations to retain.

The next priority is **preserving content and reporting outcomes accurately**, before expanding the extension list. Small reproductions found accepted rewrites that remove ZIP members, change tarball layout, alter XML text and JSON numbers, discard Parquet metadata, and overwrite an unrelated output file. Passing lint and the existing tests does not establish preservation across the supported formats.

Recommended order:

1. Fix confirmed preservation defects and add regression fixtures.
2. Strengthen candidate validation, resource limits, result semantics, and bulk execution.
3. Simplify shared infrastructure and verify supported platforms and optional extras.
4. Add inspection, resumable batch processing, configurable profiles, and deeper format-specific optimization.

This document is a review and proposed backlog. It does not change implementation or declare any future capability implemented.

**Implementation progress (2026-10-03):** A1–A5, the early A6 Parquet/ODF/EPUB fixes and A7 distribution checks are implemented and verified locally through the corresponding changes in the [OpenSpec roadmap](../../openspec/ROADMAP.md). B1 now has shared typed staging/acceptance/publication and subprocess interfaces, filesystem/source/link/durability policies, dedicated format-family modules, compatibility exports and typed worker/progress contracts. Its local implementation is complete; Linux/Windows and actual second-filesystem evidence remain open. The two broader A6-related proposals remain partial: other data writers, SQLite live-database preservation, resource budgets, alias/capability audits and application fixtures are still open. The findings and delivery checklist below retain the original review snapshot; current implementation, verification and rollout status lives in OpenSpec. The latest full suite with DICOM dependencies passes 857 tests with three skips; the base environment passes 821 tests with 39 skips. B1/C5 now includes 49 transaction cases and 92 family/compatibility/scratch cases. Installed wheel/sdist evidence and its interpreter-specific counts are recorded in OpenSpec; remote CI, integration and deployment remain separate work.

## 2. Scope and validation baseline

Reviewed the Python package, CLI, dispatch and extension tables, archive writers, standalone codecs, nested assets, DICOM gate, result models, tools/configuration, tests, packaging, CI, documentation, and OpenSpec state.

The checkout already contained edits to `.idea/workspace.xml`, `filerepack/__main__.py`, `test/conftest.py`, `test/test_cli.py`, and `test/test_progress.py`, plus untracked `test/helpers.py`. These were included in the working-tree review and left unchanged. The new CLI wording and ANSI-normalization test changes were treated as existing work.

| Check | Observed result |
| --- | --- |
| `python -m pytest --cov=filerepack --cov-report=term-missing` | **306 passed, 1 skipped**, 307 collected; **62%** statement coverage |
| `ruff check filerepack test` | Passed |
| `mypy filerepack test --ignore-missing-imports` | Passed; 35 source files checked |
| `python -m build --no-isolation --outdir /tmp/filerepack-review-dist` | Wheel and source distribution built; license-metadata deprecation warnings |
| `npm --prefix docs run build` | Passed using the installed documentation dependencies |
| `openspec validate --all --strict --no-interactive` | All three active changes passed |
| Test collection from the freshly extracted source distribution | **Failed**: three import errors for missing support modules |
| Synthetic preservation checks | Confirmed defects described below, using temporary files only |

Execution environment: macOS, Python 3.13.7. Actual tools were used for ZIP/tar rewrites and CAB/WIM write probes; PyArrow and DuckDB were used for the Parquet check. Conversion collision and cross-device failure were checked with mocked encoder/filesystem boundaries. No original repository fixtures or user documents were rewritten.

The local environment lacks `mutagen`, `pikepdf`, `fontTools`, `defusedxml`, and `tomli`. Their real integrations were not established by this review. Windows/Linux execution, application-level Office/PDF rendering, complete codec fidelity, clean-environment dependency installation, and performance benchmarks remain unverified. Coverage and build success are local results, not claims about remote CI.

## 3. Current features and implementation quality

The extension tables contain **252 distinct entries**: 146 archive aliases and 106 standalone aliases. There are **79 packer keys**. These counts describe routing breadth, not 252 independently validated formats. Every standalone extension currently resolves to a registered packer.

| Area | Implemented today | Main improvement opportunity |
| --- | --- | --- |
| CLI and library | `repack`, `bulk`, `doctor`; `FileRepacker`, `RepackOptions`, `PackResult`, `RepackSummary`; legacy mapping access | Explicit statuses, correct destinations, consistent validation and reports |
| Archives and Office | ZIP/7z/RAR, OOXML/ODF/EPUB and many aliases; nested dispatch; Info-ZIP preference for OOXML; tar/stream families; WIM; attempted CAB writing | Preserve member sets and container rules; correct tar layers; capability-check writers |
| Images | JPEG/PNG lossless passes; opt-in quality flags; GIF/WebP/SVG/TIFF and many external-tool formats; SVG data URIs; ultra PNG candidates | Verify frames, dimensions, color/profile behavior, metadata policy, and actual lossless encoding |
| PDF and Illustrator | qpdf rewrite; Ghostscript profiles; optional pikepdf DCT/JPX image-stream optimization; PDF-based AI files | Consistent signature/encryption protection, stronger validation, broader supported image streams |
| Video | FFmpeg H.264/VP9 transcoding; selected container conversion; CRF 0 option | Explicit lossy policy, complete stream preservation, collision-safe conversion |
| Audio and covers | FLAC/ALAC/WavPack/TTA/APE paths; MP3/optivorbis tools; optional mutagen cover walking | Preserve all tracks/tags/covers and expose unsupported codec reasons |
| DICOM | Transfer-syntax eligibility check; lossless JPEG-LS via GDCM/DCMTK; image/category dispatch | Complete signature scan, parser bounds, decoded-pixel verification |
| Data and fonts | Parquet, SQLite/GPKG/MBTiles, ORC/Avro/Feather/Arrow, HDF5/NetCDF, WOFF/WOFF2; PSD ZIP channel recompression | Metadata/schema fidelity, batch streaming, SQLite concurrency policy, real fixtures |
| Batch processing | Recursive scan, extension/size filters, directory exclusions, backups/output directories, process pool, progress, JSON/CSV | Bound submissions, manage cancellation and destination conflicts, preserve per-file outcomes |
| Safety and operations | argv subprocesses, fixed command timeouts, temporary candidates, size acceptance, basic signatures, extraction caps, environment/TOML tool overrides | Full transaction lifecycle, validation depth, cumulative budgets, executable/capability checks |
| Engineering | pytest, Ruff, mypy, Ubuntu Python 3.9–3.13 CI, Docusaurus build/deployment | Extras/platform matrices, source-distribution tests, preservation tests, current specs |

Strengths to preserve:

- Subprocess commands use argument lists and explicit `cwd`; the earlier shell and process-global directory problems have been addressed.
- `_commit_output` centralizes size thresholds, dry-run reporting, candidate cleanup, and replacement. It is the right place to strengthen transaction guarantees.
- `_PACKERS`, `FileKind`, and result dataclasses provide useful extension points without requiring a new plugin framework.
- Missing tools usually leave source bytes unchanged. Existing failure-path tests and archive dry-run staging are valuable.
- Documentation and CI are usable today; improvement should extend them rather than replace them.

## 4. Prioritized review findings

Priority definitions: **P0** = confirmed content loss or destructive overwrite to fix before the next release; **P1** = correctness or safety contract requiring the next reliability milestone; **P2** = maintainability and delivery improvements. “Reproduced” means observed with synthetic files; “inspection” identifies a code path or missing safeguard without claiming a demonstrated exploit or complete real-format failure.

### R01 — P0: archive rebuild drops root dotfiles

**Reproduced with installed 7zz.** A ZIP containing `.hidden` and `visible.txt` was rewritten from 10,219 to 183 bytes; only `visible.txt` survived. `_expand_globs` uses `glob('*')`, which omits root dotfiles whenever visible entries exist. The reduced size passes acceptance despite missing content.

Evidence: `filerepack/repack.py:36` (`_expand_globs`), `:1571` (`_write_archive`), `:1666` (`_write_infozip`).

**Change:** enumerate every member explicitly, including hidden entries, with tool-specific safe argument handling. Compare the candidate member manifest to the intended output manifest before replacement. Preserve empty directories and define handling of duplicate names, links, permissions, and archive comments. A blanket `--` insertion is not interchangeable across all external tools; test each adapter.

**Acceptance:** root `.hidden`, hidden directories, empty directories, Unicode names, and names resembling options survive ZIP/7z/tar/OOXML rebuilds. A missing or extra member rejects the candidate.

### R02 — P0: compressed tar rebuild introduces an extra tar layer

**Reproduced with installed 7zz and default size acceptance.** An uncompressed-level gzip tarball containing `document.txt` was rewritten from 10,263 to 170 bytes. The resulting tarball contained `bundle.tar`, rather than `document.txt`. `7zz x` extracts the outer stream into a tar file, while `_write_tar_bundle` wraps the extraction directory in another tar. Nested walking can optimize that inner tar but does not correct the outer layout.

Evidence: `filerepack/repack.py:1483` (`_extract_7z`), `:1619` (`_write_tar_bundle`); `filerepack/formats.py` compound/family mappings.

**Change:** explicitly decode the stream, extract the tar payload, optimize members, rebuild the tar, and encode exactly one outer stream. Bound and validate each stage. Audit aliases such as `gem`, `crate`, and `unitypackage` against their actual container structure instead of assuming every alias shares the same wrapper.

**Acceptance:** member paths, member types, links, and payloads round-trip for tar.gz/tgz, tar.xz, tar.bz2, and available optional codecs, with both deep modes. Rejected or failed stages preserve source bytes.

### R03 — P0: XML minification changes preserved text

**Reproduced without external tools.** `<r xml:space="preserve">\n  <a/>\n  <b/>\n</r>` lost all its whitespace text nodes. CDATA text `hello>\n<world` became `hello><world`. `_XML_GAP` operates on raw bytes after parsing and cannot distinguish element-only indentation from text, inherited `xml:space`, CDATA, or other lexical contexts. The existing tests preserve same-line text, which does not cover these cases.

Evidence: `filerepack/markup.py:69` (`minify_xml_bytes`); `test/test_markup.py`. The preservation semantics are specified by [XML 1.0 whitespace handling](https://www.w3.org/TR/xml/#sec-white-space).

**Change:** use lexical/context-aware handling and a conservative policy for unknown XML vocabularies. Only remove whitespace whose insignificance is established for the supported vocabulary. Preserve mixed content, CDATA, inherited `xml:space`, entities, comments, processing instructions, namespaces, and declaration/encoding consistency. Do not replace this regex with generic ElementTree serialization that introduces different lexical changes. Make hardened parser availability deterministic rather than silently changing behavior with the environment.

**Acceptance:** text/tail content and preserved regions compare equal before/after; fixtures include OOXML text, XHTML mixed content, inherited preservation, CDATA, namespaces, and alternate encodings. Invalid or unsupported input returns an explicit unchanged/unsupported outcome.

### R04 — P0: destinations can overwrite unrelated files, even before option validation

**Reproduced in the CLI; conversion boundary also reproduced with a mock encoder.** An existing output JSON file was overwritten by `--output-dir` before an invalid `--pdf-profile` caused exit 1. A synthetic WMV conversion replaced an already existing `movie.mp4` and removed `movie.wmv`. Path comparisons use strings, not normalized identities. RAR conversion has the same unguarded destination pattern.

Evidence: `filerepack/__main__.py:235–252`; `filerepack/jobs.py:27–40`; `filerepack/repack.py:835` (`_pack_video`), `:1696` (`_repack_rar`); `filerepack/utils.py:135` (`create_backup`).

**Change:** validate options and source/destination identity before any copy or backup. Stage output and publish it only after acceptance. Default to preserving an existing different destination; expose an explicit overwrite policy if needed. Reserve conversion destinations during bulk planning, including conflicts such as `movie.wmv` and `movie.avi` both targeting `movie.mp4`. Define backup collision behavior and never silently overwrite the only previous backup.

**Acceptance:** invalid flags cause zero writes; existing output/conversion targets remain unchanged; relative/absolute aliases and symlinks are handled consistently; parallel jobs cannot publish to the same target. A requested backup failure produces a visible failure and prevents destructive work by default.

### R05 — P0: DICOM signature gate misses normal trailing and nested signatures

**Reproduced with synthetic tagged datasets; no real signed clinical document was processed.** `dicom_is_packable` returned `True` when a Digital Signatures Sequence was appended after Pixel Data, and when it was inside a sequence item. `_dataset_ok` stops at Pixel Data; `_skip_value` skips nested elements without checking signature tags. The current fixture places signatures before Pixel Data, masking the trailing case.

Evidence: `filerepack/dicom.py:107` and `:148`; `test/dicom_fixtures.py:68`; `test/test_dicom.py`. DICOM requires increasing tag order, so `(FFFA,FFFA)` follows `(7FE0,0010)` in the normal top-level ordering. See [DICOM data element ordering](https://dicom.nema.org/medical/dicom/current/output/chtml/part05/chapter_7.html) and the [Digital Signatures macro](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.12.html).

**Change:** inspect the full dataset, including nested sequences, while safely skipping pixel payloads. Validate declared lengths and add a nesting bound. Reuse a maintained parser if that reduces the safety burden; otherwise document and test the supported subset. Verify the output transfer syntax, image attributes, frame count, decoded pixels, and retained non-pixel data rather than only `DICM` bytes.

**Acceptance:** trailing/nested signature sequences, truncated Pixel Data, malformed lengths, and excessive nesting all prevent rewrite. Supported unsigned fixtures retain decoded pixel values and relevant attributes.

### R06 — P0: JSON and Parquet transformations lose information

**Reproduced.** JSON `1.234567890123456789` became `1.2345678901234567`, and two `same` keys collapsed to the final key. `json.loads`/`dumps` changes numeric tokens and duplicate-member structure. A real PyArrow Parquet file with an `app` schema-metadata entry was rewritten by DuckDB; that metadata disappeared.

Evidence: `filerepack/markup.py:40` (`pack_json`); `filerepack/repack.py:295` (`pack_parquet`); `filerepack/codecs.py:548–642` for other data rewrites.

**Change:** minify JSON lexically, removing only insignificant whitespace outside strings while preserving numeric tokens and object-member order/duplicates. Reject non-standard non-finite literals. Define preservation contracts for data formats: logical values, schema/types/nullability, custom metadata, identifiers, and file-vs-stream framing. Preserve these with a suitable writer or skip unsupported cases. For SQLite, define an offline/snapshot policy covering open writers, WAL/SHM sidecars, and concurrent changes before replacing a live database file.

**Acceptance:** JSON high-precision numbers, large exponents, duplicate keys, escaped strings, and valid scalar roots survive. Parquet metadata and schema round-trip alongside row values. Arrow stream input does not silently become file framing without an explicit conversion policy. Data-format tests include nested types, decimals, timestamps, nulls, and metadata.

### R07 — P1: standalone library `outfile` is ignored

**Reproduced.** `FileRepacker().repack('source.json', outfile='requested.json')` changed the source and created no requested output. `dest` is computed, but standalone dispatch receives `filename` and each packer commits back to that path. The CLI hides this by copying inputs itself.

Evidence: `filerepack/repack.py:1382` (`repack_zip_file`).

**Change:** make destination semantics part of the shared transaction API and use that API from both CLI and library. Define behavior when a candidate does not shrink: whether an explicit output receives an unchanged copy or no artifact. Report the actual destination, including converted extensions. Preserve legacy result access while adding destination information.

**Acceptance:** standalone and archive `outfile` calls preserve the source, produce the documented destination, honor dry-run, and respect collision/acceptance policies. Tests invoke the library directly, without the CLI's pre-copy workaround.

### R08 — P1: video defaults and stream retention need an explicit fidelity contract

**Command construction reproduced; complete media fidelity not tested.** With `lossy=False` and default options, MP4 dispatch still constructs `libx264 -crf 18`. Video is therefore currently lossy by default, unlike JPEG/PNG/PDF. `_encode_video` and `_pack_ffmpeg_audio` also omit explicit stream mapping; copying audio alone does not guarantee retention of every audio track, subtitle, attachment, or data stream. FFmpeg's [automatic stream-selection rules](https://www.ffmpeg.org/ffmpeg.html#Automatic-stream-selection) explain this limitation.

Evidence: `filerepack/repack.py:807` (`_encode_video`), `:835` (`_pack_video`); `filerepack/codecs.py:394` (`_pack_ffmpeg_audio`).

**Change:** decide and document whether default video processing should remux, use verified lossless encoding, or skip without explicit lossy permission. Changing the existing default requires an OpenSpec proposal and migration notes. Add structured probing, explicit mapping, metadata/chapter/disposition handling, and a destination-container compatibility policy. Refuse transformations that would silently drop unsupported streams. Audit ImageMagick and PNG/APNG paths for frames, bit depth, transparency, and color fidelity; `-quality 100` alone is not an established preservation contract in this repository.

**Acceptance:** multi-audio/subtitle/attachment/chapter fixtures retain the intended streams and metadata. Lossless modes compare decoded frames/samples; lossy modes record the requested settings. Animated and high-bit-depth images retain frame count and supported color characteristics.

### R09 — P1: candidate validation is too weak to establish integrity

**Reproduced against validators.** Two JPEG magic bytes, `%PDF` alone, arbitrary MP4 text longer than 32 bytes, and arbitrary Arrow-like content were accepted as valid. ZIP detection checks structural recognition rather than all member CRCs. Some packers pass no validator; unknown validation kinds return `True`. RAR output has no format verification argument.

Evidence: `filerepack/utils.py:291` (`_verify_special`), `:388` (`verify_output`); `filerepack/repack.py:119`; `filerepack/codecs.py:595–642`; `filerepack/repack.py:1696`.

**Change:** introduce validator adapters with explicit guarantees: signature recognition, structural validation, and preservation verification. Require structural validation for replacement, reject unknown validation kinds, and use archive test commands/CRC checks, appropriate parsers, or decoders. Hash lossless stream payloads; compare archive manifests; validate schema/metadata and media dimensions/frames as appropriate. Apply signature/encryption protection at the whole PDF/package transaction boundary, since the pikepdf-only gate does not protect later qpdf/Ghostscript rewrites. Audit signed/checksummed aliases such as JAR/APK/MSIX/WHL before allowing nested content changes.

**Acceptance:** truncated/corrupt output is rejected despite valid magic; every writer declares a validator; missing validators produce a reasoned skip/failure. Signed or integrity-protected inputs follow a documented preservation policy and cannot be silently invalidated.

### R10 — P1: replacement is not fully portable and loses filesystem metadata

**Mode change reproduced; cross-device failure reproduced with an `EXDEV` mock.** A JSON file changed from mode `0644` to `0600` because the temporary candidate replaced its inode. `_make_temp` uses the system temp directory rather than the destination filesystem. `os.replace` can consequently fail across devices; cleanup then discards the candidate, although the source remains intact. `FileRepacker.temppath` only controls archive extraction, not all candidates.

Evidence: `filerepack/repack.py:105` (`_make_temp`), `:119` (`_commit_output`), `:1347` (`FileRepacker.__init__`); `filerepack/containers.py:31`.

**Change:** create final publish candidates beside the destination or copy into a verified destination-local staging file before atomic replacement. Define and preserve source mode and the requested timestamp/extended-attribute policy. Detect source changes between inspection and commit. Define symlink/hardlink behavior explicitly. Offer configurable scratch storage separately from publish staging; add fsync behavior if crash durability is promised.

**Acceptance:** files retain documented permissions/metadata, cross-volume scratch locations work, failed publication preserves source and existing destination, source changes cause conflict, and no partial output becomes visible.

### R11 — P1: failure outcomes and machine-readable reporting are misleading

**Reproduced.** A `broken.gz` containing `not gzip` returned worker status `processed`, with zero savings. Missing tools, disabled packers, rejected candidates, unsupported input, and actual codec failures can all collapse into an unchanged summary. `bulk --dryrun --json` emitted ordinary scanning/processing messages before the JSON document, so `json.loads(stdout)` failed. Failure and skip details are also omitted from `acc.results`.

Evidence: `filerepack/models.py`; `filerepack/jobs.py:65–83`; `filerepack/repack.py:1382`; `filerepack/__main__.py:32`, `:356`, `:432`, `:589–594`. Archive summaries do not expose the outer candidate's `replaced` flag; nested result paths refer to deleted staging files. `elapsed_seconds` is defined but not populated.

**Change:** introduce an explicit outcome vocabulary such as `replaced`, `unchanged`, `skipped`, `unsupported`, `failed`, and `predicted`, with stable reason codes, source/destination/member paths, actual vs predicted sizes, validator/tool information, and timing. Keep legacy mapping compatibility. Send human diagnostics to stderr and reserve stdout for JSON/CSV. Include all per-file outcomes and define single/bulk exit codes from those outcomes. Report outer archive savings separately from inner results to avoid suggesting rejected changes were published.

**Acceptance:** corrupt input fails visibly; unavailable tools and no-growth decisions are distinguishable; plain JSON/CSV parses without `--quiet`; dry-run results are marked predicted; archive reports use durable member names; summary counters reconcile with every input.

### R12 — P1: bulk execution lacks bounded submission and effective fail-fast behavior

**Inspection.** `_run_bulk_jobs` submits the entire input list at once. Breaking after a failure still exits the executor context with its normal wait behavior, so submitted jobs can continue mutating files while their results are never consumed. The scan does not exclude an existing output/backup subtree inside the input directory. Backup naming uses a check-then-copy sequence that is unsafe under competing workers. `--jobs auto` uses CPU count without a shared resource budget; external tools may also run multiple threads.

Evidence: `filerepack/__main__.py:330`, `:386–429`; `filerepack/utils.py:135`; `filerepack/jobs.py`.

**Change:** use a bounded in-flight queue and incremental scanning; reserve destinations/backups centrally; exclude resolved output and backup trees. Stop submitting on abort, cancel pending tasks, and account for running tasks explicitly. Add cooperative cancellation/subprocess management and a clear partial-result policy. Limit CPU, disk, and memory pressure independently of worker count. Test process spawning on supported platforms.

**Acceptance:** in-flight work stays bounded for large directories; fail-fast behavior and completed writes are accurately reported; interrupts produce a usable partial report; no input/output/backup path is processed twice; serial and parallel runs agree on outcomes.

### R13 — P1: resource and extraction safeguards are incomplete

**Inspection.** Limits are usually preflight estimates. The unrar path checks size only after extraction; 7z checks actual extracted size only when listing was unavailable. Nested archives each receive fresh limits, with no shared depth/byte/member budget. Standalone stream decoding and PSD `zlib.decompress` are unbounded by these archive options. `_peek_cli_tar` blocks on reading 512 bytes without a read timeout. No application-level member/path/link containment validation is performed before extraction.

Evidence: `filerepack/repack.py:179`, `:220`, `:1483`, `:1508`, `:1530`; `filerepack/formats.py:187` (`_peek_cli_tar`); `filerepack/codecs.py:903` (`_rezip_payload`).

**Change:** carry a shared operation context with cumulative decoded bytes, scratch bytes, member count, nesting depth, deadline, and cancellation. Enforce streaming output caps and actual extraction monitoring, not only listed sizes. Validate normalized member paths and link targets; define a conservative policy for links and duplicate/case-colliding paths. Keep subprocess logs bounded and expose timeouts. These are missing defenses, not proof that a particular installed archiver permits traversal.

**Acceptance:** nested/stream/PSD stress fixtures stop within configured limits and leave originals intact; stalled decoders terminate; escaping paths/links are rejected; total scratch usage is bounded across workers.

### R14 — P1: generic archive writers do not preserve specialized container rules

**ODF ordering reproduced; other aliases need targeted validation.** A synthetic ODT with `mimetype` first was rebuilt with `content.xml` first. ODF requires `mimetype` first, uncompressed, without a header extra field; this is a container requirement beyond ZIP recognition. See [OpenDocument package requirements](https://docs.oasis-open.org/office/OpenDocument/v1.3/OpenDocument-v1.3-part2-packages.html). Other ZIP-based formats can also require prescribed ordering, compression, headers, manifests, or signatures.

Evidence: `filerepack/consts.py` (`ARCHIVE_EXTS`, `ZIP_SENSITIVE_EXTS`); `filerepack/repack.py:1571`, `:1666`.

**Change:** distinguish a generic ZIP family from format-specific container policies. Add ODF/EPUB mimetype handling and semantic package checks, audit USDZ and executable/package aliases, and preserve or explicitly skip unsupported wrappers/signatures. Test CAB write capability: the installed 7zz returned **`E_NOTIMPL`** for `a -tcab`, while WIM creation succeeded. CAB is presently a routing attempt, not working recompression on this backend.

**Acceptance:** valid ODF/EPUB structure and archive metadata survive; signed/unsupported packages skip with reasons; advertised write support is backed by a successful round-trip fixture on the declared tool/platform.

### R15 — P2: tools, option validation, packaging, and specification state need cleanup

**Reproduced and inspected:**

- `doctor` labels an environment override pointing to a nonexistent 7zz executable as `ok`, because discovery accepts arbitrary configured strings. Tool versions, format write capabilities, and optional Python modules are absent from diagnostics (`filerepack/tools.py:112–183`).
- Python 3.9/3.10 TOML loading falls back to `tomli`, but packaging does not declare it. A normal installation without it silently ignores the config (`pyproject.toml:30–44`).
- CLI accepts quality `500`, compression level `99`, and unknown PNG quality in a dry-run. `parse_size('1G')` returns `1`; negative sizes are accepted through the integer fallback. Invalid min/max input is not consistently converted to a friendly CLI error (`filerepack/utils.py:19`, `:403`; CLI option definitions).
- `_setup_log` uses a warning threshold by default while CLI messages log at info, and does not reset `_log_enabled` on subsequent invocations (`filerepack/__main__.py:66`).
- The built source distribution contains test modules but omits `conftest.py`, `__init__.py`, `dicom_fixtures.py`, and the local `helpers.py`. Collection fails; the missing DICOM helper affects the committed code independently of the local helper change. There is no explicit source manifest or artifact-test CI job.
- CI runs Ubuntu and `[dev]`; it does not exercise the optional data/fonts/media/pdf extras or macOS/Windows. Some integration tests return early when work did not occur, yielding a pass instead of an explicit skip/failure. Coverage is 35% for `codecs.py`, 46% for `covers.py`, and 56% for `repack.py`.
- Packaging builds emit deprecated license table/classifier warnings. The actual license is BSD 3-Clause; align metadata with it using a compatible build-backend version.
- `openspec list --specs` reports no current specs. Three completed changes remain active; `openspec/project.md` still says no tests exist and describes the former monolithic architecture. `dev/docs/improvement_report.md` is a historical baseline, not a current backlog.

**Change:** validate executable identity/capability; add the conditional TOML dependency or explicitly revise supported versions; validate all options centrally before writes; repair logging state; include complete test support in the source distribution; add artifact/extras/platform checks; update project guidance and reconcile completed changes with current specs. Check fresh extras installations for required runtime codec dependencies, including Avro's selected compression backend. Keep tool/version pins deliberate and test compatibility instead of updating versions without evidence.

**Acceptance:** capability diagnostics agree with runnable tools; invalid options make no writes; Python 3.9/3.10 config is tested; installed wheel and extracted source distribution pass their intended checks; missing integrations skip explicitly; project/spec documentation matches implemented behavior.

## 5. Architecture improvements

Implement these incrementally after reproductions are retained as regression tests. The goal is to reduce hidden coupling while keeping the current public API and CLI recognizable.

| Improvement | Why it helps | Scope and acceptance |
| --- | --- | --- |
| Shared transaction module | `codecs.py`, markup, and nested helpers reach back into `repack.py` through dynamic `_r() -> Any` imports | Move staging, subprocess execution, verification, acceptance, and publishing behind typed internal interfaces; preserve public imports; one tested publish path |
| Shared operation context | Resource/cancellation/destination policy is otherwise duplicated or lost during recursion | Carry immutable options plus bounded operation state into every nested packer; verify cumulative budgets |
| Typed format/capability registry | Routing is split among extension lists, aliases, `_PACKERS`, family tables, validators, tool specs, and docs | Start with consistency tests; then describe aliases, tools/extras, output family, fidelity, and validator in one source that generates diagnostic/docs tables |
| Explicit outcome models | `Optional[PackResult]` and arbitrary dictionaries erase why work did not happen | Add typed outcomes and typed worker requests; adapt legacy mapping/API at the boundary; no internal `None`-as-everything contract |
| Codec modules by family | `repack.py` is 1,757 lines and `codecs.py` 1,017 lines, with broad exception swallowing | Split along proven archive/image/media/data boundaries after shared helpers move; keep compatibility re-exports; log structured failures |
| Gradual typing | Passing mypy currently permits numerous `Any` paths and relaxes return checking in `codecs.py` | Tighten shared-core and worker interfaces first; add return annotations; remove the `warn_return_any = false` exception as coupling is reduced |

Avoid a plugin loader, new web service, task database, or extensive class hierarchy unless a measured use case requires one. Fixing the registry and internal contracts is sufficient for the current application.

## 6. Updates to existing features

| Existing feature | Proposed update | Completion criterion |
| --- | --- | --- |
| Archive/Office repacking | Correct layer handling, manifest preservation, specialized container policies, signature gates | Real ZIP/tar/OOXML/ODF/EPUB fixtures preserve members and application structure |
| XML/JSON minification | Conservative lexical transformations with exact text/numeric preservation | Regression cases in R03/R06 pass and unsupported cases skip safely |
| PDF optimization | Whole-file protection policy; choose smallest valid original/qpdf/walk candidate; tune linearization separately from compression | Signed/encrypted behavior is explicit; no larger intermediate hides a better candidate; page/content structure retained |
| Images/media | Explicit fidelity and metadata policies; frame/stream-aware adapters; independent image/audio/video category controls | `--no-images` remains compatible while new category controls work independently; nested assets inherit policy |
| Data files | Preserve schema/metadata/framing; process batches where supported; define SQLite snapshot behavior | Logical and metadata comparisons pass; peak memory scales with the processing batch |
| Bulk processing | Bounded scheduling, source/output exclusion, cancellation and conflict management | Large scans keep bounded memory and produce complete reconciled reports |
| Backups/output directories | Central destination policy, verified staged publication, collision-safe backups | Source and existing outputs remain recoverable through failure/interrupt cases |
| `doctor` and config | Executable/version probes, extras visibility, per-format read/write capability, tested config fallback | A configured but unusable tool or unwritable format is reported accurately |
| Progress/reporting | Stable status/reason schema, durable member paths, stderr diagnostics, all outcomes | JSON/CSV parse cleanly and counters include failure/skip/unchanged/predicted cases |

For embedded assets, option propagation also needs attention: XML/PDF helpers construct their own `pack_images=True` options, audio entries do not consistently forward all quality/ultra flags to covers, and SVGZ does not forward the full parent policy. Add propagation tests so selective controls, metadata, and quality settings retain their intended scope.

## 7. New feature roadmap

These extend existing capabilities instead of duplicating `--dryrun`, `doctor`, `--ultra`, or parallel jobs. Proposed command/flag names are design suggestions, not implemented interfaces.

| ID / priority | New capability | User value and proposed interface | Dependencies / effort | Acceptance criteria |
| --- | --- | --- | --- | --- |
| N01 / P1 | Fast inspection and planning | `filerepack inspect PATH --json` reports detected formats, tools/extras, protection gates, destination conflicts, estimated resource needs, and planned operations **without doing a full encode**. Current dry-run remains an exact candidate measurement | Outcomes, capability registry, resource policy; M | No source mutation or compression pass; identify known signatures/unsupported formats; distinguish estimates from measured savings |
| N02 / P2 | Persistent audit reports | `--report FILE` and streaming JSONL record every outcome, nested member identity, source/destination, selected tool/version, settings, validation result, and timing | Outcome schema and bounded bulk runner; M | Versioned schema; parseable under progress/errors; includes partial/aborted jobs; bounded report memory; source paths have an explicit privacy policy |
| N03 / P2 | Resumable batch jobs | `--manifest FILE --resume` avoids repeating completed work after interruption; resume checks source identity, options, and tool changes | Reports, conflict handling, bounded runner; L | Changed source/options/toolchain invalidates a cached outcome; completed work is not repeated; manifest publication is atomic; no stale-success reuse |
| N04 / P2 | Named optimization profiles and budgets | `--profile fast|balanced|maximum|preserve` makes existing scattered effort/quality settings reproducible; per-file timeout, temp-space, and worker/tool-thread budgets prevent one costly input dominating a job | Registry, resource context, preservation policy; M/L | CLI overrides profile deterministically; lossy behavior stays explicit; profiles carry a reproducible version; benchmark time/savings tradeoffs on the same corpus |
| N05 / P2 | Archive-member selection | `--exclude-member PATTERN`, nested depth controls, and category selectors allow users to target images/documents/data or avoid expensive subtrees | Manifest-preserving writers and shared operation context; M | Excluded payload bytes remain unchanged; archive structure still validates; path normalization is tested; decision reasons appear in reports |
| N06 / P3 | Deeper lossless PDF image optimization | Extend the existing DCT/JPX walker to eligible Flate/PNG-like images and images referenced through nested forms; avoid repeated work on shared streams | PDF fixtures, protection gates, format validators; L | Decoded pixels/masks/color spaces retained; shared objects handled once; unsupported filters skip explicitly; real page-render comparisons pass |

Effort notation: **S** = approximately 1–2 engineering days; **M** = 3–5 days; **L** = 1–2 weeks. These are planning ranges for one contributor, including tests and documentation, not delivery commitments. Format fidelity and platform validation can increase them.

After those features, consider additional format support only when there is a concrete corpus and a reliable writer. Prioritize gaps in existing promises—CAB capability honesty, protected packages, animation/color retention, and data metadata—over another large alias expansion. A GUI, hosted API, watch daemon, and arbitrary third-party plugin system should wait for demonstrated demand.

## 8. Delivery plan and dependencies

### Milestone A — preservation fixes; next maintenance release

Deliver small, independently reviewable changes. Each fix should first reproduce the defect on the old implementation and then pass against the corrected path.

- [ ] **A1 (M):** preserve complete archive member sets and safe argument handling; R01.
- [ ] **A2 (M):** implement explicit compressed-tar stages and validate member layout; R02.
- [ ] **A3 (M):** preserve XML text and JSON lexical values; R03/R06.
- [ ] **A4 (M):** validate before writes, protect existing destinations, and implement standalone `outfile`; R04/R07.
- [ ] **A5 (M):** repair full/nested DICOM signature inspection; add correct tag-order fixtures; R05.
- [ ] **A6 (M):** preserve Parquet metadata and ODF package constraints; add focused real-format fixtures; R06/R14.
- [ ] **A7 (S):** repair source-distribution contents and add an artifact collection check; R15.

**Release gate:** all confirmed content-changing/overwrite reproductions are covered; protected inputs and destination collisions cannot publish an unsafe candidate. Tests, lint, typing, documentation, and artifact checks pass. Do not advertise unsupported aliases as fully validated.

### Milestone B — trustworthy execution and observable outcomes

- [ ] **B1 (L):** extract the transaction/subprocess core; stage publication on the destination filesystem, preserve filesystem policy, and check concurrent source changes; R10.
- [ ] **B2 (L):** add validators and whole-file/package protection policies; R09/R14. Build on A1/A2's manifests.
- [ ] **B3 (M):** add explicit typed outcomes, clean stdout, reason codes, timing, and complete summary accounting; R11. Preserve legacy mapping access.
- [ ] **B4 (L):** bound submissions, handle cancellation, exclude outputs/backups, and reserve destinations; R12. Requires A4 and B3.
- [ ] **B5 (L):** enforce cumulative extraction/decode/scratch/depth/deadline budgets; R13. Requires B1 and operation-context propagation.
- [ ] **B6 (L):** define video default migration and preserve media streams/frames; R08. Use an approved capability proposal for behavior changes.

**Completion gate:** failed work is visibly failed; reports reconcile with all inputs; every publishable candidate is structurally validated; resource limits apply inside nested and standalone operations; interrupted work leaves usable originals and partial outcomes.

### Milestone C — sustainable implementation and compatibility

- [ ] **C1 (M):** unify registry metadata and add executable/version/capability diagnostics; correct CAB advertising and old-Python TOML handling; R14/R15.
- [ ] **C2 (L):** add extras, macOS/Windows, and installed-artifact test lanes; retain the core Python compatibility matrix.
- [ ] **C3 (M):** add preservation/property/fault-injection fixtures, explicit integration skips, and meaningful changed-path coverage gates.
- [ ] **C4 (M/L):** stream data operations where supported, document SQLite offline/snapshot policy, and validate schema/metadata preservation.
- [ ] **C5 (M):** split proven codec families, tighten core typing, repair logging/options propagation, and generate capability/docs tables.
- [ ] **C6 (S/M):** update `openspec/project.md`, reconcile completed changes into current specs after confirming deployment status, and link this report as the current roadmap.

**Completion gate:** documented format/platform claims have a corresponding fixture or explicit limitation; support matrices derive from tested capabilities; source and wheel installations behave consistently.

### Milestone D — user-facing growth

- [ ] Ship **N01 inspection** after capability/outcome work.
- [ ] Ship **N02 audit reports**, then **N03 resume** after batch lifecycle work.
- [ ] Ship **N04 profiles/budgets** after preservation and benchmark contracts.
- [ ] Ship **N05 member selection** after archive manifests and context propagation.
- [ ] Ship **N06 PDF stream expansion** after real PDF validation/protection coverage.

Measure adoption and corpus results before selecting further formats or services. Avoid committing to a release date until the preservation fixture workload is established.

## 9. Validation strategy and success measures

Use preservation-oriented tests rather than tests that merely confirm a command flag or non-`None` return.

| Layer | Required verification |
| --- | --- |
| Transaction | Failure before/after encode, validation rejection, replacement failure, existing destination, permissions, source changes, scratch cleanup, dry-run zero source mutation |
| Archives/packages | Intended member manifest; decoded hashes for unchanged members; links/empty directories; hidden/Unicode/option-like paths; tar layering; ODF/EPUB ordering; signature/manifest policy |
| Markup | Exact string/text tokens, inherited XML preservation, CDATA/mixed content, exact JSON numbers/member order, invalid/unsupported inputs |
| Images/media | Dimensions, bit depth, transparency, animation/frame count; decoded equality in lossless modes; complete streams/chapters/dispositions/tags; requested lossy settings |
| PDF/DICOM | Protection gates; page/frame counts; valid parse; image/pixel equality where applicable; metadata/attributes; realistic signature placement |
| Data/fonts | Rows and values, schema/nullability/nested types, metadata, IPC framing; SQLite sidecar/concurrency behavior; font tables and usable decode |
| CLI/bulk | Parse stdout as JSON/CSV without quiet; status/exit-code matrix; bounded scheduling; abort/interrupt reports; exclusions/conflicts; serial vs parallel results |
| Distribution/platform | Build/install wheel; collect/run included sdist tests; minimum/core and optional extras; Python 3.9–3.13 plus a deliberate future-version policy; Windows/macOS/Linux filesystem/process behavior |

Suggested success measures:

- **Zero accepted candidates with missing members, unintended text/value changes, protected signatures, or unrelated destination overwrites** in the preservation corpus.
- **100% of advertised writers** have a round-trip fixture or are explicitly labeled unavailable/experimental for that tool/platform.
- **100% of batch inputs** reconcile to a terminal outcome, including unchanged, skipped, failed, and interrupted work.
- Ratchet overall coverage from the measured **62% toward 75%**, with a higher bar for changed transaction/validation code. Coverage is secondary to preservation assertions; do not inflate it with mocks that accept invalid output.
- Record elapsed time, peak memory, maximum scratch use, bytes saved, and tool versions on a fixed representative corpus. Establish the baseline first; select performance targets from measurements rather than inventing compression gains.
- Include both already optimized and poorly compressed inputs. Report inner candidate savings separately from the final container savings and publish acceptance rate as well as total bytes saved.

## 10. OpenSpec implementation workflow

The plan is mapped to [22 OpenSpec changes](../../openspec/ROADMAP.md), with priorities, dependencies, requirement scenarios, and complete finding/milestone/feature traceability. This report records the reviewed pre-implementation behavior; the linked roadmap and each change's tasks track subsequent implementation. Archive preservation, compressed-tar, markup preservation, output-destination and DICOM safety fixes are now implemented and verified locally.

The repository's OpenSpec guidance applies to follow-up implementation:

1. Check existing requirements and active changes before each slice. Current canonical specs are absent, so reconcile the implemented baseline first where necessary.
2. Bug fixes restoring existing intended behavior can proceed through focused fixes/tests under the repository's documented exception. Use proposals for new capabilities, changed defaults, architecture, and significant security/performance behavior.
3. Suggested proposal IDs include `refactor-repack-transactions`, `update-repack-outcomes`, `add-operation-resource-budgets`, `update-media-preservation-policy`, `add-inspection-command`, `add-audit-reports`, and `add-resumable-bulk`. Confirm uniqueness when creating them.
4. Each proposal should include rationale, affected code/capabilities, tasks, design when needed, requirement deltas, and at least one scenario per requirement. Preserve public CLI/API compatibility or supply explicit migration notes.
5. Run `openspec validate <change-id> --strict`; review and approve the capability proposal before implementation. Archive completed work only after deployment status is confirmed and canonical specs are updated.

The earlier `dev/docs/improvement_report.md` remains useful history. Do not reopen its completed recommendations as new work: shell-safe execution, basic atomic replacement, lossless JPEG/PNG/PDF defaults, dataclasses, jobs, doctor/config, directory exclusions, progress, and additional formats already exist. The next work should address the concrete gaps documented here.

## 11. Minimal reproduction recipes for the first fixes

These examples use temporary files. The archive examples require a runnable `7zz` or `7z`. They describe the reviewed behavior and should become focused regression tests during implementation.

### Root dotfile and tar layer preservation

```python
import gzip
import io
import tarfile
import tempfile
import zipfile
from pathlib import Path
from filerepack import FileRepacker, RepackOptions

with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    path = root / 'example.zip'
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('.hidden', 'important')
        zf.writestr('visible.txt', 'A' * 10000)
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=False))
    with zipfile.ZipFile(path) as zf:
        assert '.hidden' in zf.namelist()  # Fails on reviewed implementation.

with tempfile.TemporaryDirectory() as scratch:
    path = Path(scratch) / 'bundle.tar.gz'
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        payload = b'hello' * 1000
        info = tarfile.TarInfo('document.txt')
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    path.write_bytes(gzip.compress(buf.getvalue(), compresslevel=0))
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=False))
    with tarfile.open(path, 'r:gz') as tf:
        assert tf.getnames() == ['document.txt']  # Gets ['bundle.tar'] today.
```

### Preserved XML text

```python
from xml.etree import ElementTree as ET
from filerepack.markup import minify_xml_bytes

for source in (
    b'<r xml:space="preserve">\n  <a/>\n  <b/>\n</r>',
    b'<r><![CDATA[hello>\n<world]]></r>',
):
    candidate = minify_xml_bytes(source)
    assert candidate is not None
    assert list(ET.fromstring(candidate).itertext()) == list(
        ET.fromstring(source).itertext()
    )  # Fails for both inputs today.
```

### Signature after DICOM Pixel Data

```python
import tempfile
from pathlib import Path
from filerepack.dicom import dicom_is_packable
from test.dicom_fixtures import build_dicom, expl_empty_sq

with tempfile.TemporaryDirectory() as scratch:
    path = Path(scratch) / 'signature-gate.dcm'
    path.write_bytes(build_dicom() + expl_empty_sq(0xFFFA, 0xFFFA))
    assert not dicom_is_packable(str(path))  # Returns True today.
```

The DICOM recipe tests detection of the signature-sequence tag. It does not construct or verify a cryptographic signature. Conversion collision and cross-device checks should remain clearly labeled fault-injection tests until complemented by platform/media integration fixtures.
