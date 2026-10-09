## Context

SPSS system files combine a dictionary with case records. `$FL2` supports raw or
bytecode case data; `$FL3` uses zlib block framing over a case stream. Zlib variants
have additional reader requirements, so a smaller ZSAV is not a transparent SAV rewrite.

## Goals / Non-Goals

- Goals: change supported native compression while retaining dictionary and exact case data.
- Non-goals: dataframe import/export, recoding strings, changing missing values or formats,
  dropping variables/cases, automatic SAV-to-ZSAV conversion, or universal SPSS version claims.

## Decisions

1. Phase zero identifies full header/dictionary/data framing, integer and float
   representations, mode and dictionary extensions on complete files. Test real
   compression opportunities and trusted PSPP/SPSS-compatible readers. An absent
   compatible beneficial rewrite leaves inspection support only.
2. Initial numeric profile supports IEEE-754 with tested endian handling. Decode case
   elements without converting through Python floats/strings: preserve exact eight-byte
   numeric/string elements, signed zero, supported NaN/system-missing bit patterns,
   padding, very-long-string segments and case order. The bytecode encoder uses an
   abbreviated numeric code only when decoding it recreates exactly those bytes;
   otherwise retain a literal element.
3. Retain dictionary records byte-for-byte: names/labels, value labels, user missing
   definitions, encodings, measurement/display formats, weights, multiple-response
   definitions and extension payloads. Reject unknown records if the parser cannot
   prove their boundaries or whether their references remain valid. Do not normalize
   dictionary metadata via a generic reader/writer library.
4. For `$FL2`, raw-to-bytecode is eligible only under native-reader evidence for the
   same system-file kind; update only required compression fields and derive the
   data stream. Already bytecode-compressed files are rewritten only when a smaller
   exact candidate exists. Preserve the remaining header including bias and timestamps.
   No automatic `$FL2` to `$FL3` conversion is proposed.
5. For existing `$FL3`, initially preserve the complete inflated bytecode stream and
   its logical block partition, changing zlib envelopes and required header/trailer
   offsets and lengths. Independently validate block bounds, checksums, indexes,
   case counts and EOF. Do not interpret archive zlib as a whole-file gzip wrapper.
6. A passive decoder distinct from the writer verifies complete dictionary bytes and
   case-element identity under shared budgets. Trusted native-reader fixtures additionally
   compare dictionary semantics and all cases. A related implementation such as ReadStat
   plus pyreadstat is one reader lineage, not two independent implementations.

## Risks / Trade-offs

- The bytecode format can be less effective on arbitrary numeric values; no minimum
  gain is assumed from the survey. Report unchanged and failed files alongside savings.
- Very long strings and metadata extensions complicate structural validation; enable
  only tested profiles and skip unsupported data without removing metadata.
- Proprietary SPSS reader access may limit coverage. Record actual reader versions and
  fixture evidence; a PSPP-only gate does not establish compatibility with every SPSS version.

## Migration Plan

Complete source classification and the feasibility decision before adding any writer
to the supported registry. Enable SAV and ZSAV profiles independently; ZSAV requires
new complete real files since none was found in the survey.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.
