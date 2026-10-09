## Context

The review reproduced XML whitespace/CDATA changes and JSON numeric rounding and duplicate-member loss. Parse-and-reserialize JSON and a raw XML gap regex do not satisfy content preservation.

This design covers R03, R06, A3 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Replace JSON parse/reserialize minification with validation plus lexical whitespace removal.
- Goal: Limit XML whitespace removal to contexts proven insignificant; preserve character and lexical regions.
- Goal: Make XML parser safety and encoding support deterministic for standalone and nested inputs.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Retain JSON strings, number tokens, object-member order, and duplicate keys except insignificant external whitespace.
2. Unknown XML vocabularies preserve element text/tail whitespace; removal needs a vocabulary/context rule.
3. Preserve CDATA, entity references, namespace spelling, declarations, comments, and processing instructions; skip unsupported encodings rather than silently converting them.
4. Keep direct helper compatibility (`PackResult` or `None`) until typed outcomes are introduced.

### Implemented policy (2026-10-03)

- JSON validation uses the standard-library parser with string-valued number hooks and a rejecting non-finite hook. The candidate retains the original UTF-8 bytes/BOM and removes only whitespace outside string tokens; no parsed value is serialized.
- XML validation uses Expat namespace and byte-offset callbacks consistently, without an optional `defusedxml` fallback. XML 1.0 in UTF-8/ASCII is supported; DTDs, declared/external entities, invalid `xml:space`, alternate versions and other encodings are rejected. Predefined/character references remain lexical input bytes.
- Quoted attribute values and protected markup are retained verbatim while unquoted tag syntax is compacted. Inter-element gaps are eligible only under the OPC content-types `Types` root (`Default`/`Override`) and package `Relationships` root (`Relationship`). The [ECMA-376 Part 2 schema bundle](https://ecma-international.org/wp-content/uploads/ECMA-376-2_5th_edition_december_2021.zip) defines these element-only structures. Unknown children, nested child content, mixed text, character references, CDATA or inherited preservation disable the relevant removal.
- Existing embedded-image optimization remains available only for complete image data URIs in `href`, `xlink:href` and `src` values; it does not scan character data or protected regions. Candidates are parsed again before publication. Malformed/unsupported input returns `None` and records a debug-level reason; structured public reasons remain part of the outcomes roadmap.
- Real ZIP, DOCX, ODT and EPUB fixtures exercise nested JSON and XML parts, including WordprocessingML, OpenDocument and XHTML text. These checks establish part preservation; package-specific ordering/compression/signature guarantees remain the container-policy change.

## Risks / Trade-offs

- Conservative XML processing may save less space; content preservation takes precedence.

## Migration Plan

1. Replace the completed Chisel JSON/XML requirement blocks after canonical-baseline reconciliation.
2. Retain existing XML aliases and nested dispatch; keep valid scalar JSON roots eligible.

## Verification

- Compare XML text/tail and protected lexical regions and JSON token sequences exactly.
- Verify malformed/unsupported input does not replace sources.
