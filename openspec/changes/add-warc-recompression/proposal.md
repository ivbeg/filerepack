# Change: Add preserving WARC record recompression

## Why
Web archives commonly concatenate independently compressed WARC records. The
generic gzip writer currently merges these into one member, removing record
random access. Plain WARC files are not supported.

## What Changes
- Add dependency-free, streaming WARC 1.0/1.1 parsing and level-9 gzip encoding
  with one member per record, including normalization of whole-file gzip inputs.
- Preserve exact decoded headers, content blocks, separators and record order;
  do not normalize headers, generate digests, transform HTTP payloads or convert ARC.
- Verify full framing, gzip integrity, candidate member boundaries and exact
  decoded-byte preservation before publication under shared savings policies.
- Route `.warc.gz` before generic gzip, including WARC identified inside `.gz`.
- Convert standalone plain `.warc` to `.warc.gz` with collision-safe publication;
  skip plain conversion with `--no-convert-container` or inside other containers.
- Skip replacements with adjacent CDX/CDXJ indexes; document rebuilding external
  indexes after recompression. Respect existing format budgets and cancellation.

## Impact
- New capability: `warc-recompression`.
- Affected code: format detection, standalone dispatch, stream handler,
  verification, destination planning and new `filerepack/warc.py`.
- No new runtime dependency or CLI flag. The user's explicit request to implement
  WARC recompression authorizes this scoped implementation.
