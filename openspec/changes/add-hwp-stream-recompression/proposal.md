# Change: Recompress qualified HWP 5 document streams with exact decoded bytes

## Why

HWP 5 uses CFB and already-compressed document streams, making it suitable for
format-preserving recompression beyond allocation compaction. It does not use the
OfficeArt host layout or necessarily the RFC1950 wrapper used by Office metafiles,
so it requires its own discovery, framing and verification contract.

## What Changes

- Extend ole_recompress to the separately qualified HWP 5 host profile.
- Recompress already-compressed DocInfo and BodyText/Section streams while
  preserving every decoded record byte and original compression mode/flags.
- Add compressed BinData only when DocInfo/header metadata fully resolves its
  identity and compression policy; preserve exact decoded binary bytes.
- Qualify raw-DEFLATE encoding, bounded native stream replacement and a separate
  hwp-stream intended-change verifier with full unchanged-stream/CFB comparison.
- Report per-stream savings and final physical gain beyond strict compaction.

## Impact

- New capability: hwp-stream-recompression.
- Affected code: HWP host/stream codecs, isolated operation/verifier, native
  replacement, ole_recompress dispatch and docs/fixtures/extras.
- Priority: P2; prerequisite: the HWP profile in
  [additional host support](../extend-ole-host-format-support/proposal.md).
- stdlib zlib provides the baseline; stronger Zopfli remains qualified/optional.
- HWP 3/HWPX, changing compression flags, script rewriting, record reserialization,
  binary image conversion, encrypted/signed/distribution and unqualified
  script-bearing content profiles remain excluded.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

Use real licensed HWP 5 files with multiple sections, binary data and distinct
supported versions. Compare exact decoded stream bytes and all other bytes/CFB
metadata independently, exercise malformed/trailing/over-budget encodings and
flag faults, and verify application opening/rendering where available. Report
unavailable Hancom/platform checks and savings without a percentage promise.
