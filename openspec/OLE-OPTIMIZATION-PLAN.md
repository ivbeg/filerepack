# OLE optimization proposals

Created on 2026-10-04 from the requested DOC/XLS compression and additional OLE
format plan. The user approved implementation of all seven changes on 2026-10-04 with
“Реализуй все предложения”. Tasks remain unchecked until their implementation
and required qualification are complete; approval does not claim delivery.

## Current baseline

- [Container compaction](changes/add-ole-container-compaction/proposal.md) copies
  every live stream and logical CFB metadata item unchanged.
- [PPT storage-wrapper recompression](changes/add-ppt-ole-record-recompression/proposal.md)
  preserves every decoded nested CFB byte.
- [Initial OfficeArt recompression](changes/add-officeart-payload-recompression/proposal.md)
  has an implemented, opt-in EMF/WMF slice. Raster images remain unchanged;
  populated BIFF8 workbooks and many Word picture layouts remain outside its gate.
- Canonical openspec/specs is currently empty. The proposals below use uniquely
  named ADDED requirements and reference the pending baseline changes. Integrate
  the implemented baseline first; do not populate canonical specs with this plan.

## Delivery order and dependencies

| Order | Change | Scope | Prerequisites |
| --- | --- | --- | --- |
| 1 | [extend-doc-xls-officeart-coverage](changes/extend-doc-xls-officeart-coverage/proposal.md) | Populated BIFF8 workbooks, Word formatting and floating/mixed picture layouts | Initial OfficeArt and strict OLE contracts |
| 2 | [add-officeart-raster-recompression](changes/add-officeart-raster-recompression/proposal.md) | Lossless PNG IDAT and JPEG entropy optimization | Initial OfficeArt; expanded coverage for newly supported host layouts |
| 3 | [add-ole-embedded-payload-recompression](changes/add-ole-embedded-payload-recompression/proposal.md) | Qualified DOC/XLS embedded files and CFB objects | Strict OLE and verified child packers; expanded host coverage where needed |
| 4 | [add-officeart-image-deduplication](changes/add-officeart-image-deduplication/proposal.md) | Byte-identical BLIPs in fully resolved shared picture stores | Expanded host/reference coverage |
| 5 | [extend-ole-host-format-support](changes/extend-ole-host-format-support/proposal.md) | Strict compaction profiles for MSG, VSD, PUB, MPP, MSI and HWP 5 | Strict OLE verifier and native writer |
| 6 | [add-hwp-stream-recompression](changes/add-hwp-stream-recompression/proposal.md) | Exact decoded-byte recompression of qualified HWP 5 streams | HWP host profile from order 5 |
| 7 | [add-ole-maximum-compression-effort](changes/add-ole-maximum-compression-effort/proposal.md) | Bounded stronger Zopfli trials through existing ultra selection | Initial OfficeArt; raster codec only if delivered |

Coverage and the initial PNG/JPEG codecs can be developed independently after
approval; release claims for their combination require the same end-to-end
fixtures. Additional host profiles can be qualified independently, one at a time.
The existing named-profile proposal is not a prerequisite for using the existing
ultra option; named-profile integration waits for that proposal's delivery.

## Shared acceptance rules

Each change defines its own allowed representation changes and independent
verifier. Strict OLE stream equality and the existing exact PPT decoded-storage
contract remain unchanged. A combined candidate needs verification of the union
of its declared changes; independent candidate selection alone does not authorize
composing transformations.

All new operations use shared root budgets, private staging, cancellation,
dry-run, destination/backup policies and physical-file savings thresholds. Report
coverage, fallback reasons, stream savings and actual final file savings
separately. Benchmarks use pinned real, licensed fixtures; synthetic allocation
holes or deliberately weak encodings are reported as controls. No proposal
promises a compression percentage before measurement.

Parent category/member selections remain effective for descendants. A new OLE
option cannot silently re-enable a disabled image/child category or permit loss.
Raster contracts preserve metadata regardless of a generic stripping preference;
these proposals do not introduce an OLE metadata-removal mode.

## Deferred scope

CFB version 4, BIFF5/older Word formats, additional template/CAD/Works families,
MSP/MST/MSM installer variants, PNG/JPEG alternatives such as DIB/TIFF/PICT,
generic opaque-stream carving, application resaving, DOCX/XLSX conversion,
fast-save/history deletion, preview removal, image downsampling, lossy JPEG and
VBA rewriting are outside these proposals. They need separate preservation and
compatibility decisions. Text, cells and formula streams are never wrapped in
arbitrary DEFLATE under their existing names.

## Review and validation

Review proposal.md, design.md, tasks.md and the delta specification in each
directory. Validate each change with openspec validate <change-id> --strict
--no-interactive. The full portfolio is now approved for implementation. Record delivery evidence
and incomplete application/platform checks before marking tasks complete.

## Implementation evidence (2026-10-05)

All seven runtime directions have bounded implementations. See
[qualification report](../dev/ole/PORTFOLIO.md) and
[public API measurements](../dev/ole/qualification-portfolio.json).
Original/compaction/selected sizes, worker usage and 31 passive LibreOffice
comparisons are recorded separately from synthetic controls. Individual tasks
track verified implementation and remaining original-corpus qualification.
No proposals are archived or claimed deployed; Office/Hancom and remote native
platform limitations are explicit.

The [1,055-file original coverage census](../dev/ole/CORPUS.md) pins each source
identity and rejection reason. It qualifies an additional populated worksheet
with bounded tertiary fill flags and four new unchanged DOC/XLS fixtures. The
broader original inheritance/duplicate-store acquisition tasks remain open.
The census now includes 277 unchanged LibreOffice, 11 larger POI originals and
56 distinct NPOI variants.
Seven additional DOC/XLS fixtures pass complete public API and page comparisons;
five demonstrate file-sector savings beyond strict compaction. Four qualified
original dedup graphs have no removable entries. The remaining inheritance gap
concerns original piece-PRM-owned operands, not ordinary inherited font/language
formatting. Style-owned picture locations are forbidden by MS-DOC UpxChpx and are
now rejection cases; the previous positive synthetic example was invalid.
