## Context
NIBArchive's documented layout has a 50-byte header, followed by object, key,
value and class tables. Object records point to contiguous value-table ranges;
value type 10 points to an object by its ordinal. Sharing serialized values is
distinct from merging objects, which can change runtime identity.

Primary format references:
- https://github.com/matsmattsson/nibsqueeze/blob/master/NibArchive.md
- https://github.com/matsmattsson/nibsqueeze/blob/master/src/MMNibArchive.m
- https://www.mothersruin.com/software/Archaeology/reverse/uinib.html
- https://github.com/michaelwright235/nibarchive (coder-10 trailer limitation)

## Decisions
- Accept version 1/coder 9 or 10 and exact contiguous table framing. The separate
  coder-10 format analysis confirms the same tables and identifies class auxiliary
  integers as fallback class indexes. Validate those indexes and terminated class
  names. Coder 10 can also carry undocumented trailing bytes; those files remain
  outside this profile. Retain the source's coder version exactly.
- Keep every object ordinal and class index. Keep exact scalar payload bits,
  opaque data, duplicate key records and their ordering within each object.
- Group overlapping nonempty object-value ranges into components. Store
  identical components once, then relocate each object's range within its
  component. Preserve all unreferenced records in their original order. This
  avoids expanding partially overlapping ranges or changing object identities.
- Retain the complete ordered key/class tables, including unused entries and
  class fallback indexes. Only structural varints and table locations change.
- A separate fingerprint parser includes the ordered object values and object
  references, exact key/class tables and ordered unreferenced values. It never
  calls the writer or instantiates archived classes.
- Use the existing cumulative format budget for records, bytes, memory estimates
  and cooperative deadlines, plus cancellation checks. Byte input is capped by
  `read_small` (32 MiB at the default 256 MiB memory budget); records and logical
  value visits are charged to the cumulative node limit.

## Risks / Trade-offs
- The format is reverse engineered. Restrict versions and framing, reject
  unknown types and invalid indexes, and test independently constructed bytes.
- More aggressive class stripping and object deduplication could save more;
  preserving the complete metadata and identity graph takes precedence here.
- UIKit loading and UI instantiation/rendering cannot be validated on this
  macOS command-line-tools host. Passive AppKit `NSNib` construction passed for
  both original and rewritten real AppKit files; this is not a rendering gate.

## Validation
Test all documented value types, duplicate keys, cyclic/shared references,
floating-point bit patterns, overlaps, opaque payloads and unused metadata.
Reject corrupt counts/offsets/varints/references and valid candidates with
changed semantic content. Exercise direct, CLI, bulk and nested-archive routes,
publication policies, metadata and resource limits.

See [validation.md](validation.md) for real-file and local regression evidence.
