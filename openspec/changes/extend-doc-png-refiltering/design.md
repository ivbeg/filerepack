## Decisions

Reuse the qualified PPT codec for static, noninterlaced 8-bit DOC PNGs, with
host-neutral names and diagnostics. Source discovery and final independent
verification both use the same exact unfiltered sample identity. It preserves
IHDR, palette/index bytes, alpha, invisible RGB and every non-IDAT chunk in order.
Only independently validated IDAT bytes can be copied from an optional encoder.

Both inline and floating Word discovery use compact identities, release expanded
rows between images and retain original byte identities for unselected pictures.
Opaque historical/unreferenced PICFs remain exact. Existing Word consumers,
formatting and stream-offset relocation stay in the host adapter.

The DOC selection allowance is the smaller of the existing 64 MiB aggregate
bound and the root decoded-byte limit divided by five. Each actual decode,
scratch write and child process remains charged to that root. The existing
one-second optional oxipng 10.2.0 trial ceiling and 20-second final verification
reserve apply. Missing/invalid/expired optional encoders retain independently
verified original/zlib/Zopfli alternatives; root exhaustion still aborts.
High-depth, interlaced or unsupported PNG variants retain their earlier contract.
XLS stays on its existing exact-filtered codec; PPT behavior and budgets stay exact.

## Qualification

Controlled regressions exercise different legal row filters, hostile image and
metadata changes, inline/floating relocation, opaque history and native/public API
verification. Supplied-document candidates are saved separately from originals,
independently checked and rendered through LibreOffice for pixel comparison.
Microsoft Office and other platforms are not inferred from local results.

The source-bound report is
[`qualification-word-png-refilter-2026-10-08.json`](../../../dev/ole/qualification-word-png-refilter-2026-10-08.json).
`gov.doc` is 4,060,672 bytes, saving 492,544 bytes (10.82%) from its original and
219,136 bytes beyond the earlier exact-filtered candidate. The second document
is 1,049,088 bytes, saving 299,520 bytes (22.21%) from its original and 145,408
additional bytes. All 34/48 LibreOffice 96-DPI RGB pages match exactly, and source
hashes remain unchanged. Seven static PNGs in gov.doc use the new sample profile;
three interlaced PNGs retain exact-filtered encoding. The broader DOCX path can
change interlacing, so its measured savings are not this profile's target.
The complete related native regression run passed 683 tests. Changed runtime
modules passed mypy, and changed runtime/tests passed Ruff. Strict change/spec
validation and the ownership audit passed (187 canonical requirements and 288
audited source blocks). This is local working-tree qualification.
