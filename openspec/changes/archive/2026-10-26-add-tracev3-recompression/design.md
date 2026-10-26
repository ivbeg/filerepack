## Context

Apple Unified Logging `.tracev3` files are chunk streams. In the inspected profile, chunkset bodies contain `bv41` compressed LZ4 blocks, `bv4-` uncompressed blocks, and a `bv4$` end marker. LZ4 block recompression can preserve decoded bytes while changing the encoded block length. The format is partially reverse-engineered, so the implementation must accept only the explicitly supported structures and markers.

## Goals / Non-Goals

- Goals: reduce `.tracev3` size through in-format LZ4 recompression; preserve decoded data, chunk ordering, metadata, and all non-target bytes; bound parser resource use; leave unsupported inputs unchanged.
- Non-Goals: edit log records, modify logarchive packages/directories, wrap a complete file in another codec, or rewrite live system logs.

## Decisions

- Decision: implement as an optional isolated format worker using `lz4.block`; use raw LZ4 blocks and the input's previous decoded block as the dictionary where required by the supported block stream.
- Decision: keep each original block unless a valid replacement is strictly smaller, and publish only candidates that pass structural and lossless comparison.
- Decision: treat malformed lengths, unknown markers, unsupported chunk layouts, missing required LZ4 support, and exhausted budgets as unchanged/error outcomes; never guess how to repair a stream.
- Decision: reject in-place operations whose source or destination resolves inside macOS's active Unified Log store. Repacking a source from that store to a separate destination remains possible.
- Alternatives considered: compress the whole file externally (would not preserve direct `.tracev3` compatibility); rewrite every block at a fixed HC level (can enlarge data); use private Apple APIs (not portable and not available in this Python package).

## Risks / Trade-offs

- The `.tracev3` format is not a stable public interchange format; a future marker or layout may be rejected until explicitly supported.
- LZ4 HC can use more CPU than the existing encoding; the compression level and worker time/memory budgets limit the cost.
- A successful byte-preservation check proves decoded chunkset equality for the supported parser profile, but not acceptance by every macOS log consumer. The change must document this compatibility boundary.

## Migration Plan

No migration is required. The feature is opt-in through the standalone `.tracev3` packer and its optional dependency. Existing files remain untouched unless the caller requests repacking.

## Open Questions

- None for the proposed scope.
