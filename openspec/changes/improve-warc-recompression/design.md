# Per-record WARC gzip selection

## Goals and non-goals

- Goal: Never discard a smaller eligible original gzip member because another
  record in the archive has different compression characteristics.
- Goal: Make `--ultra` request additional lossless WARC compression effort.
- Goal: Keep normal WARC output standard gzip with exactly one record per member.
- Non-goal: change WARC headers or payloads, recompute digests, mutate CDX/CDXJ,
  convert to Zstandard or weaken archive-level acceptance and resource policies.

## Decisions

1. Continue parsing the decoded WARC stream with the existing strict bounded
   parser. While decoding source gzip, retain an original member as a candidate
   only after its trailer is valid and its entire decoded contents parse as
   exactly one complete WARC record. A member that splits a record or contains
   multiple records is not eligible for reuse.
2. For each record, compare the eligible source member and a fresh zlib-9 gzip
   member. With `ultra`, also compare an optional pinned Zopfli-15 gzip member
   when the decoded record is within the separately qualified size cap. Use the
   smallest candidate; prefer the source member on exact ties, then zlib-9.
   Recheck each emitted member by decoding and comparing exact record bytes.
3. Do not add a mandatory encoder dependency. Reuse the existing `zopfli==0.4.3`
   optional backend if it is available and its platform/runtime qualification
   covers the current environment. Otherwise finish with original/zlib-9
   candidates. Large records beyond the cap also use the best existing
   candidate. Establish or adjust the cutoff using the pinned corpus before
   implementation. Runtime audit reporting stays with the separate audit-report
   capability.
4. Propagate the already-existing `ultra` boolean through the WARC dispatch
   adapter. Do not add a WARC-specific profile flag; named profile resolution
   stays in `add-optimization-profiles`.
5. Use operation-owned scratch and existing cumulative decoded/written bytes,
   memory, time and cancellation budgets. If optional compression exhausts the
   operation budget, follow the current failure and source-retention contract;
   never restart the budget or publish a partially checked candidate.
6. Retain whole-archive minimum-savings policy. The per-record minimum keeps the
   output no larger than the smallest candidate for each record, but this does
   not remove the user's configured archive-level savings threshold.
7. Do not add libdeflate in this implementation. Research showed useful gains,
   but the upstream library is whole-buffer and its Python bindings are third
   party; any binding needs explicit packaging and platform review. Do not emit
   `.warc.zst`: the available IIPC WARC-Zstandard format remains proposed and
   experimental.

## Resource and validation notes

The initial measurements only qualify records up to 512 KiB; this is a research
cap, not a final supported limit. Use the fixed sources in
`dev/warc/results-2026-10-05.json` and add representative binary, large response,
request, metadata and revisit records before setting the production cutoff.
Zopfli's runtime grows with effort and its upstream describes the compressor as
slow, so no larger-record promise follows from these small samples.

The current transaction flow makes multiple full decoded passes. This proposal
keeps those checks unchanged. A future transaction-level optimization may reuse
the writer's source fingerprint only through a typed proof bound to the captured
source and staged candidate; it must coordinate with `refactor-repack-transactions`
and `add-operation-resource-budgets` and keep an independent candidate validation.

## Qualification

On 27 Common Crawl records, current zlib-9 output totals 153,868 bytes. Selecting
minimum gzip size across source, zlib-9 and Zopfli-15 per record totals 144,758
bytes (5.92% less); allowing either Zopfli-5 or 15 per record totals 144,731
bytes (5.94% less). On a controlled two-record mixed archive, choosing source or
zlib-9 per record recovers 1,769 bytes compared with the current whole-file
rewrite. These samples are small and text-heavy. See the linked research report
for input provenance, timing notes and the full candidate results.
