## Context

Existing handlers use guarded source snapshots, private candidate files and
atomic publication. The extension lists and standalone aliases drive both direct
processing and recursive archive walking. Existing active preservation changes
remain intact; this change adds format-specific checks without claiming those
broader changes complete.

## Goals / Non-Goals

- Goal: implement all ten format families in the reviewed list except LAS/LAZ.
- Goal: never rename these files or discard scientific, image or project data.
- Goal: reject invalid/unsupported inputs and failed verification before writes.
- Non-goal: lossy scientific compression, Blender resaving through execution,
  Jupyter output removal, external NRRD data mutation or LAS/LAZ conversion.

## Decisions

1. Reuse lexical JSON/XML minimization for aliases. JSON Lines needs a separate
   streaming handler preserving record boundaries, exact tokens and line endings.
2. QGZ uses the verified ZIP path with an application policy: validate project
   XML and any auxiliary SQLite payload, preserve unrelated members and prohibit
   nested conversions that change member names. QGD receives a snapshot-safe
   SQLite handler with logical-content verification.
3. PSB uses the existing version-2 Photoshop parser, adds structural and decoded
   channel verification, and only recompresses ZIP channels.
4. Blender compression wraps an unchanged, structurally checked decoded stream;
   preserve existing gzip/Zstandard codecs and verify the decoded hash. Do not
   run embedded Python or open/resave a project. Unsupported file versions are
   skipped rather than guessed.
5. FITS uses optional Astropy/CFITSIO tiled GZIP compression with floating-point
   quantization disabled. Compare logical image arrays bit-for-bit, metadata
   values/comments with repeated-keyword order, and unchanged non-image HDUs.
   Header positions and regenerated checksums can change. Standard compressed-primary layout
   changes are explicit and do not change the filename extension.
6. NRRD supports attached raw/gzip/bzip2 binary arrays with known type/size,
   no offsets and bounded decoding. Preserve every header byte except the
   encoding value and require identical decoded array bytes. Detached headers
   and unsupported encodings remain untouched.
7. Aseprite preserves frames, timings, layer/link/palette and unknown chunk
   bytes, recompressing supported zlib cel/tile data only. Rebuild declared
   lengths and compare normalized decoded chunks before publication.

## Risks / Trade-offs

- FITS readers need tiled-compression support; optional dependency and layout
  behavior are documented. Unsupported/scaled cases must be tested or skipped.
- Blender stream recompression may drop compression seek indexes but preserves
  decoded bytes; real-reader checks are separate from structural verification.
- Native parsers enforce explicit bounds and skip inputs beyond supported limits.
- File extensions alone are insufficient: verify signatures/structure before
  processing SQLite, Photoshop, scientific and QGIS data.

## Migration Plan

Add aliases and optional handlers without changing existing CLI flags. Missing
dependencies leave input untouched. Release tests exercise standalone, nested,
distinct-output, dry-run, corrupt input and failure retention cases.

## Open Questions

None affecting the approved implementation scope. Application rendering and
large-file benchmark evidence are reported separately from format preservation.
