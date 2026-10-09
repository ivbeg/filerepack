# Legacy Office CFB writer

Optional native writer for filerepack's stream-preserving DOC/XLS/PPT compaction.
The production dependency is pinned to `cfb 0.14.0`; `Cargo.lock` pins its full
dependency graph. Build with Rust 1.89+ (the locked UUID dependency's minimum).

From a repository checkout or extracted source distribution:

```sh
python -m pip install '.[ole]'
cargo install --locked --path tools/ole-compactor
filerepack repack report.doc --dryrun --stats
filerepack repack workbook.xls
```

Ensure Cargo's bin directory is on PATH. Alternatively, build with
`cargo build --release --locked --manifest-path tools/ole-compactor/Cargo.toml`
and set `FILEREPACK_OLE_COMPACTOR` to the resulting executable's absolute path.
Python wheels install the adapter and verifier, not this native executable.
No Java, .NET or Office runtime is required for production compaction.

The helper takes `SOURCE EMPTY-STAGING-FILE`. It opens the source read-only and
refuses a nonempty destination. The Python adapter creates/owns that staging
file, checks the Office profile, independently verifies the result with pinned
`olefile 0.47`, and publishes it through the shared transaction. Invoke it
through filerepack to obtain those eligibility, preservation and publication checks.

Version 0.2.0 additionally advertises `ppt-stream-replacement-v1` through
`--capabilities`. Its internal `--replace-ppt-streams DOCUMENT CURRENT-USER
SOURCE EMPTY-STAGING-FILE` invocation substitutes only the two root streams
`PowerPoint Document` and `Current User`; all other streams, including nested
streams with those names, are copied unchanged. Replacement inputs are bounded
to 128 MiB / 4 KiB and opened/size-checked before the destination. Their bytes
are copied in bounded blocks, with growth and truncation rejected. This backend does
not select objects or authorize record changes: use
`filerepack repack slides.ppt --ole-recompress` with the `ole-recompress` extra
for eligibility, bounded worker encoding and independent intended-change checks.
Old helpers retain ordinary compaction through capability fallback.

Version 0.3.0 adds `officeart-stream-replacement-v1`. Internal fixed modes are:

```text
--replace-officeart-streams doc WORD-DOCUMENT DATA SOURCE EMPTY-STAGING-FILE
--replace-officeart-streams xls WORKBOOK SOURCE EMPTY-STAGING-FILE
--replace-officeart-streams ppt POWERPOINT-DOCUMENT PICTURES SOURCE EMPTY-STAGING-FILE
```

These replace only the corresponding existing root streams. Arbitrary host names,
stream paths and missing root streams are refused. Each private input is checked
for exact length and a 128 MiB maximum; aggregate live stream size is checked
before opening the empty destination. Nested streams with identical names and all
other stream/metadata bytes are copied unchanged. Use the Python OfficeArt mode
for host qualification and independent content/reference verification; this native
interface alone cannot authorize content changes. Old helpers retain strict
compaction with an explicit capability fallback reason. Public usage:
`filerepack repack report.doc --ole-recompress --verbose`.

The current helper streams staged replacements instead of retaining all of them
beside the source CFB buffer. Rebuild the helper to receive this memory fix:
`cargo install --locked --path tools/ole-compactor --force`.

Current builds also advertise `png-unfilter-v1` for independent PPT PNG sample
verification. The internal invocation is
`--png-unfilter-v1 WIDTH HEIGHT COLOR-TYPE PALETTE-ENTRIES FILTERED EMPTY-SAMPLES`.
It reads already validated noninterlaced 8-bit rows, reverses all five PNG
filters with two row buffers, checks palette indexes and exact input bounds,
and writes exact unfiltered samples to an owned empty output. Both input and
sample workload are bounded to 16 MiB. Python retains PNG framing/CRC/metadata
checks, hashes the samples and controls root scratch/RSS/lifetime/publication.
This adds no dependency. Rebuild to receive the accelerated verifier; older
helpers retain the bounded Python row checks.

Qualified extensions: DOC/DOT, BIFF8 XLS/XLT/XLA, PPT/POT/PPS in CFB v3 with
512-byte sectors. Live stream bytes, exact names/hierarchy, empty objects, CLSIDs,
state bits and recorded FILETIMEs are retained. Free physical sectors and
mini-stream holes can disappear. The default copies all application bytes; the
opt-in OfficeArt/PPT modes have separate intended-change contracts.
Compaction can yield no savings. Equal/larger candidates are discarded by default.
Observed nonzero root creation FILETIMEs are preserved exactly despite the
MS-CFB requirement for a zero value; both root timestamps remain part of the
independently compared manifest. No timestamp normalization is performed.

Limits: 128 MiB source/candidate and aggregate stream bytes, 8,192 directory slots,
32 storage levels, 128 directory traversal levels, 200,000 Office records,
4,096 PPT edits, 16 MiB per encoded/decoded PPT VBA storage, 4 MiB per property
stream/StwUser table, 4,096 properties/user variables,
and a 120-second writer timeout. BMP names use pinned Unicode 16.0.0 simple
uppercase mappings, including `ß` and Greek mappings that Python's full
uppercase expands. Supplementary Unicode names remain outside the pinned writer's
qualified comparison profile. The observed slot-zero root service name `R` with
declared length 2 is normalized to `Root Entry` in private reader/writer views;
only those name/length bytes can change. Source files remain untouched until
normal verified publication, and equal-size candidates are still discarded.
Other invalid names, malformed allocations, orphan objects, storage entries containing
stream allocation fields, unsupported root metadata and incomplete independent
reads are rejected. Canonical unsigned DOC/DOT `Macros` and XLS/XLT/XLA
`_VBA_PROJECT_CUR` projects are retained byte-for-byte, after bounded host signature
checks. DOC StwUser signature names and DocumentSummaryInformation signature
properties are detected even without a signature-named stream. Project headers
and property indices are checked; VBA code and property values stay opaque.
PPT/POT/PPS qualify a single user edit with one canonical VBAInfoContainer and
a unique persist reference to a top-level compressed/uncompressed project storage.
The Python reader inspects its nested CFB with a 16 MiB decoding bound and exact
wrapper termination checks; the helper retains the encoded record byte-for-byte.
CFB v4, other OLE applications, unknown/embedded/incomplete or history-dependent VBA layouts,
signed, encrypted, rights-managed and unqualified profiles remain unchanged
with a reason. Macros and embedded objects are never executed.

Local qualification used macOS arm64, Rust 1.93.1, real Apache POI fixtures,
OpenMcdf 3.3.0 comparison and a pinned LibreOffice renderer. Reproduction and
measurements: `dev/ole/README.md`, `dev/ole/qualification.json` (initial pilot),
`dev/ole/qualification-vba.json` (DOC/XLS VBA) and `dev/ole/qualification-ppt-vba.json`
(PPT VBA) in the repository.
`dev/ole/qualification-ppt-runtime.json` records the opt-in PPT implementation,
its ordinary compaction baseline, exact decoded objects and rendering checks.
`dev/ole/qualification-officeart-runtime.json` records the shared OfficeArt runtime,
its compaction comparison, worker resource usage and renderer results.
Linux/Windows native jobs are configured in CI; Microsoft Office is not locally
qualified. Renderer checks supplement exact logical manifests.

License: BSD-3-Clause, as the project. See LICENSE and THIRD_PARTY_LICENSES.md for
the MIT-licensed writer dependencies. The comparison-only OpenMcdf program is
outside this helper and uses the MPL-2.0 OpenMcdf library.

## Version 0.4.0 qualified path interfaces

The Python layer now qualifies strict MSG, Visio 11, Publisher 2002, MPP9, MSI
and HWP 5 profiles, with separate intended-change verifiers for new content
modes. This supersedes the older host list above; arbitrary CFB remains excluded.
The native helper does not decide eligibility or authorize application changes.

`qualified-stream-replacement-v1` takes
`--replace-qualified-streams-v1 HOST PLAN SOURCE EMPTY-STAGING-FILE`. PLAN begins
with `FRPLAN01`, a little-endian u32 count, then u16 UTF8 stream-name/path lengths
and those strings. The plan is limited to 1 MiB/8,192 unique existing streams.
Generated private payload files and source paths are bounded; aggregate live
streams remain ≤128 MiB. Fixed host scopes admit only DOC root Word/Data/Table,
XLS Workbook, PPT Document/Pictures/Current User, HWP DocInfo/Section/BinData,
DOC ObjectPool/_decimal descendants or XLS MBD8hex descendants. Empty/dot/escaping
components, unknown modes, duplicates, additions and missing targets are refused.

`qualified-object-extraction-v1` takes
`--extract-qualified-object-v1 HOST-OBJECT SCOPE SOURCE EMPTY-STAGING-FILE`.
Only existing DOC ObjectPool/_decimal or XLS MBD8hex storages can become child
root views. All descendants and logical metadata stay exact. CFB root creation
time is zero; the original parent storage creation time is retained separately
and never imported back. CLSID, state and modified time remain exact. Python
compares the extracted view with the original logical substorage using a second
reader before invoking any child optimizer. Replacement returns existing streams
only; parent class/cache/link metadata and hierarchy are independently checked.

The old fixed interfaces remain supported. Python selects separate strict/image/
embedded/dedup candidates by final allocated size. See `dev/ole/PORTFOLIO.md` and
`dev/ole/qualification-portfolio.json` for current evidence and explicit limits.
