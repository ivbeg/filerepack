# Change: Add preserving CPBZ2 stream recompression

## Why
CPIO archives compressed with bzip2 commonly use `.cpbz2`, which is currently
skipped by filename discovery despite having a compatible stream recompressor.

## What Changes
- Recognize `.cpbz2` as a standalone bzip2 alias, including case-insensitive
  discovery and `cpbz2`/`bz2` extension filters.
- Recompress only the outer bzip2 stream at level 9, preserving the complete
  decoded CPIO bytes and the original filename/extension.
- Reuse full-stream validation, decoded SHA-256 comparison and existing
  savings, dry-run, destination and filesystem metadata policies.
- Cover standard-library and external-bzip2 paths, CLI/bulk/nested routing,
  corrupt inputs/candidates and candidates with different decoded content.
- Document that CPIO members are not extracted or optimized, even with `--deep`.

## Impact
- New capability: `cpbz2-recompression`.
- Affected code: extension registration, standalone aliases, validator aliases,
  tests and format/archive documentation. No new dependency or CLI flag.
- Raw `.cpio` remains unsupported for container rewriting. `.cpio.bz2` retains
  its existing generic bzip2 route.
- The user's explicit request to implement this previously described outer-stream
  recompression authorizes the scoped implementation.
