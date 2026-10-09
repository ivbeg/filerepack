# NIB qualification evidence

Local checks on 2026-10-05, macOS, Python 3.13.7.

## Real compiled archives

- Read all 41 regular `.nib` files under
  `/System/Library/Frameworks/AppKit.framework/Versions/C/Resources`.
  All used format 1/coder 10 and completely parsed under the qualified profile.
- Copy each file to an isolated temporary directory, run `pack_nib` on the copy,
  compare preservation fingerprints and re-read the system original to ensure
  its bytes remained unchanged. Every copied archive shrank and verified.
- Aggregate bytes: 864,602 original -> 855,672 candidate, saving 8,930 bytes
  (1.033%). This is measured on this local corpus, not a prediction for other nibs.
- Invoke Swift/AppKit `NSNib(nibData:bundle:)` on all 82 original/candidate
  inputs. Construction succeeded for every input. No instantiation method was
  called; application code, UI rendering and UIKit compatibility remain untested.
- Reconstruct the 1,802-byte coder-9 ibtool sample from the author's published
  [annotated hex dump](https://dkimitsa.github.io/assets/2018/02/13/test.nib.hexdump.html),
  linked from the [format investigation](https://dkimitsa.github.io/2018/02/13/wl-tech-details-2-robovm/).
  All 24 objects parsed and the rewrite preserved its fingerprint. Its already
  compact layout stayed 1,802 bytes. The sample is not redistributed.

No installed application or system resource was modified. Real-file corpus
bytes are not redistributed; the checked-in raw fixtures are original test data.

## Automated gates

- `test/test_nib.py` covers coder 9/10, all value types, bit-exact scalar/data
  preservation, duplicate keys, cyclic references, object identity, overlaps,
  unreferenced records, class fallbacks, multi-byte/nonminimal varints,
  invalid records and undocumented trailers, changed candidate rejection,
  independent verification, cancellation, resource budgets, metadata,
  dry-run/output/backup/savings policies, CLI, parallel bulk and nested ZIPs.
- The first full-suite run used the installed `filerepack-ole 0.3.0`, producing
  13 failures in existing OLE extension tests. The repository's native helper is
  0.4.0. After `cargo build --release --locked --manifest-path
  tools/ole-compactor/Cargo.toml`, all 79 OLE extension tests passed with
  `FILEREPACK_OLE_COMPACTOR` pointing to that built helper.
- Final full suite with the repository helper: **1,896 passed, 159 skipped** in
  69.16 seconds. The focused nib suite: **59 passed**.
- Ruff passed across `filerepack`, `test` and `dev/validate_distribution.py`.
  Mypy 1.20.2 passed across 128 source files with the configured Python 3.9 target.
  New Python files also parsed under Python 3.9 grammar. Python 3.9 runtime and
  Windows/Linux runtime execution were not available locally.
- `openspec validate add-nib-compaction --strict` passed.
- Docusaurus production documentation build (`npm run build` in `docs`) passed.
