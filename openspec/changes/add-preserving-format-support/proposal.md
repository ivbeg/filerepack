# Change: Add file-format support without changing extensions

## Why

The existing JSON, XML, SQLite and Photoshop handlers can cover additional
application formats. Blender, FITS, NRRD and Aseprite also offer lossless internal
compression while retaining their original file extensions.

## What Changes

- Add PSB, GeoJSON, Jupyter Notebook, JSON Lines/NDJSON, QGIS QGZ/QGS/QGD and
  Qt Designer UI routing and preservation checks.
- Add lossless Blender, FITS, attached NRRD and Aseprite recompression with
  decoded-content verification and conservative rejection of unsupported inputs.
- Keep source and output extensions, existing dry-run, size acceptance,
  filesystem preservation, nested walking and publication contracts.
- Document optional dependencies and supported subsets; add real-byte tests.
- LAS/LAZ and conversions that change the extension are excluded.

## Impact

- Affected specs: format-expansion; coordinates with format-capabilities,
  data-preservation, container-policies and output-validation pending changes.
- Affected code: extension aliases, dispatch, markup, binary format handlers,
  QGIS package policy, optional dependencies, tests and documentation.
- Authorization: the user reviewed the candidate list and explicitly requested
  implementation of every listed format except LAS/LAZ on 2026-10-03. This
  proposal records that approved scope; no additional approval is required.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
