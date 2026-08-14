## Context
filerepack dispatches standalone formats through `_PACKERS` and `STANDALONE_EXTS`. Optional CLI tools (not Python libraries) do the rewrite; output is written to a temp file, verified, then `os.replace`d. DICOM is a tagged medical container: pixel data lives in `(7FE0,0010)` under a Transfer Syntax UID, and the rest of the dataset (patient/study identifiers, LUTs, overlays) must survive.

This change adds a first, lossless-only DICOM packer. It is a new external-tool dependency with diagnostic-safety constraints, so the tool choice and skip rules need to be fixed before implementation.

## Goals / Non-Goals
- Goals:
  - Recompress uncompressed and RLE-lossless **image** DICOM to JPEG-LS lossless
  - Preserve the DICOM dataset except Transfer Syntax UID / encapsulated pixel data as updated by the encoder
  - Fail closed: skip when the file cannot be proven safe to rewrite
  - Optional tools with doctor/install hints on macOS, Linux, and Windows
  - Nested `.dcm` members inside ZIP/7z/tar follow the existing archive walk
- Non-Goals:
  - Lossy JPEG / near-lossless JPEG-LS / JPEG 2000 irreversible
  - Re-encoding already-compressed JPEG, JPEG-LS, or JPEG 2000 pixel data
  - Extensionless DICOM (PACS dumps without `.dcm`)
  - DICOMDIR, SR, waveforms, encapsulated PDF/CDA, video (MPEG/HEVC) SOP classes
  - Changing SOP Instance UID or stripping private tags
  - A Python DICOM stack (`pydicom` / `pylibjpeg`) as a required or extra dependency

## Decisions
- Decision: JPEG-LS lossless as the only output transfer syntax (`1.2.840.10008.1.2.4.80`).
  - Alternatives considered: JPEG lossless SV1 (`dcmcjpeg +el`) — worse ratios on typical CT/MR; JPEG 2000 lossless (`gdcmconv --j2k`) — extra decoder burden and weaker Windows packaging. JPEG-LS is the usual lossless medical default and both candidate tools support it.
- Decision: Prefer `gdcmconv --jpegls`; fall back to DCMTK `dcmcjpls`.
  - `gdcmconv` is one binary for convert/inspect-adjacent workflows and is well packaged on Homebrew/apt.
  - DCMTK is the Windows-friendly fallback (`choco install dcmtk`; GDCM is weakly packaged there).
  - Env overrides: `FILEREPACK_GDCMCONV`, `FILEREPACK_DCMCJPLS` (existing `ToolSpec` pattern).
- Decision: In-process skip checks, no `pydicom`.
  - Read the 128-byte preamble + `DICM`, parse File Meta Information (always Explicit VR LE) for Transfer Syntax UID `(0002,0010)`, then walk the dataset only far enough to see Pixel Data `(7FE0,0010)` and Digital Signatures Sequence `(FFFA,FFFA)`.
  - If parsing fails, skip (fail closed). A tiny tag/VR table for those elements is enough; a full data dictionary is not.
- Decision: Input transfer syntax allow-list only:
  - Implicit VR Little Endian `1.2.840.10008.1.2`
  - Explicit VR Little Endian `1.2.840.10008.1.2.1`
  - Explicit VR Big Endian `1.2.840.10008.1.2.2`
  - RLE Lossless `1.2.840.10008.1.2.5`
  - Everything else (JPEG, JPEG-LS, J2K, MPEG, Deflated, …) is left untouched.
- Decision: `--lossy` is ignored for DICOM. Quality flags never reach `pack_dcm`. Medical lossy is a later, explicit change if wanted.
- Decision: Do not route DICOM through ImageMagick. `convert` strips tags and is unsafe here even though TIFF/DNG use it.
- Decision: `verify_output(..., 'dcm')` must seek to offset 128 for `DICM`. The current helper only peeks 16 bytes; the DICOM checker uses `path`, not that peek.
- Decision: Category `image`, so `--no-images` skips DICOM without a new flag.

## Risks / Trade-offs
- Homegrown tag walk can miss odd encodings (undefined-length sequences, non-standard preamble-less files) → Mitigation: skip on parse failure; require `DICM` preamble in v1.
- Encoder bugs could change pixels while keeping a valid container → Mitigation: lossless JPEG-LS only; keep original unless output is smaller and verifies; do not claim diagnostic certification.
- Signed instances rewritten would break `(FFFA,FFFA)` → Mitigation: skip when that sequence is present.
- `gdcmconv` missing on Windows → Mitigation: DCMTK fallback and doctor hints.
- JPEG-LS may not shrink incompressible pixel data → Mitigation: existing `keep_if_larger` / `--allow-grow` / `--min-savings` apply unchanged.

## Migration Plan
- Additive. No default CLI behavior changes except that `.dcm` / `.dicom` / `.dic` are no longer skipped when a DICOM tool is installed.
- If both tools are missing, `pack_dcm` returns `None` and the source file is unchanged (same as DNG without `tiffcp`).
- Rollback: remove the packer and extensions; no on-disk format migration.

## Open Questions
- None blocking v1. Lossy DICOM and extensionless detection are deferred.
