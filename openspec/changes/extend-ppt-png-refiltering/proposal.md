# Change: Bring qualified PPT PNG compression closer to PPTX

## Why

The supplied mapping presentation retains identical PNG bytes when converted to
PPTX. Its PPTX optimizer saves 5,050,934 bytes, while the exact-filtered PPT codec
saves 1,548,288. Private PPT experiments transplant only independently checked
PNG IDAT data and restore every original non-IDAT chunk. They save 3,811,840 bytes
with the existing 37-image selection, or 4,998,144 bytes with all 49 PNGs. All 45
slides and 45 notes pages render identically. Embedded Photoshop objects remain
byte-identical in both experiments.

## What Changes

- Add a separately qualified PPT PNG profile for static, noninterlaced 8-bit
  samples. Independently reverse PNG filters and compare exact sample bytes;
  retain IHDR and every non-IDAT chunk byte-for-byte, including hidden RGB values.
- Consider optional oxipng 10.2.0 IDAT candidates alongside original, zlib9 and
  bounded Zopfli alternatives. Restore source chunks, preserve BLIP identities
  and all host references, and retain the smallest independently verified result.
- Process PPT PNGs sequentially with compact sample identities. Derive their
  deterministic selection allowance from a conservative root decode reservation
  rather than treating the old 64 MiB workload allowance as retained memory.
  Keep per-image, count and actual root memory/decode/scratch/deadline limits.
- Reuse completed independent final host verification only with exact source
  and candidate digest/snapshot bindings, retaining publication conflict guards.
- Accelerate independent sample verification through a bounded two-row decoder
  in the existing Rust helper. Keep Python checks for older helpers; introduce
  no new dependency, and qualify native output against independent controls.
- Bound optional refilter trials locally and reserve time for final verification;
  retain verified prior encodings when only the local optional trial expires.
- Leave unsupported PNG variants on their existing exact-filtered codec; leave
  DOC/XLS codecs and notes-bearing JPEG bytes unchanged.
- Add corruption, missing-tool, resource and corpus tests and record real file
  gains, costs and independent rendering.

## Impact

- Capability: officeart-recompression. Expected files: ole_raster.py,
  ole_officeart.py, ole_ppt_art.py, ole_recompress.py, candidates.py,
  tools/ole-compactor/src/main.rs, qualification tooling, tests and documentation.
- No new flag or mandatory dependency. Existing --ole-recompress opt-in applies.
- Photoshop storage deduplication is excluded: the preceding experiment establishes
  identical bytes but not independent editing of shared storage in PowerPoint.
- Approval: the user explicitly requested integration of the experiments with
  “Внеси результаты экспериментов в основной код” on 2026-10-08. This authorizes
  implementation of the measured PNG changes; no additional approval is needed.
- Evidence: dev/ole/qualification-ppt-pptx-comparison.json. This prior development
  experiment is not itself production resource qualification or deployment.
