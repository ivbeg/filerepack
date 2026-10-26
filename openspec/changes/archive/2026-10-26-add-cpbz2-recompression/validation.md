# CPBZ2 validation evidence — 2026-10-05

- `python -m pytest test/test_cpbz2.py test/test_formats.py test/test_consts.py -q`:
  75 passed, including all 18 new CPBZ2 cases. Both external bzip2 and the
  standard-library fallback were exercised, along with nested ZIP processing.
- `venv/bin/python -m pytest -q --tb=short`: 1934 passed, 159 skipped in 126.00s.
  This is the project's configured virtual environment. An earlier full run
  with system Python lacked optional OLE/image dependencies and failed unrelated
  cases; the configured-environment run passed.
- `venv/bin/python -m ruff check filerepack test dev/validate_distribution.py`:
  all checks passed.
- `venv/bin/python -m mypy filerepack test dev/validate_distribution.py
  --ignore-missing-imports`: no issues in 129 source files; unused optional-module
  configuration notes only.
- `git diff --check`: passed.
- `openspec validate add-cpbz2-recompression --strict`: passed.

The generated newc fixture is 1,025,024 decoded bytes and contains a directory,
a regular file, a symbolic link and two hard-link entries with explicit uid,
gid, modes and timestamps. Independent system `cpio -it` accepted the fixture
and listed every member (exit status 0). Its bzip2 size decreased from 10,342
bytes at level 1 to 2,313 bytes at level 9. This is a fixture result, not a
general savings estimate; publication tests require exact decoded-byte equality.

CPIO contents are opaque to the recompressor. No CPIO extraction, member
transformation, format conversion, new dependency or deployment is included.
