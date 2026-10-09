# Versioned bounded effort over existing codecs

## Decisions

### Version 1 mapping

| Selection | Trials |
| --- | --- |
| Default | Original representation, zlib9, qualified Zopfli15 for decoded payloads up to 1 MiB, matching the current baseline |
| ultra | All default trials, plus qualified Zopfli50 for decoded payloads up to 2 MiB |

The decoded-size cutoff is an effort eligibility threshold, not an expanded hard
decode/memory/file limit. No mode increases the 120-second OLE root deadline or
the per-payload/aggregate ceilings. Version this mapping and include it with
encoder versions in diagnostics and any delivered report/resume fingerprints.
Changing trials/cutoffs later requires another version and benchmark evidence.

Use the existing qualified optional Zopfli binding; absence retains zlib9 and
original representations with an explicit effective-effort reason. Maximum is
best effort under the root budget, not a guarantee every large payload receives
all trials. Apply the existing root timeout/cancellation policy; an exhausted
root operation does not publish partially processed unchecked content. Do not
misreport an interrupted trial as a completed maximum pass.

### Selection and option propagation

Ultra is effort only. Without ole_recompress or another separately enabled
content mode, strict compaction stays the only OLE behavior. Pass resolved effort
explicitly through library/CLI/bulk/archive/worker paths. Default-valued explicit
overrides and any later named profiles follow the named-profile proposal when
that feature is delivered; do not invent a second profile option here.

Preserve originals and the best proven default result per payload; compare every
new trial by actual encoded size and independent decoded equality. More Zopfli
iterations are not assumed to improve every input. Allocate and independently
verify final candidates before applying physical savings thresholds. A larger or
equally sized maximum result cannot replace a better default result.

Apply to EMF/WMF first and to exact-IDAT PNG only after raster delivery. Do not
modify JPEG quantization or enable lossy encoders. PPT storage wrappers/HWP raw
streams keep their current mappings until framing-specific qualification covers
them; this proposal adds no generic raw-stream compression facility.

## Qualification and rollout

Measure fixed originals plus explicit weak-encoding controls; include cutoff
boundaries, incompressible payloads, absent/mismatched optional bindings and
timeouts. Report eligible/processed/skipped counts, encoder settings, peak memory,
wall time and incremental physical bytes against strict compaction and default.
No change to default effort; rollback removes the maximum mapping. Existing
preservation verifiers are unchanged and must accept every selected trial.

## References

- [Current codec and measured baseline](../add-officeart-payload-recompression/design.md)
- [Versioned named profiles](../add-optimization-profiles/specs/optimization-profiles/spec.md)
- [Root resource contract](../add-operation-resource-budgets/specs/operation-budgets/spec.md)
