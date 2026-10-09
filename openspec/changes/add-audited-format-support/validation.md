# Validation evidence, 2026-10-04

- New regression suite: 86 tests passed. Covers extension filters, exact JSON
  tokens, SWF/TGS decoding, invalid inputs, offline database sidecars, implicit
  SQLite row identities, Arrow nested float bits and batch boundaries, optional
  dependency failures, bounds, metadata, dry-run, output, savings rejection,
  candidate corruption, scratch cleanup, early JSON reading bounds and
  database/animation archive members.
- Python 3.9.6 full suite: 1306 passed, 44 skipped (optional integrations/fixtures).
- Python 3.13.7 full suite: 1309 passed, 41 skipped. DuckDB 1.4.2/PyArrow 21.0.0
  were used on Python 3.9; DuckDB 1.4.5/PyArrow 25.0.1 on Python 3.13.
- Ruff and mypy passed; git diff whitespace checks passed.
- Docusaurus build and strict OpenSpec validation passed.
- Fresh wheel and source installations passed import/export/CLI smoke checks
  and extracted tests. The source installation ran 1214 passing tests with
  108 skips; optional format extras were intentionally absent in those clean
  development-only installations. Wheel tests include the new format suite.

## Read-only local sample checks

Two accessible Mellel samples, six DuckDB samples (including list/struct columns),
six SWF samples and six TGS samples passed the supported structural inspection.
Real files were only inspected or processed with dry-run.

TGS dry-run examples shrank from 46,970 to 43,330 bytes, 23,344 to 21,494 bytes,
and 21,104 to 19,554 bytes (about 7-8%). A Mellel dry-run shrank from 24,730,162
to 24,715,679 bytes, preserving all member payloads and metadata. This check
exposed zero ZIP attributes being replaced by ZipFile's default mode; the writer
now restores the exact original attributes and the regression uses this layout.

An already compact real DuckDB sample produced no accepted savings. A generated
deleted-row database shrank from 16,265,216 to 1,323,008 bytes (91.87%), with
catalog and typed value verification. Savings are input-dependent.

No Mellel application rendering, SWF execution or Telegram upload is asserted.
Supported subsets and bounds are documented in docs/docs/formats/index.md.
