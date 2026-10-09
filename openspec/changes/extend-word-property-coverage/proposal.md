# Change: Extend lossless Word formatting and drawing-property coverage

## Why

The supplied `gov.doc` has qualified inline PNG pictures, but its ordinary
formatting, conditional table styles and shape z-order record prevent discovery.
The user explicitly authorized implementation in this conversation on 2026-10-08.

## What Changes

- Audit and retain additional offset-free character, paragraph and table operands.
- Validate conditional table-style operands, including their nested properties;
  prohibit hidden Data references and picture identity in those operands.
- Admit Word-only scalar protection/shape flags and shape-owned tertiary `dhgt`.
- Admit only empty complex fill/line image defaults; retain nonempty inline-image
  variants outside this profile.
- Keep complete independent preservation, resource and publication gates.

## Impact

- Affected specs: officeart-recompression.
- Affected code: Word and OfficeArt parsers; no new options or encoders.
- Qualification: supplied DOCs are measured locally without redistributing them;
  regressions use existing licensed fixtures and controlled formatting variants.
