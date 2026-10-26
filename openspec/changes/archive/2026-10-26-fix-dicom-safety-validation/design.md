## Context

Synthetic datasets with signatures after Pixel Data or inside sequence items were accepted as packable. Current output verification checks only DICM bytes.

This design covers R05, A5 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Scan the full dataset and all nested sequences for signature elements without decoding large pixels during eligibility inspection.
- Goal: Fail closed on malformed lengths, unsupported syntax, truncation, and parser limits.
- Goal: Verify JPEG-LS output structure, transfer syntax, frames, attributes, and decoded pixels.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. A Pixel Data encounter records eligibility but does not terminate signature scanning.
2. Use bounded sequence-aware parsing; prefer a maintained parser if it can support deterministic optional-dependency behavior and the declared syntaxes.
3. If structural or pixel verification is unavailable, do not publish a merely magic-valid output; report missing verification support.
4. Use synthetic tag fixtures for gate tests and independently decoded unsigned fixtures for real encoder tests.

## Risks / Trade-offs

- Full inspection and pixel comparison add work; stream/seek where possible and apply the shared resource limits when available.
- The test signature sequence is not a cryptographic signature; separately validate realistic signed-file rejection.

## Migration Plan

1. Replace the two existing DICOM requirement blocks after baseline reconciliation.
2. Keep .dcm/.dicom/.dic routing, eligible transfer syntaxes, optional tool fallback, and unconditional lossless DICOM policy.

## Verification

- Assert encoders are never invoked for protected/malformed/limit-exceeded inputs.
- Assert unsupported or invalid candidates preserve original bytes.

## Implemented policy (2026-10-03)

`filerepack/dicom.py` performs seek-based structural inspection with one shared
100,000-element/item budget, 64 sequence levels and 4 MiB of File Meta. It
checks sorted unique dataset tags, File Meta boundaries, explicit VR headers,
even bounded value lengths, defined/undefined sequence items and pixel
encapsulation. Pixel Data does not stop inspection; signatures in any parsed
item prevent encoding. Implicit VR uses pydicom's maintained dictionary.
Unknown private item-shaped values are scanned conservatively; undefined UN
and opaque UN sequences are rejected rather than guessing their encoding.

`filerepack/dicom_verify.py` requires the optional `dicom` extra (pydicom,
NumPy, pyjpegls) before encoding. Candidate verification requires JPEG-LS
Lossless `.80`, the same frame/image attributes, decoded pixels in every frame,
all non-encoding dataset attributes including private/nested values, SOP
identity, the preamble and non-encoding File Meta attributes. Decimal string
values also retain their spelling to avoid numeric-wrapper rounding. Allowed
changes are root pixel encoding/offset tables/padding, group lengths and File
Meta implementation/version bookkeeping; an encoder application title may be
added if absent. A changed existing application title is rejected.

All DICOM aliases use `verify_output(..., source_path=original)`; source-free
verification returns false. Existing `has_dicm_magic` remains identification
only. Parser, attribute, pixel and unavailable-verifier failures retain the
source, and encoding always remains lossless regardless of image quality flags.
GDCM receives `--jpegls --use-dict` to retain known sequence VRs from implicit
inputs. DCMTK's `dcmcjpls` cannot decode RLE; that backend fails safely and
RLE recompression needs GDCM.

Inspection never decodes pixels. pydicom 3 uses its raw frame iterator for
comparison; Python 3.9 resolves to pydicom 2.4 and compares complete decoded
arrays. Global decode/memory/scratch budgets remain `add-operation-resource-budgets`
work. Tests use synthetic, non-clinical unsigned images, plus realistic
signature-macro structure with placeholder certificate/digest bytes. They
establish protected-file rejection, not clinical IOD or cryptographic signature
validation. Color-image, clinical-corpus and broader platform evidence remains
separate quality-gates work.

References: [DICOM sequence encoding](https://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_7.5.html),
[pydicom frame iterator](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.pixels.iter_pixels.html),
and [pydicom 3 Python requirement](https://pypi.org/project/pydicom/3.0.1/).
