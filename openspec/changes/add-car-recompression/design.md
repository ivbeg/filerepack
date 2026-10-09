## Context
The BOMStore v1 header/index/variables and BOM tree framing are described by
Timac's CAR reverse engineering and the original bomutils format research.
CSI v1 is a 184-byte header followed by TLV metadata and a length-delimited body.
Real Apple catalogs demonstrate two MLEC shapes: version 0 is a single
compressed payload; version 1 contains KCBC bands. In older catalogs ZIP bands
actually contain gzip members. Codec 2 is ZIP; other codecs remain opaque.

References:
- https://timac.org/2018/1018-reverse-engineering-the-car-file-format/
- https://github.com/hogliux/bomutils
- https://github.com/xtool-org/AssetKit/blob/main/docs/coreui-970-format.md

## Decisions
- Support BOMStore v1, fixed 436-byte CARHEADER storage versions 8–17,
  KEYFORMAT v0 and CSI v1. Skip other versions and ambiguous structures.
- Keep every allocated block including unreferenced blocks; never deduplicate
  block IDs or tree entries. Only trailing null index slots can disappear.
- Keep physical block order and each block address modulo 16. Preserve entire
  allocated tree pages, including padding. Remove only zero padding or declared
  free ranges; reject unclassified nonzero gaps/trailers.
- Rebuild the free list after compaction. Preserve block count convention and
  the original zero index trailer. Check all live/free/table intervals for overlap.
- Parse named trees with bounded traversal and verify leaf chains, back links,
  entry counts and referenced IDs. Decode only values in the RENDITIONS tree.
- Use the existing format budget and cancellation context across optimization
  and separate structural/preservation checks. Bound input buffers, nodes, TLVs,
  decoded streams and tree depth; zlib decoding rejects incomplete streams,
  concatenation, trailing bytes and failed checksums.
- Fingerprints retain all block IDs, opaque bytes, tree/key/variable metadata,
  gzip/zlib wrapper metadata and exact decoded DEFLATE bytes. Only physical
  addresses, unused index capacity, free allocation metadata and known compressed
  length fields are normalized. The verifier never invokes the writer.

## Validation
Original synthetic fixtures exercise all supported framing and fault boundaries.
Read-only native tests use installed Apple catalogs when available; only temporary
copies are rewritten. `assetutil -I` must retain every asset's metadata/digest
apart from SizeOnDisk, and `assetutil -Z` must accept the candidate. Native tools
are optional test oracles; runtime parsing/rewriting remains cross-platform.
