# Exact-stream HWP recompression

## Decisions

### Discovery and compression state

Use the new host profile's FileHeader signature/version/features and protection
audit. Select only already-compressed DocInfo and the exact BodyText/Section
inventory resolved from document metadata. Keep FileHeader, section identifiers,
record ordering, text, layout, styles, links, scripts and previews unchanged.
Uncompressed files/streams retain their mode; this proposal does not toggle the
global compression bit or infer compression from stream names alone.

Parse decoded record envelopes under bounds without reserializing their bodies.
Resolve BinData IDs, storage names, embedding/link kind and per-object compression
policy from DocInfo and header flags. Add compressed BinData as a separate
qualified subset after document streams; unresolved/default/override combinations
remain unchanged until their exact semantics are qualified. Images inside binary
streams are preserved as exact decoded bytes, not passed to raster optimizers.

### Raw DEFLATE is a distinct codec

Hancom's parsing example uses a negative zlib window parameter for DocInfo, i.e.
raw DEFLATE. Qualify the framing for each admitted stream/version from the primary
specification and real fixtures; do not add an RFC1950 header/Adler checksum.
Require valid complete termination, no unexplained trailing/concatenated data and
bounded output. Raw framing has no zlib checksum, so independently compare exact
decoded bytes rather than claim checksum-based preservation.

Encode with stdlib raw-DEFLATE level 9, retaining the original when smaller.
Optional stronger raw-DEFLATE encoding requires a qualified binding/interface
with recorded version/license and complete framing checks; the OfficeArt zlib
binding cannot be substituted blindly. Preserve all record/binary bytes and
compression declarations. No semantic normalization is needed because decoded
stream lengths/offsets/IDs remain identical.

### Independent verification and native replacement

Independently inspect source/candidate host metadata and decode exactly the
declared changed streams. Compare every decoded byte, unchanged encoded stream,
header/DocInfo metadata, section/BinData identity and complete CFB logical manifest.
Reject an undeclared stream replacement, altered compression flag or missing
section. Exact decoded bytes alone are insufficient if host metadata differs.

Qualify a versioned bounded native replacement interface restricted to the
profile-resolved HWP stream paths, including Section/BinData child storages.
Preserve storage/stream metadata and all unrelated names/objects. It must not act
as an unchecked general CFB stream editor. Strict OLE verification still rejects
encoded-stream changes; the new verifier governs this specific intended change.

### Budgets, selection and reporting

Use the existing isolated root operation bounds, initially no larger than the
OLE defaults (128 MiB file/live streams, 16 MiB per decoded selected stream,
64 MiB aggregate selected decoded bytes and 120 seconds overall). Every repeated
decode/verification consumes the root work budget; no per-section reset. Enforce
separate stream/record counts and live memory/scratch before activation.

Compare original, strict compaction and fully verified stream-recompression
files after allocation. Retain the smallest passing existing thresholds. Expose
profile/version, selected/recompressed stream counts, encoder availability,
stream savings, extra physical savings and fallback reasons through existing
CLI/library/bulk/archive policies. Rollback disables HWP content recompression
while retaining its separately qualified strict compaction profile.

## Qualification stages

First DocInfo/BodyText, then metadata-resolved compressed BinData. Cover multi-
section documents, stored-versus-compressed binary data, Unicode/empty streams,
large record envelopes, original raw framing and rejected wrapper variants.
Test changed decoded bytes, flags, IDs, metadata, missing streams and decompression
limits. Real samples and weak-encoding controls are measured separately. A
Hancom-specific application check must be reported as passed, failed or unavailable;
other readers do not establish Hancom compatibility by themselves.

## Primary references

- [Hancom primary HWP format documents](https://download.hancom.com/support/downloadCenter/hwpOwpml)
- [Hancom raw-DEFLATE/DocInfo/BinData parsing example](https://tech.hancom.com/python-hwp-parsing-1/)
- [Hancom FileHeader and section structure](https://tech.hancom.com/%ED%95%9C-%EA%B8%80-%EB%AC%B8%EC%84%9C-%ED%8C%8C%EC%9D%BC-%ED%98%95%EC%8B%9D-hwp-%ED%8F%AC%EB%A7%B7-%EA%B5%AC%EC%A1%B0-%EC%82%B4%ED%8E%B4%EB%B3%B4%EA%B8%B0/)
