# OLE writer qualification

The production path is `filerepack/ole.py`, `filerepack/ole_ppt.py`, `filerepack/ole_protection.py`,
`filerepack/ole_verify.py` and the
optional Rust helper in `tools/ole-compactor`. This directory contains a
comparison-only OpenMcdf program and reproducible pilot measurements.

Current evidence is in [PORTFOLIO.md](PORTFOLIO.md) and the
[1,055-file original corpus census](CORPUS.md). The census inventories accepted and
rejected profiles with pinned source hashes; its stage counts do not predict
physical savings. Earlier measurements below document individual implementation
stages.

```sh
python -m pip install -e '.[dev,ole]'
cargo build --release --locked --manifest-path tools/ole-compactor/Cargo.toml
dotnet build dev/ole/openmcdf/Compare.csproj -c Release -p:RestoreLockedMode=true
PYTHONPATH=. python dev/ole/qualify.py \
  --writer "$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  --dotnet dotnet \
  --openmcdf-dll "$PWD/dev/ole/openmcdf/bin/Release/net8.0/Compare.dll" \
  --soffice soffice --pdftoppm pdftoppm --ppt-uncompressed \
  --output dev/ole/qualification-ppt-vba.json
```

On Windows the native executable has an `.exe` suffix. Renderer and .NET
arguments are optional. Use a pinned renderer/font environment for before/after
comparison. Each export gets a private LibreOffice profile with macro security
level 3. Headless export success and equal page pixels supplement stream/metadata
checks; interactive Microsoft Office repair prompts have not been tested.

The real corpus is `test/fixtures/ole`, with Apache POI commit, URLs, SHA-256,
sizes, Apache-2.0 LICENSE and NOTICE retained. It includes protected/VBA files and
structural variants intentionally skipped. Controlled variants reuse the real
application streams and add 80 free regular sectors, mini-stream holes and an
empty storage with nontrivial CLSID/state/FILETIMEs. These synthetic variants
measure reclaimable space, not a representative compression ratio.

Pinned comparison: OpenMcdf 3.3.0 (MPL-2.0), .NET SDK 8.0.425; production:
cfb 0.14.0 (MIT), Rust 1.93.1, olefile 0.47 (BSD). The locked Rust graph requires
Rust 1.89+ because of UUID. See `tools/ole-compactor/THIRD_PARTY_LICENSES.md`.
No OpenMcdf DLL or .NET runtime is distributed with the production adapter.

The initial macOS arm64 pilot (`qualification.json`) produced 18/18 Rust candidates with equal complete
manifests. Nine real originals rendered identically before/after with
LibreOfficeDev 26.8.0.0.alpha0 commit 2c87e51eeaa2b413ff4ae097b2705eea1995d8e5
and Poppler 26.05.0 at 96 DPI. It covers PNG, OLE embedding, formulas and a chart.
Seven originals saved zero bytes; SampleShow.ppt saved 512 bytes and
ole2-embedding-2003.ppt saved 2,560 bytes. Controlled variants saved
40,960–48,640 bytes. Timings are individual wall-clock runs including process
startup, excluding Python verification/rendering; peak memory was not measured.

The continued pilot (`qualification-vba.json`) uses the expanded 21-file corpus:
13 eligible originals and eight skips. Its 26/26 native manifests and 13/13
before/after render pairs are equal in the same pinned renderer environment.
It includes three actual canonical unsigned VBA projects: SimpleMacro.doc,
SimpleMacro.xls and external_name.xls. All their project streams remain identical;
rendering uses macro security level 3. HeaderWithMacros.doc is also eligible but
has no VBA project storage. That pilot skipped SquareMacro.xls because of its
nonzero root creation time; the 2026-10-08 compatibility fix below qualifies it.
The four newly eligible originals save zero bytes;
the controlled variants save 40,960–48,640 bytes. The report records fixture
hashes and unsigned-project presence in addition to measured candidate sizes.

Unsigned DOC/XLS projects are permitted only with complete host-signature checks:
DOC StwUser `Sign`/`SigAgile`/`SigV3` and DocumentSummaryInformation property
`GKPIDDSI_DIGSIG`. These checks bound the complete index/name table; property values
and VBA internals remain opaque. Controlled regressions insert signature markers
at those locations and assert the writer is never reached. They test signature
presence, not cryptographic validity. At that stage PPT, embedded, incomplete and
unknown VBA layouts still skipped; encryption, document signatures and rights
management remain unsupported.

The comparison-only OpenMcdf `Flush(consolidate: true)` invocation changed
root/storage metadata (CLSID, state bits, creation/modification times), and its
embedded-DOC candidate failed olefile's strict empty-stream check. Its output is
therefore rejected for this contract. This result qualifies that invocation,
not every possible OpenMcdf reconstruction implementation.

Run native regression tests with the writer on PATH or an explicit absolute
`FILEREPACK_OLE_COMPACTOR` path:

```sh
FILEREPACK_OLE_COMPACTOR="$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  pytest -q test/test_ole.py test/test_ole_protection.py test/test_ole_ppt.py
```

The suite covers FAT/MiniFAT cycles/overlaps, orphans and invalid directory
references/names, extended DIFAT, mini-stream threshold edges, unknown and empty
objects, exact metadata, protection, resource bounds, reader disagreement,
incomplete reads, source/candidate preservation, dry-run/size rejection,
interrupt cleanup, nested archives, distinct output/backup and filesystem metadata.
Linux/macOS/Windows Python 3.9/3.13 native jobs are configured; local execution and
application qualification are macOS only. Wider platform/application results
must be recorded after those jobs run.

At the DOC/XLS-stage check, repository-wide Ruff reported three long lines in
`__main__.py` (checkpoint options) and `dispatch.py` (experimental format budgets).
Mypy reported eight errors in `verification.py` (Pillow-specific attributes),
`mat.py` and `hierarchical.py`. Focused OLE Ruff/Mypy checks pass. These unrelated
shared-working-tree changes are not rewritten by this feature.

Initial-stage local checks: 73 OLE tests passed; the full source and
installed-sdist suites each had 1,288 passed / 108 skipped. Installed-wheel
compatibility/validation/OLE tests had 488 passed / 22 skipped. Isolated wheel/
sdist validation, documentation build, strict OpenSpec validation, focused OLE
Ruff/Mypy, Cargo fmt and Clippy passed. Repository-wide static failures are
reported above and remain outside the OLE implementation.

Continued-stage local checks: 120 native OLE tests passed, including unsigned
DOC/DOT and XLS/XLT/XLA projects, host-signature rejection and malformed indices.
The full source and installed-sdist suites each passed 1,342 tests / 109 skipped;
the installed-wheel subset passed 542 / 22 skipped. Both isolated artifact
installations passed runtime/CLI/dry-run checks; source writer/lock/license
inclusion passed. Documentation build, strict OpenSpec validation and focused
OLE Ruff/Mypy passed. Repository-wide static failures are listed above.

The PPT stage (`qualification-ppt-vba.json`) qualifies SimpleMacro.ppt and its
PPT/POT/PPS aliases. The 21-file corpus now contains 14 eligible originals and
seven skips, including four actual unsigned VBA projects across DOC/XLS/PPT.
Its 29/29 native candidates retain complete manifests: 14 originals, 14 controlled
hole variants, and one fixture-derived uncompressed PPT project wrapper.
All 15 renderer pairs are equal with macro security level 3; the uncompressed
variant's pages also match the original compressed presentation. SimpleMacro.ppt
itself saves zero bytes; its hole variant saves 41,984 bytes. Other original
savings and the overall controlled-hole range remain unchanged.

PPT qualification accepts one user edit, one canonical VBAInfoContainer below
the current document's DocInfoList, recognized project flags and an unambiguous
persist reference to a preceding top-level project storage. Duplicate IDs within
an index, child-record targets, multiple edits with VBA, empty/unknown project
variants and unknown/embedded layouts skip. The compressed/uncompressed nested
project is inspected with the independent CFB reader; encoded and decoded storage
bytes are bounded to 16 MiB. Declared size, zlib checksum/termination and absence
of trailing or concatenated data are checked. Decoding inspects the container;
VBA code remains opaque and every original encoded application record is retained.
Macro-free PPT edit-history handling remains supported. The fixture-specific
uncompressed-wrapper relocation helper is development/test code only.

PPT-stage local checks: 161 native OLE tests passed. Full source and installed-sdist
suites each passed 1,383 tests / 109 skipped; the installed-wheel subset passed
583 / 22 skipped. Isolated wheel/sdist runtime/CLI/dry-run/source checks, documentation
build, strict OpenSpec validation, focused OLE Ruff/Mypy and repository-wide Ruff
passed. Repository-wide Mypy currently reports four unrelated operand-type
errors in `mat.py`; the new PPT module passes its focused type check. Wider
platform/application and peak-memory qualifications remain outside local evidence.

## PPT compressed-record feasibility (development only)

`ppt_record_pilot.py` compares record-level recompression on the checksum-pinned
`ole2-embedding-2003.ppt` fixture and two encoding-only derivatives. It is restricted
to that fixture's exact surrounding bytes, object identities and edit/persist
layout. It does not publish files or add runtime support. The separate proposal
is `openspec/changes/add-ppt-ole-record-recompression`; it was approved on
2026-10-04 and implemented in the separate runtime modules described below.
Ordinary `ole` verification still requires every stream byte unchanged.

Reproduce with Python 3.10+ and the existing qualification environment:

```sh
python -m pip install 'zopfli==0.4.3'
PYTHONPATH=. python dev/ole/ppt_record_pilot.py \
  --writer "$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  --soffice soffice --pdftoppm pdftoppm \
  --output dev/ole/qualification-ppt-records.json
PYTHONPATH=. pytest -q dev/ole/test_ppt_record_pilot.py
```

The real input is 40,448 bytes, ordinary compaction 37,888, and the Zopfli
candidate 37,376. zlib level 9 reduces the application stream by 100 bytes but
saves no additional sector; Zopfli's 521-byte stream reduction saves another
512 file bytes. Both decoded storages (40,448-byte DOC and 13,824-byte XLS) stay
byte-identical. The controlled level-1/level-0 wrappers save 1,024/50,176 extra
file bytes with Zopfli; these are deliberately different encodings of the same
objects and are not representative real-world savings.

All six record candidates retain fixture-specific intended content, references,
unaffected streams and full directory metadata, and render equal page pixels in
the pinned LibreOffice/Poppler environment with macro security level 3. Each
candidate also passes both strict CFB readers; the native writer preserves the
staged manifest exactly. Their source/candidate strict `ole` stream manifests
differ as expected, so a new, explicit preservation contract is necessary.
The original fixture is checksum-verified before and after the experiment.

Development fault tests cover stale persist/edit references, modified decoded
objects, wrappers, checksums, extra/trailing zlib data, records, streams and root
metadata. The experimental fixture allocator remains test/development-only.
At the research stage, general record/extension eligibility, native stream
replacement, bounded encoder workers and CLI propagation were deferred to the
proposal. The implementation below supplies those runtime capabilities;
interactive Microsoft Office qualification remains unmeasured.

Research-stage local checks: 18 development tests and 161 existing native OLE
tests passed (179 combined), focused pilot Ruff/Mypy passed, and strict OpenSpec
validation passed for both the new proposal and existing compaction change.
No production module, dependency, CLI or native-helper behavior changed at this stage.

## Approved PPT runtime implementation

The production modules `filerepack/ole_ppt_records.py` and
`filerepack/ole_recompress.py` implement a general, bounded single-edit gate,
relocation and the separate `ppt-ole` verifier. They do not import the pilot or
fixture allocator. The Rust helper 0.2.0 replaces only two explicitly named root
streams. `--ole-recompress` is off by default and propagates through CLI, bulk
workers and archive members. DOC/XLS use the unchanged compaction contract.

Install `.[dev,ole-recompress]`, rebuild the helper and run:

```sh
PYTHONPATH=. python dev/ole/qualify.py \
  --writer "$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  --soffice soffice --pdftoppm pdftoppm --ppt-uncompressed --ppt-recompress \
  --output dev/ole/qualification-ppt-runtime.json
FILEREPACK_OLE_COMPACTOR="$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  pytest -q test/test_ole.py test/test_ole_protection.py test/test_ole_ppt.py \
  test/test_ole_recompress.py
```

The expanded pinned corpus contains 23 real files: 15 ordinary-compaction
profiles and eight skips. It includes two more real embedding presentations:
`testPPT_oleWorkbook.ppt` compacts by 512 bytes but falls back for record type
1058; `ppt_with_embeded.ppt` is rejected for unknown VBA flags. This expands
negative/profile evidence; only `ole2-embedding-2003.ppt` qualifies for the initial
record rewrite. The record allowlist and extension boundary are documented in
the change's `design.md` and enforced by parser faults.

`qualification-ppt-runtime.json` contains 33/33 equal native compaction manifests,
18/18 equal renderer pairs and 11/11 successful public-API PPT intent checks.
Four runtime cases apply record recompression: the real embedding original,
its controlled holes and two encoding-only controls. The remaining seven use
strictly verified compaction. The real original yields 40,448 → 37,376 bytes,
including 512 bytes beyond its 37,888-byte compaction baseline. The controlled
level-1/level-0 wrappers add 1,024/50,176 bytes of opportunity. All decoded
embedded bytes stay identical. Changed representations intentionally fail strict
`ole` stream equality and pass `ppt-ole` intended-change equality.

The report records transformation-worker RSS (including native descendants),
charged decoded bytes, writes, nodes and elapsed time. It does not measure the
whole pipeline's peak memory. Qualification used macOS arm64 Python 3.13.7,
olefile 0.47, Zopfli 0.4.3 and the same pinned LibreOffice/Poppler environment.
Linux/macOS/Windows Python 3.9/3.13 native CI includes these tests; those remote
jobs and interactive Microsoft Office behavior have not been executed locally.

Runtime-stage checks: 57 new preservation/worker/transaction regressions passed,
plus 161 existing OLE and 18 development-pilot tests. The final installed-sdist
suite passed 1,478 / 156 skipped and the installed-wheel subset 641 / 22 skipped.
Fresh artifact provenance, CLI/exports, native-source/fixture inclusion and license
checks passed. Repository-wide Ruff, focused Mypy (`--follow-imports=silent`, eight
OLE/worker modules), Rust fmt/release/Clippy, documentation build and strict
OpenSpec checks passed. Full Mypy still reports four pre-existing operand errors
in `mat.py`. A transient PyPI DNS failure in the first artifact attempt was
resolved by a successful repeat; both final isolated installations passed.

## Shared OfficeArt feasibility (historical pre-approval stage)

`officeart_pilot.py` implements one bounded EMF/WMF record codec and three
checksum-bound host experiments. DOC rebuilds PICFs and actual picture references;
XLS rebuilds MsoDrawingGroup/CONTINUE and repairs BoundSheet and Index `ibXF`;
PPT rebuilds Pictures and repairs FBSE sizes/delay offsets. It preserves every
decoded metafile byte, UID, geometry, surrounding record, unselected JPEG/PNG,
embedded storage and CFB logical metadata. It retains original wrappers when an
encoder does not improve them; only explicit controlled variants may grow.

Run with the existing development extras, qualified optional Zopfli 0.4.3 and
native helper 0.2.0 (nothing is published or written back to source fixtures):

```sh
PYTHONPATH=. python dev/ole/officeart_pilot.py \
  --writer "$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  --soffice soffice --pdftoppm pdftoppm \
  --output dev/ole/qualification-officeart.json
pytest -q dev/ole/test_officeart_pilot.py
```

The report contains four real originals, two encoding-only controls per original
and two encoder trials per input: 24/24 intended-content and renderer comparisons
pass. Every native compaction retains the complete staged manifest and both CFB
readers agree. Macro security is level 3 in a private LibreOffice profile; the
exact renderer/platform versions are in the report. Peak RSS, generalized host
discovery, Microsoft Office repair prompts and other platforms are unmeasured.
The current corpus has 25 real files / 17 compaction profiles / eight skips;
historical reports retain their earlier corpus coverage.

| Real input | Ordinary compaction | OfficeArt with Zopfli | Additional physical savings |
| --- | ---: | ---: | ---: |
| vector_image.doc, 24,064 bytes | 24,064 | 24,064 | 0 |
| word_with_embeded.doc, 117,248 bytes | 117,248 | 116,224 | 1,024 |
| SimpleWithImages.xls, 48,128 bytes | 48,128 | 47,104 | 1,024 |
| ole2-embedding-2003.ppt, 40,448 bytes | 37,888 | 37,888 | 0 |

The first DOC and PPT still save 74/149 stream bytes but no additional file
allocation. zlib 9 alone saves 1,024 physical bytes on the embedded DOC. Controlled
zlib 0/1 trials demonstrate opportunity and are not expected real-world ratios.
`selected_bytes`, `selected_verifier` and `selection_reason` distinguish a
smaller OfficeArt file from a strictly verified baseline that should be retained.
Changed representations fail strict `ole` byte equality as intended.

This is **development-only**, not a generalized parser or production packer.
Fixture checksum gates establish the audited host layouts; fixed CPicLocation
positions, BIFF pointer families and PPT FBSE positions cannot be used as runtime
discovery. No runtime module, CLI, dependency or native interface changed here.
The test allocator must remain outside runtime code. General adapters, complete
host reference accounting, a bounded root-stream replacement interface, isolated
encoding and an independent intended-change verifier are specified in
`openspec/changes/add-officeart-payload-recompression/` and were subsequently approved under
`openspec/AGENTS.md`. PNG/JPEG recompression follows its own metadata/UID
qualification; mixed-store raster bytes are copied exactly in the first stage.

Local feasibility checks: 108 new development tests passed; the combined
OfficeArt/prior-pilot/native OLE suite passed 358 tests. Focused Ruff/Mypy and
strict validation of the new and two existing OLE changes passed. Fault checks
include valid zlib with altered metafile bytes, valid BIFF pointers to a wrong
sheet, stale Index pointers, UID/geometry changes, extra/trailing wrappers,
encoder failures and directory/unrelated-stream changes. Every source checksum
was rechecked after rendering. No fresh production artifact/platform qualification
is claimed for this development-only stage.


## Shared OfficeArt runtime

The approved initial EMF/WMF stage now uses generic FIB/piece/style/FKP Word
reference discovery, audited BIFF8 drawing-group and pointer relocation, and PPT
live drawing-group/Pictures discovery. Production has no checksum/fixture offset
gate and imports neither this development directory nor the test allocator.
Its supported subset and preservation contract are documented in the Office guide.
PNG/JPEG remain exact and require separate later qualification before rewriting.

Native helper 0.3.0 supplies three bounded fixed root-stream modes. The isolated
public API compares strict compaction and separately verified payload candidates;
existing PPT storage encoding stays available. Runtime reproduction:

```sh
PYTHONPATH=. python dev/ole/qualify_officeart.py \
  --writer "$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  --soffice soffice --pdftoppm pdftoppm \
  --output dev/ole/qualification-officeart-runtime.json
FILEREPACK_OLE_COMPACTOR="$PWD/tools/ole-compactor/target/release/filerepack-ole" \
  pytest -q test/test_ole_officeart.py
```

The report uses four real originals and two encoding-only controls for each.
Both CFB readers and selected intended-change verifiers agree, decoded metafiles
and rendered RGB page hashes match, and corpus checksums stay unchanged. Actual
worker usage is recorded separately from application renderer use. Local evidence
covers macOS arm64; Linux/macOS/Windows native CI jobs include this runtime suite.
CI configuration does not establish a locally observed result on remote platforms.


Delivery checks for the initial runtime stage: 125 new production tests pass with
Zopfli and with zlib-only dependencies; full source 1,618 passed / 156 skipped,
fresh wheel 781 passed / 22 skipped and fresh sdist 1,618 passed / 156 skipped.
Ruff, focused ten-module Mypy, native fmt/release/Clippy, docs and strict relevant
OpenSpec checks pass. Full Mypy still reports the four existing `mat.py` operand
errors. Native platform jobs are configured; remote results remain unmeasured.

A project-local `venv` was installed with current editable runtime/recompression
extras and native helper 0.3.0. `source venv/bin/activate` selects both updated
commands; the system `filerepack` detected during delivery was an older install
without the new option. The activated CLI dry-run confirms embedded DOC
117,248 → 116,224 and prints payload/encoder/stream/file savings diagnostics.

## Approved portfolio implementation

See [PORTFOLIO.md](PORTFOLIO.md), [qualification JSON](qualification-portfolio.json)
and `qualify_portfolio.py` for the seven new bounded profiles, licensed fixtures,
physical size/RSS/timing evidence and explicit application/platform limits.

## PPT directory-name compatibility, 2026-10-08

The session “Ошибка сжатия PPT файлов” diagnosed a slot-zero root name encoded
as UTF-16 `R`, zero padding and declared length 2, followed by a `ß`-containing
MsoDataStore name rejected by Python's full uppercase expansion. The initial
unused-directory-slot hypothesis was not the cause: these slots were already
handled by the runtime reader.

The runtime now qualifies exactly that root-name anomaly in private strict,
independent and native reader views. Application names and every other directory
field remain exact. CFB comparison uses a generated, pinned Unicode 16.0.0 BMP
simple-uppercase table; no full expansions or Unicode normalization are applied.
The native dependency already handles BMP simple-uppercase exceptions.
Supplementary names remain outside that backend's qualified profile.
The PPT pipeline reuses its verified source instead of retaining two full parses,
allowing the 25,570,304-byte mapping presentation to complete within the default
256 MiB worker limit.

`qualification-ppt-name-compatibility.json` records four local inputs, including
the previously normalized copy, native candidate sizes, complete independent
manifest equality, public compaction/recompression results and unchanged sources.
All candidates have equal size, so normal publication correctly retains the
originals. At that compatibility stage, record type/version 1008 remained outside
the qualified content profile; those results did not assert new PPT-record support,
renderer equivalence or Microsoft Office qualification.

The table matches all 65,536 UTF-16 units against the versioned UnicodeData source.
Its source SHA-256 and Unicode license are included in the generated module;
`generate_cfb_upper_table.py` regenerates it from local pinned source/license files.
New regression coverage includes Greek simple-uppercase exceptions, duplicate
keys, root-field corruption, unchanged dry-runs, native compaction, embedded
processing and actual record recompression across PPT/POT/PPS aliases.

References: [CFB name comparison](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/d30e462c-5f8a-435b-9c4c-cc0b9ea89956),
[directory fields](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/60fe8611-66c3-496b-b70d-a504c94c9ace),
[Unicode 16.0.0 source](https://www.unicode.org/Public/16.0.0/ucd/UnicodeData.txt).

## PPT notes and Pictures feasibility, 2026-10-08

`analyze_ppt_notes.py` is a read-only development study of the three supplied
presentations and the normalized mapping duplicate. It records notes/slide/master
links, the old notes-master field variant, unqualified record types and binary
tags, immutable Photoshop storage payloads, shared FBSE entries and exact PNG
zlib9 trials. It never writes a PPT candidate or changes runtime qualification.

```sh
venv/bin/python -m dev.ole.analyze_ppt_notes \
  temp/_raw/crimemapping_v2.ppt temp/_raw/mapping_rus_v1.ppt \
  temp/_raw/ruslocal_v1.ppt temp/_raw/mapping_rus_v1.root-normalized.ppt \
  --output dev/ole/qualification-ppt-notes-analysis.json
```

See [measured evidence](qualification-ppt-notes-analysis.json) and the
[support design](../../openspec/changes/extend-ppt-notes-picture-coverage/design.md).
The subsequently approved proposal separates notes-aware host qualification from the selected
payload operation, preserves nested Photoshop objects, supports existing image
sharing and selects PNGs within the current 64 MiB allowance. Measured stream
savings for that bounded PNG selection are 595,977 / 1,499,469 / 1,431,579 bytes.
Those feasibility results are superseded for runtime acceptance by the
implementation qualification below.

## Notes-bearing PPT runtime qualification, 2026-10-08

The approved implementation adds `ole_ppt_host.py` and `ole_ppt_extensions.py`.
It validates single-edit persist/liveness accounting, typed slide/master/notes
lists, bidirectional notes links and the separately referenced notes master.
Normative master fields and exactly the observed `(0x80000000, 2)` variant are
accepted only in that master role. The observed record versions, owners and
PPT9/10/12 blobs have explicit rules; unknown forms still reject the strategy.

Pictures discovery is independent of strict embedded DOC/XLS payload selection.
The seven subtype-zero Photoshop wrappers and their main-master references are
validated as immutable spans, without interpreting or repairing their nested CFB.
Shared FBSE `cRef` must match the complete simple picture-property consumer count;
complex-property lengths are not image indexes. BStore indexes, counts and UIDs
remain exact. Only selected BLIP representations and enumerated FBSE size/delay
fields can change; the Document length, persist/edit/Current User and notes bytes
do not move. Separate intended-change verification and native physical-size
selection remain mandatory.

PNG selection uses Pictures order and the unchanged 64 MiB sample allowance.
Expanded PNG samples are released between images; retained identities compare
sample length/hash and every non-IDAT chunk. Unselected images and notes-profile
JPEGs remain byte-identical. The previously qualified JPEG codec is retained for
presentations without notes. Shared OLE verification now reads large streams
incrementally through olefile's independently parsed FAT/directory and sector
reader, with exact chain-length/termination checks. The private legacy-root view
patches only its two service fields without copying the complete input. Neither
optimization relaxes strict CFB allocation, metadata or stream checks.

Reproduce with unchanged supplied inputs and private, automatically removed PPT
intermediates:

```sh
venv/bin/python -m dev.ole.qualify_ppt_notes \
  temp/_raw/crimemapping_v2.ppt temp/_raw/mapping_rus_v1.ppt \
  temp/_raw/ruslocal_v1.ppt temp/_raw/mapping_rus_v1.root-normalized.ppt \
  --output dev/ole/qualification-ppt-notes-runtime.json
```

[`qualification-ppt-notes-runtime.json`](qualification-ppt-notes-runtime.json)
records the following default-effort native results. Ordinary compaction alone
gave the original size on every input, so these savings are also additional
savings over that baseline.

| File | Source bytes | Candidate bytes | Saved bytes | Selected PNGs | Worker peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| crimemapping_v2.ppt | 11,301,376 | 10,668,032 | 633,344 | 18 | 132.5 |
| mapping_rus_v1.ppt | 25,570,304 | 24,022,016 | 1,548,288 | 37 | 195.7 |
| ruslocal_v1.ppt | 19,887,104 | 18,439,168 | 1,447,936 | 27 | 222.0 |

The normalized duplicate yields the same 24,022,016-byte result and identical
logical candidate streams. All four source hashes remain unchanged. Every notes
container/storage wrapper and unaffected stream stayed exact, and all candidates
passed the complete OfficeArt contract. LibreOffice slide and notes PDF exports,
rasterized at 72 dpi, yielded identical RGB pages for all 88 slides and 88 notes
pages. Separate development controls using normative zero master fields also
rendered the same notes pages, qualifying the narrow old-master interpretation.
Those controls do not authorize any production normalization of notes fields.

Local qualification used macOS arm64, Python 3.13.7, olefile 0.47, Zopfli 0.4.3,
native helper 0.4.0 and LibreOfficeDev 26.8.0.0.alpha0. Runtime report times include
concurrent test load and stayed below the default 120-second deadline. RSS refers
to the supervised transformation worker and descendants, not total application
memory. These results do not claim Microsoft PowerPoint or remote Linux/Windows
execution; the existing native CI matrix now includes the new generated fixtures.
No mandatory dependency, CLI flag or default operation budget changed.

Final checks: the complete OLE/CFB suite passed 656 tests on Python 3.13.7 and
655 tests on Python 3.9.6, with one expected optional HWP Zopfli skip on 3.9.
The focused transformation/transaction/budget/output/archive suite passed 418
tests with two environment skips. Repository-wide Ruff and Mypy (176 source/test
files), documentation production build, all 104 strict OpenSpec items and
182-requirement baseline ownership/audit reconciliation passed. These suites
include 57 generated notes/Pictures tests; private supplied files are not needed
for normal regression execution.

## Combined PPT options and memory-limit regression, 2026-10-08

The three-option path retained an outer CFB parse while independently encoding
Pictures, then loaded the source again for strategies that ultimately rejected
the notes-bearing host. Whole-file root normalization and native replacement
buffers added transient copies. Separate native candidates now run against the
already verified source before picture encoding. Only preservation identities
remain during assembly, staged Python payloads are released, and the native
writer streams replacements with exact growth/truncation checks. Its source
carrier is allocated once at the observed size. The 256 MiB worker limit and
64 MiB PNG selection allowance are unchanged.

[`qualification-ppt-combined-options.json`](qualification-ppt-combined-options.json)
records both the bulk dryrun and independently checked private candidates with
all three OLE options. Every candidate SHA-256 matches its previously rendered
candidate, and every source SHA-256 remains unchanged.

| File | Candidate bytes | Saved bytes | Bulk worker peak MiB | Private candidate worker peak MiB |
| --- | ---: | ---: | ---: | ---: |
| crimemapping_v2.ppt | 10,668,032 | 633,344 | 129.6 | 127.7 |
| mapping_rus_v1.ppt | 24,022,016 | 1,548,288 | 215.2 | 215.2 |
| ruslocal_v1.ppt | 18,439,168 | 1,447,936 | 195.8 | 196.3 |

Complete OLE/CFB regressions passed 662 tests on Python 3.13 and 661 tests with
one expected optional HWP Zopfli skip on Python 3.9. The final native allocation
adjustment additionally passed the 268-test native/notes/extended subset. Five
Rust tests, Rust fmt/Clippy, repository Ruff, changed-module Mypy and spec
ownership reconciliation passed. The current native helper was rebuilt locally;
other installations need to rebuild it to receive the streaming-memory fix.

An attempted private outfile API probe was refused by the existing filesystem
metadata guard: macOS adds a non-removable `com.apple.provenance` attribute to
the destination although the supplied source has no attributes. This is separate
from content transformation and memory qualification; no metadata check was
relaxed, and no original was published or changed.

[`qualification-ppt-remaining-savings.json`](qualification-ppt-remaining-savings.json)
records a read-only survey: there are no exact duplicate BLIPs or encoded image
payloads on these inputs. Processing the unselected PNGs in zlib9 trials adds
639,446 stream bytes on mapping and 202,866 on ruslocal, before CFB size selection.
All three presentations contain seven identical 720,810-byte Photoshop payloads,
but deduplicating distinct external-object identities/storage references remains
outside the qualified runtime contract. These findings do not extend the notes
deduplication profile or authorize rewriting those objects.

## Qualified PPT PNG refiltering, 2026-10-08

The approved `extend-ppt-png-refiltering` change integrates the PNG experiment
recorded in [`qualification-ppt-pptx-comparison.json`](qualification-ppt-pptx-comparison.json).
All 50 original image encodings match between mapping PPT and its converted PPTX.
The main compression difference is PNG row filtering: the older PPT codec keeps
filtered scanlines exact, whereas the PPTX optimizer chooses better filters.
The PPTX also contains one Photoshop storage where the PPT contains seven;
that storage-sharing difference remains outside production qualification.

Production now independently reverses all five PNG filters for static,
noninterlaced 8-bit PPT PNGs and compares exact unfiltered samples. It retains
IHDR, indexed samples/palette, alpha, hidden RGB and every non-IDAT chunk exactly.
Optional oxipng 10.2.0 runs at level 4 with bounded filters `0,1,6,7`, disabled
color/depth/palette/interlace changes, libdeflate level 9 and the configured thread count. Each optional trial has a one-second ceiling and reserves 20 seconds for final verification. Local expiry retains verified prior encodings; actual root exhaustion remains a refusal. Only its
verified IDAT is used; original metadata, including ICC encodings, is restored.
Original/zlib9/bounded Zopfli alternatives remain candidates. Missing or
unqualified oxipng and ordinary bad trials retain verified prior alternatives;
actual root-limit exhaustion refuses the operation.

The current Rust helper accelerates independent verification via `png-unfilter-v1`, reversing already validated rows with two buffers and no new dependency. Python hashes its bounded sample output; scratch and process limits remain enforced. Native/Python/Pillow controls cover every filter and supported color mode. Rebuild the helper with `cargo install --locked --force --path tools/ole-compactor`; older helpers retain Python checks.

Compact identities permit sequential PNG processing with five decode passes
reserved per original sample workload under the unchanged root decoded-byte
limit. Individual 16 MiB and 64-picture bounds remain; DOC/XLS retain their
64 MiB aggregate codec bound. The final complete host is independently parsed
and compared in the worker. Its completed check is bound to source/candidate
SHA-256 values and exact filesystem snapshots; publication retains conflict
and metadata guards without repeating decoding under a depleted allowance.

```bash
venv/bin/python -m dev.ole.qualify_ppt_notes \
  temp/_raw/crimemapping_v2.ppt temp/_raw/mapping_rus_v1.ppt \
  temp/_raw/ruslocal_v1.ppt \
  --output dev/ole/qualification-ppt-png-refiltering.json
```

[`qualification-ppt-png-refiltering.json`](qualification-ppt-png-refiltering.json)
records native candidates, independent host contracts, exact source hashes and
LibreOffice slide/notes RGB comparisons at 72 dpi. All 88 slides and 88 notes
pages match. Every notes/Photoshop storage span and unaffected CFB stream stays
byte-identical, including the old-master normative rendering controls.

| File | Source bytes | Candidate bytes | Saved bytes | PNGs | Worker seconds | Worker peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| crimemapping_v2.ppt | 11,301,376 | 9,721,856 | 1,579,520 | 18 | 60.50 | 118.45 |
| mapping_rus_v1.ppt | 25,570,304 | 22,039,040 | 3,531,264 | 49 | 118.11 | 193.28 |
| ruslocal_v1.ppt | 19,887,104 | 17,504,768 | 2,382,336 | 31 | 74.11 | 150.67 |

Public bulk qualification uses byte-identical private source copies and all
three OLE options under the default 256 MiB / 120 s per-file limits. All three
files passed, predicting 8,017,920 bytes saved in that run. Optional-trial timing
can change which verified encodings win; size predictions are measurements of
that run. Embedded DOC/XLS and
strict notes-bearing deduplication continue to report their existing qualified
host boundaries. Matching Photoshop bytes do not authorize merging distinct
storage/object identities. Microsoft PowerPoint editing and remote CI are
separate evidence gates; no deployment is asserted here. The helper acceleration
requires the rebuilt native binary.

Final checks: 920 Python 3.13 OLE/CFB/publication/resource tests passed; two
cross-device tests skipped because macOS had no second filesystem. All 88 new
contracts passed on Python 3.9 with the qualified helper. Seven Rust tests,
fmt/Clippy, Ruff, changed-module Mypy and strict specification reconciliation
passed. A final-profile public CLI outfile on a private crime source copy
produced exactly the independently rendered candidate SHA-256; its source stayed
unchanged. All three original PPT hashes and the converted PPTX hash stay exact.

## Nonzero root creation FILETIME compatibility (2026-10-08)

The reported `temp/_raw/doc20250523-113622.xls` contains root creation FILETIME
133827851172139529. Its other allocation, BIFF8 and unsigned-VBA gates pass.
The installed pinned native writer and independent olefile reader preserve this
value, the root modification time, all metadata and all live streams exactly.
The Python gate now accepts the recorded timestamp rather than rejecting it or
normalizing it to zero. MS-CFB 2.6.2 requires a zero creation field; this is an
explicit preserving compatibility case for observed Office containers.

Regression coverage includes exact 100 ns root timestamp preservation through
DOC/XLS/PPT compaction, record/embedded modes and dry-run; candidate timestamp
mutations and nonzero stream timestamps are still rejected. SquareMacro.xls and
WithEmbeddedObjects.xls now pass full eligibility and native preservation checks.
Earlier JSON qualification reports remain historical snapshots.

The reported XLS yields a verified 3,830,272-byte candidate, equal to its source,
so dry-run predicts no savings. Its canonical unsigned VBA project is copied
unchanged; OfficeArt recompression retains the existing macro-host skip.
No macro is executed and no helper rebuild is required for this Python gate fix.

Validation: 750 OLE/CFB regressions and 184 transaction/publication/resource tests
passed on the project Python 3.13 environment with the installed native helper;
two cross-device tests skipped because no second filesystem was available.
Changed-module Ruff/Mypy, complete strict OpenSpec validation (105 items) and
the requirement ownership/audit checks passed. Repeating the public dry-run
returned status 0 and retained source SHA-256
`c48ae8970cdc738facc6173c62853b0061a4845f403ccd95da0d1456cb06106e`.


## Mixed inline Word Data qualification (2026-10-08)

The user-provided `rosspending_fullreport.doc` previously fell back at paragraph
spacing property `0xA413`, followed by an inapplicable delayed-BStore diagnostic.
It contains ten inline PNGs, 74 binary fields and 490 referenced PrcData regions;
37 references connect the HugePapx/TableProps levels inside Data. The existing
approved mixed-Data requirement now covers this fully resolved profile. Every
moved binary/formatting target is relocated by region identity, while private
bytes, formatting operands, padding, unrelated streams and CFB metadata remain
exact. Unknown properties, gaps and overlapping or cyclic interpretations still
reject recompression. TDefTable's two-byte length is parsed explicitly.

Default public dry-run now reports 1,348,608 -> 1,194,496 bytes (154,112 bytes,
11.43% beyond equal-sized strict compaction); all ten PNGs use exact-filtered
`png-zlib9`. The independent host verifier accepts the candidate. All 48 pages
render with identical dimensions and RGB hashes before/after at 96 dpi under
the same LibreOffice environment. Original SHA-256 stays
`4a4426185600fec98234ab3154d04bd9fbd18f969409e63062d6f009966605a5`.
Measurements and per-page hashes are in
[the qualification report](qualification-word-mixed-data-2026-10-08.json).
The original is not redistributed or counted as a licensed corpus fixture;
Microsoft Word/platform opening checks and broader layout qualification are not
claimed. Existing corpus-acquisition tasks remain open.

Public API publication passed using an exact byte copy with ordinary filesystem
attributes. Distinct output from the actual original was refused: applying its
quarantine attribute adds macOS `com.apple.provenance`, so the exact filesystem
attribute check fails. Native clone/copy and attribute removal did not establish
exact preservation in this environment. The check and original attributes have
not been weakened or removed; this separate publication limitation remains.

Regression controls exercise binary/PrcData relocation, cycle/bounds/overlap and
unknown-property rejection, stale or wrong valid targets, private-byte changes,
HugePapx envelopes, the existing root limits, large TDefTable operands and named
OfficeArt shapes. Existing DOC/XLS/PPT and raster/protection regressions, changed
module Ruff/Mypy, strict related OpenSpec validation and requirement ownership
checks passed.

Primary references: [MS-DOC paragraph properties](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/484822ee-a9d9-4af4-8423-29fda67a6a58),
[NilPICFAndBinData](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/5830324c-4f03-462a-b1f7-45707cd4036e),
[PrcData](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/473fd992-c824-4655-8880-3186bd432f80),
[TDefTableOperand](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-doc/de06ec41-a0ac-4046-9096-cdfaa0091ad9),
and [MS-ODRAW shape names](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-odraw/aaa94f58-eab7-4e88-ba37-de97d319c2e7).

## Additional PPT round-trip Pictures qualification (2026-10-08)

`Apps4Russia_proposal_all.ppt` previously rejected Pictures qualification first at
record 1058, so its public dry-run saved only 5,632 bytes through compaction.
The approved extension qualifies the observed slide/master layout links, layout
instances 1–11, two-entry color-MRU array, tertiary property counts 1–3 and one
zero-mask PPT9 shape-text run. Versions, lengths, owners and references remain
checked. Other shape-text masks and unknown forms remain outside this profile.
No helper rebuild, new dependency, default limit change or application resave
is required. Verbose output now reports the image fallback independently even
when its text matches the compressed-record strategy's reason.

The native result is 2,694,144 -> 2,082,816 bytes: 611,328 bytes saved (22.69%),
605,696 beyond compaction. Thirteen PNGs save 600,990 stream bytes. All 16 JPEGs
and three PNGs with unsupported chunks remain exact. The complete independent
host verifier passes; all 11 slide and 11 notes RGB pages match before/after in
LibreOffice at 72 dpi, and the legacy notes-master control also matches. The
original SHA-256 remains
`971add29b0d952bf8873afb5c33cab50ad6c1ee47497cd31d67cb3e510fdb13a`.
The worker uses 36,072,908 charged decode bytes, 85,032,960 peak RSS bytes and
21.47 seconds in this measured run, within unchanged default limits.

Evidence is in [the runtime report](qualification-ppt-roundtrip-runtime.json);
read-only feasibility remains separately recorded in
[the initial analysis](analysis-ppt-apps4russia.json). Reproduce native preservation
and rendering with:

```sh
venv/bin/python -m dev.ole.qualify_ppt_notes \
  temp/_raw/Apps4Russia_proposal_all.ppt \
  --output temp/ppt-roundtrip-qualification.json
FILEREPACK_OLE_COMPACTOR="$HOME/.cargo/bin/filerepack-ole" \
  venv/bin/pytest -q test/test_ole_ppt_roundtrip.py
```

All 62 new generated contracts pass on local macOS Python 3.9.6 with zlib and
the qualified helper; the Python 3.13.7/native OLE and public CLI regression run
also exercises the new profile. Local qualification does not establish remote
Linux/Windows CI or Microsoft PowerPoint opening/editing. The private input is
not redistributed as a licensed fixture; tests generate their own format bytes.

The initial distinct-output attempt was refused by the filesystem metadata guard:
macOS assigns protected `com.apple.provenance` to the newly created local stage,
and removing it does not establish the original's empty attribute set. This happens
at file creation, independently of mode 0700. Public API output from a private
exact-byte copy with ordinary mode 0644 succeeded; its candidate
SHA-256 matches the independently rendered result and its complete content also
compares equal to the actual original. The checked copy is saved locally under
`outputs/apps4russia-roundtrip/Apps4Russia_proposal_all.ppt`; publication evidence
and the initial original-metadata refusal are recorded in the runtime report.

### macOS publication correction (2026-10-08 follow-up)

Publication now records the system provenance of a newly created local stage
before copying the candidate. On macOS, when the original has no provenance,
that exact creation-time value is retained along with every original attribute.
Different original provenance, changed or later-added stage provenance, other
unpreserved attributes, modes and mtimes still fail verification. No protected
system label is removed and no source attribute is omitted.

The public CLI now writes directly from the unchanged actual original to
`outputs/apps4russia-roundtrip-preserved/Apps4Russia_proposal_all.ppt`, retaining
mode 0700 and the original nanosecond mtime. It produces the same 2,082,816 bytes
and SHA-256 as the independently rendered candidate. A private mode-0700
in-place run with backup also passes: the backup retains all original bytes and
both files retain their required attributes, mode and mtime. The private files
are removed afterwards. Publication and independent content evidence is in
[the follow-up report](qualification-ppt-macos-publication.json).

The shared filesystem/candidate/output suite passes 186 tests with two explicit
second-filesystem skips on both local Python 3.9.6 and 3.13.7. Nine controlled
provenance cases include non-Darwin platforms, ignored writes and all exception
bounds. This corrects the earlier creation-time diagnosis and supersedes the
PPT publication refusal above; it does not assert remote CI or deployment.

## Qualified DOC PNG refiltering, 2026-10-08

The user-authorized `extend-doc-png-refiltering` change reuses the bounded optional
oxipng 10.2.0 profile for audited inline/floating DOC pictures. Compact identities
retain exact unfiltered 8-bit samples, including invisible colors, with all
non-IDAT chunks restored from the source. Interlaced/high-depth PNGs retain exact
filtered rows. DOC's selection allowance is capped by both its existing 64 MiB
aggregate bound and five reserved passes under the root decoded-byte ceiling.
XLS qualification and PPT encoder/selection limits remain unchanged.

The 27 new controls cover every supported color mode, inline/floating consumers,
opaque history, changed samples/alpha/palette/metadata/depth, real public output
and dry-run, unsupported layouts and resource reservation. The shared row/encoder
controls still cover all five filters, missing/hostile/expired encoders and both
native/Python verification. Two former sub-sector DOC diagnostic fixtures now
save an additional sector with refiltering; their fallback diagnostic controls
explicitly disable the optional encoder.

```bash
venv/bin/python -m dev.ole.qualify_word_properties \
  temp/_raw/gov.doc temp/_raw/rosspending_fullreport.doc \
  --writer tools/ole-compactor/target/release/filerepack-ole \
  --output-dir outputs/word-png-refilter-coverage \
  --report dev/ole/qualification-word-png-refilter-2026-10-08.json
```

The report records unchanged source hashes, independent whole-host equality and
all 34/48 identical LibreOffice RGB pages. `gov.doc` is 4,060,672 bytes (10.82%
smaller), improving the previous candidate by 219,136 bytes; the second DOC is
1,049,088 bytes (22.21% smaller), improving by 145,408 bytes. Local candidate plus
independent verification took approximately 11.0 and 4.3 seconds. The originals
are user inputs and are not redistributed; generated controls use licensed
fixtures. These results describe the local working tree, not release/deployment,
Microsoft Office editing or remote platform execution.
The complete related native Python regression run passed 683 tests; changed
runtime modules passed mypy, and changed runtime/tests passed Ruff. Strict
specification validation and the 187-requirement/288-source ownership audit pass.

## Qualified PPT animation and rejected storage sharing, 2026-10-09

`extend-ppt-animation-storage-sharing` admits immutable sound-free legacy checker
animation records (4116/4081) and audited PPT10 checker/visibility timing. Typed
headers, owners, children, fields, strings and live unique visual shape IDs must
pass; unknown/sound-bearing/malformed forms retain the verified compaction
baseline. This changes Pictures admission only; nested payloads, distinct persist
IDs, historical edits and the strict trailing-object contract remain unchanged.

The supplied `openbudget.ppt` is now 6,936,576 bytes from 7,742,464 (10.4087%),
compared with the previous 7,728,128-byte compaction. Twelve PNGs save 784,741
logical stream bytes. CFB sector packing yields 791,552 additional physical bytes
beyond compaction. Original/candidate source hashes, full independent equality,
unchanged streams and 41 immutable notes/storage/animation/tag spans are recorded
in [the local qualification](qualification-ppt-openbudget-animation.json).
All nine slide and nine notes RGB page hashes match. The public distinct output
retains mode 0700 and original nanosecond mtime; both supplied originals remain
unchanged. It is saved at `outputs/openbudget-animation-preserved/openbudget.ppt`.

Seven exact Photoshop wrapper copies occupy 5,045,754 bytes, with 4,324,932 bytes
of repeated wrappers. A private candidate that retains all seven object/persist
IDs while storing one physical wrapper is 3,368,960 bytes. Apache POI 5.4.1,
however, resolves only one object, including after save/reopen. Its offset-to-ID
map collapses the aliased records. This is a failed compatibility control, not a
production optimization. Runtime keeps the unique-target index, separate records
and every nested byte; no nested CFB color exception or alias verifier is enabled.
Verbose/report diagnostics count the duplicate wrappers and explain retention,
without adding their bytes to realized savings.

POI opens and saves all seven source and final-candidate embeddings. Updating
persist ID 3, saving and reopening changes that payload only; the other six raw
payload hashes remain exact. POI editing and equal LibreOffice pages supplement
the complete runtime contract; interactive Microsoft PowerPoint was not tested.
Java jars remain private local QA dependencies and their versions/hashes are
pinned in the report. Reproduce with the compiled `PptStorageCompatibility.java`
and its POI 5.4.1 classpath:

```bash
venv/bin/python -m dev.ole.qualify_ppt_animation \
  temp/_raw/openbudget.ppt outputs/openbudget-animation-preserved/openbudget.ppt \
  --writer /absolute/path/to/filerepack-ole \
  --poi-classpath '/absolute/path/to/jars/*:/absolute/path/to/compiled-control' \
  --report dev/ole/qualification-ppt-openbudget-animation.json
```

The helper creates all unsupported sharing/edit/render controls privately and
removes them. Generated regressions include owners/flags/sound/variants/targets,
immutable-byte mutation, alias rejection, PNG rewriting, PPT/POT/PPS public
publication/dry-run, disabled image policy and no additional sector gain. The 876
related OLE/CLI regression suite passed on local Python 3.13.7; the final focused
controls also pass on 3.9.6 and 3.13.7. Changed runtime passes mypy, changed
runtime/tests/QA helper pass Ruff. Strict validation passes all 109 items and the
canonical/source audit is 189 requirements/290 blocks. No release, deployment or
remote CI success is implied.

### Main runtime and installed-package integration, 2026-10-09

The qualified PPT changes run through the ordinary `repack`/`bulk` OLE dispatcher
with `--ole-recompress`; no QA script is needed to activate them. Source and wheel
builds include all 106 runtime Python modules. Distribution checks now require
complete runtime inclusion in both artifacts, and the installed-wheel CI suite
includes notes, round-trip, animation and PNG-filter regressions.

A fresh installed wheel outside the checkout import path passed 482 selected
PPT/CLI/filesystem preservation tests, with two explicit second-volume skips.
Its console CLI reproduced 7,742,464 → 6,936,576 bytes for openbudget.ppt and
2,694,144 → 2,082,816 bytes for Apps4Russia_proposal_all.ppt. Both runs were dry-run
and retained the original source hashes. Package/API/entry-point/license checks
passed; development Java/renderer experiments are absent from the runtime wheel.
Evidence and artifact hashes are in
[the integration report](qualification-ppt-main-integration.json). These are
working-tree and local artifact results, not a publication or remote CI claim.

## Qualified PPT fly-from-bottom animation, 2026-10-09

The supplied `opengovernment_rewired.ppt` is admitted by the normal opt-in
Pictures operation after auditing its legacy `(1, 12, 3, 0, 0, 0)` animation tuple,
linear PPT10 x/y keyframes, accompanying null-bullet PPT9 text runs, exact PPT10
font defaults and composite-master references. Unknown directions/formulas,
non-null bullet pictures, malformed text runs and missing or inconsistent graph
targets remain rejected. The animation and all programmable tags are immutable;
the existing trailing-storage writer and write mask are unchanged.

The public CLI predicts and produces **10,278,912 → 9,250,816 bytes (10.00%)**:
1,028,096 total saved bytes, including 1,013,248 beyond strict compaction. Twenty
PNG payloads are recompressed. All four Photoshop storages remain separate and
exact. The original bytes, mtime and permissions remain unchanged; the candidate
is `outputs/opengovernment-fly-preserved/opengovernment_rewired.ppt`.

[Qualification evidence](qualification-ppt-opengovernment-fly-animation.json)
records the complete OfficeArt contract, 122 exact animation/tag/notes/storage/
layout spans, and matching RGB hashes for 19 slides and 19 notes pages.
Apache POI 5.4.1 independently compares decoded picture samples, four resolved
embedding identities/payloads, animation/page/document tags and all 113 shape
client-data records, including read/save/reopen controls for source and candidate.
Static rendering does not measure animation playback; exact complete animation
bytes and reader/save/reopen comparisons are the animation-data controls.

Seventy-five new generated controls cover valid fly data, altered headers,
effect directions, keyframe roles/times/formulas, live shape references, text
masks/bullet references, font targets, composite identities and independent
immutable mutations. The focused 180-test run passes, alongside 1,208 OLE/CLI/
transaction tests (two explicit filesystem-environment skips). Ruff, Mypy,
strict related OpenSpec validation and canonical audit reconciliation pass.
Python 3.13 was executed; this extension has Python 3.9 syntax/type-target checks,
without a Python 3.9 runtime claim. Java, renderer and QA helpers remain outside
the runtime wheel. Development evidence is local, with no release or deployment.

```sh
venv/bin/filerepack repack temp/_raw/opengovernment_rewired.ppt \
  --ole-recompress --verbose --output-dir outputs/opengovernment-fly-preserved
javac -cp '/absolute/path/to/poi-5.4.1-jars/*' -d /private/control \
  dev/ole/PptAnimationCompatibility.java
venv/bin/python -m dev.ole.qualify_ppt_fly_animation \
  temp/_raw/opengovernment_rewired.ppt \
  outputs/opengovernment-fly-preserved/opengovernment_rewired.ppt \
  --poi-classpath '/absolute/path/to/poi-5.4.1-jars/*:/private/control' \
  --report /private/qualification.json
```

Use a fresh distinct output directory for the first command; the qualification
command reads its two presentation inputs and writes only its separate report.

The final wheel was installed in a separate environment, its runtime sources
were compared with the checkout, and the same 180 tests passed against the
installed modules. The installed console command independently selects the
OfficeArt strategy. Optional PNG trials retain earlier verified encodings when
their local time ceiling is reached, so physical savings may vary with system
load; such a fallback is recorded separately in the qualification evidence.
