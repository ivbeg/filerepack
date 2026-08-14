# Change: Fix Mutable Default Arguments

## Why
The `pack_images()` method uses a mutable dictionary as a default argument (`options={'debug': False}`). This is a classic Python anti-pattern — the dictionary is shared across all calls and can be accidentally modified, leading to subtle, hard-to-debug state leakage between invocations.

## What Changes
- Replace `options={'debug': False}` with `options=None` and initialize inside the method body
- Audit the entire codebase for other mutable default arguments

## Impact
- Affected specs: `code-quality`
- Affected code: `filerepack/repack.py` (line ~1213, `pack_images()` method)
- **BREAKING**: None — default behavior is preserved
