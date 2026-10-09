## Decisions

The qualified PPT-only codec compares exact unfiltered 8-bit scanline samples.
A bounded decoder reverses None, Sub, Up, Average and Paeth filters and hashes rows
without retaining a second complete sample buffer. All non-IDAT chunks, IHDR,
palette/index identity, alpha and even invisible RGB samples remain exact. Other
layouts retain the exact-filtered codec and verifier.

Runtime qualification exposed excessive Python row-loop cost on large images.
The existing native helper therefore advertises the bounded `png-unfilter-v1`
capability. It independently reverses already validated filtered rows with two
row buffers and writes exact sample bytes to an owned temporary file; Python
hashes that output in bounded blocks. Every temporary byte is charged to root
scratch and the process remains subject to lifetime/RSS/cancellation limits.
No new native dependency is introduced. Old helpers retain the Python verifier.
All five filter types and color modes are compared against both Python and an
independent Pillow decoder; malformed bounds, rows and palette indexes fail.

Source inspection retains both the sample identity and the exact filtered-source
digest. Lazy encoding uses the latter to recheck its input without decoding all
samples again. An optional oxipng trial disables depth/color/palette/interlace
changes, runs with bounded lifetime and thread count, and contributes only IDAT.
Default trials use filters `0,1,6,7` and libdeflate level 9 to bound encoder cost.
Each optional trial has a one-second local ceiling and reserves 20 seconds for
final host verification/publication. Local trial expiry retains independently
verified prior encodings and accounts partial output; actual root exhaustion or
cancellation still aborts. This prevents one expensive optional image trial
from discarding all useful work. The root reservation and image selection stay
unchanged between source and candidate verification.
Its output is independently parsed; source metadata chunks are restored. Encoder
claims and rendered-pixel equality alone cannot accept an output.

Original/zlib/Zopfli representations remain candidates. Larger representations
need no acceptance verification; the winning candidate is independently decoded
before it can enter the native host writer. Final host parsing repeats the full
sample/metadata/reference identity check. Failed trials retain verified earlier
alternatives; actual root-budget exhaustion stops the operation.

The independent final worker check returns source/candidate SHA-256 bindings.
The publishing process captures both file generations, checks those digests and
passes the completed verification to the shared transaction. That transaction
rechecks both exact snapshots and retains all adjacent publication guards. It
does not repeat image decoding with a depleted root allowance, which would both
charge redundant work and change deterministic selection. Missing evidence uses
the existing independent validators; mismatched evidence refuses publication.

Sequential PPT PNG selection reserves at least five full decode passes per
original sample workload within the root decoded-byte ceiling. Local qualification
must show that all supplied presentations fit unchanged default memory/deadline
limits. Root reservation and every actual decode remain enforced independently.
DOC/XLS retain their existing 64 MiB codec profile. Unsupported PPT image variants
retain the existing exact-filtered and individual-size bounds.

Photoshop storages, their object identities and consumer/persist references are
immutable throughout this change. Storage deduplication needs separate editing
and application round-trip evidence before production enablement.
