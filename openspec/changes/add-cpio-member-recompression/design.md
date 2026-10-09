## Context

CPIO variants store member metadata and contents in a sequence of headers and
data. `newc` and CRC-newc use fixed-width hexadecimal fields and four-byte
alignment; odc uses octal fields with no inter-record padding; old binary uses
16-bit words, byte-order variants and two-byte alignment. Hard links share an
inode across member names. CPIO can contain privileged device records and
untrusted absolute or traversal paths.

## Goals / Non-Goals

- Goals: losslessly edit files within validated common CPIO archives, retain
  headers and untouched records, preserve CPIO format and bzip2 wrapping, verify
  candidates independently and honor existing resource limits.
- Non-Goals: apply member packers to hard-link groups, follow or recreate
  symlinks during extraction, create device/FIFO records, support vendor-specific
  layouts, normalize paths or convert CPIO formats.

## Decisions

- Decision: implement a bounded streaming parser/writer for newc, CRC-newc, odc,
  and both byte orders of old binary. Preserve each record's original header,
  name, data and padding. Rewrite only the payload size and CRC fields of an
  authorized changed regular single-link member, then align that record using
  its original format. Preserve trailer ordering and restore block padding.
- Decision: stage only regular single-link members under normalized relative
  paths. Never materialize symlinks or special files. Reject ambiguous/colliding
  paths, malformed hard-link groups, unsafe ancestors and unsupported types from
  the inner-edit path while retaining ordinary verified stream recompression.
- Decision: keep hard-link and symlink records byte-identical, including links to
  files that are optimized through another name; therefore hard-link groups are
  ineligible for member optimization.
- Decision: use existing packers in a private extraction tree. Bind their accepted
  results to exact member paths and preservation keys. Reparse the actual encoded
  candidate and compare ordered entries, all metadata and every untouched
  payload before shared publication.
- Decision: treat `.cpio` as a CPIO container, `.cpbz2` and `.cpio.bz2` as bzip2
  wrapped CPIO containers, and only classify a generically named `.bz2` by a
  bounded decoded-header peek.

## Risks / Trade-offs

- Unsupported or malformed profiles do not receive inner edits. Their original
  bytes remain eligible for the existing outer-stream bzip2 recompression.
- CPIO supports platform-specific path and metadata semantics; the implementation
  skips ambiguous paths and preserves encoded IDs and mode fields without
  requiring elevated privileges.
- Member validation adds one bounded scan of the source and candidate archives.

## Validation

Use independently generated fixtures in every supported CPIO profile, compare
all raw member metadata and untouched bytes, verify authorized inner packers,
read rebuilt outputs with an independent `cpio` implementation when available,
and run archive preservation, path-safety, budget, dry-run and full-suite tests.
