# Change: Implement the first priority formats from the local audit

## Why

The filesystem and container audit found useful unsupported application formats.
The first batch adds preservation-checked handlers while keeping file extensions.

## What Changes

- Add Mellel ZIP packages, offline SQLite `.vscdb`/`.sqlitedb`, and DuckDB databases.
- Add lossless SWF FWS/CWS and Telegram TGS compression.
- Route validated JSON `.map`, `.har`, `.topojson`, `.gltf` and XML `.rels` aliases.
- Retain publication, dry-run, nested walking and savings acceptance contracts.
- Document conservative subsets and optional DuckDB/Zopfli dependencies.

## Impact

- Affected capability: audited-formats; coordinates with output-validation,
  container-policies and data-preservation pending changes.
- Affected code: routing, package policy, native/data handlers, verification,
  extras, tests and documentation.
- Authorization: on 2026-10-04 the user requested implementation of the most
  useful audit findings after the report recommended this first batch. This
  proposal records that authorized scope; no additional approval is required.
