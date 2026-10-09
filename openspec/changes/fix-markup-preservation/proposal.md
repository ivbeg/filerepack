# Change: Preserve XML text and JSON lexical values during minification

## Why

The review reproduced XML whitespace/CDATA changes and JSON numeric rounding and duplicate-member loss. Parse-and-reserialize JSON and a raw XML gap regex do not satisfy content preservation.

## What Changes

- Replace JSON parse/reserialize minification with validation plus lexical whitespace removal.
- Limit XML whitespace removal to contexts proven insignificant; preserve character and lexical regions.
- Make XML parser safety and encoding support deterministic for standalone and nested inputs.

## Impact

- Priority: **P0**. Roadmap slice: **A3**.
- Source: [Repository review and improvement plan](../../../dev/docs/repository-review-and-improvement-plan.md); R03, R06, A3.
- Affected capabilities: `xml-json`.
- Affected code: `filerepack/markup.py`, `filerepack/codecs.py:pack_xml/pack_json`, `test/test_markup.py`, `docs/docs/formats/index.md`.
- Status: implemented and verified locally on 2026-10-03; canonical integration and deployment remain open.

## Dependencies

None. This slice can be reviewed and implemented independently.

## Existing requirement baseline

- xml-json: JSON Identification and Minification; XML Identification and Minification — openspec/changes/add-chisel-parity/specs/xml-json/spec.md

These complete replacement blocks use the named completed change as the reviewed baseline because canonical specs are currently absent. Reconcile that baseline through `update-quality-and-specification-gates` before archiving this change; do not copy future requirements into canonical specs prematurely.

## Validation

- Compare XML text/tail and protected lexical regions and JSON token sequences exactly.
- Verify malformed/unsupported input does not replace sources.

## Approval and rollout

The user authorized roadmap implementation on 2026-10-02 and continued it on 2026-10-03. Implementation and local verification tasks are complete. Existing packer entry points retain `PackResult`/`None` compatibility; conservative XML handling and rejected input policies are documented. Canonical integration, deployment and archival remain the separate unchecked rollout task.

Local verification: 445 tests passed, 1 skipped, including 76 new markup preservation cases. Ruff, mypy, strict OpenSpec validation, the documentation build and wheel build passed.

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
