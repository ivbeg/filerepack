# Change: Add preserving compiled NIB archive compaction

## Why
Compiled Apple Interface Builder NIB archives can contain repeated serialized
value sequences. Filerepack currently skips `.nib` files. Sharing stored values
can reduce their size without merging the UI objects that use them.

## What Changes
- Route `.nib` through a dependency-free, bounded NIBArchive parser and writer.
- Support version 1/coder 9–10 with contiguous documented tables and value types
  0–10; skip keyed-plist nibs, directory nib bundles and other archive variants.
- Share identical value-table components and canonicalize structural varints;
  preserve object identities, ordered values, references, keys, class metadata
  and unreferenced values; validate class-name framing and fallback indexes.
- Verify source/candidate preservation separately from optimization, and use
  the existing publication, dry-run, backup and savings policies.
- Add adversarial, lifecycle and integration tests and document the profile.

## Impact
- New capability: `nib-compaction`.
- Affected code: extension registry, standalone dispatch, candidate validation,
  compatibility exports and new `filerepack/nib.py`.
- No runtime dependency or new CLI flag. The user's request to add support
  authorizes implementing this scoped change.
