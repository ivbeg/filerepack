---
title: "Contributing"
description: "Development setup, tests, and documentation updates"
---
# Contributing

The supported CI matrix is Python 3.9–3.13. A newer Python version becomes
qualified after its core, installed-artifact and representative optional-reader
lanes pass; a permissive package version constraint alone is not qualification.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
make lint
```

- Tests live in `test/` and run with pytest.
- ruff: max line length 100, max complexity 15 (`make lint`).
- mypy is run on `filerepack/` and `test/`.
- Stage, verify and accept candidates through `filerepack.candidates`; publish through destination-local `filerepack.transactions` with source/output generation guards.
- Register typed format metadata, dispatch and a preserving validator; run `python dev/generate_capability_docs.py` and the drift tests. Mark unqualified writers unavailable or experimental.

## Documentation

The site is Docusaurus under [`docs/`](https://github.com/ivbeg/filerepack/tree/master/docs).
Source pages live in `docs/docs/`.
The locked Docusaurus release needs Node.js 20+ and npm.

```bash
cd docs
npm ci
npm start
```

From the repository root: `make docs-serve` (dev server) or `make docs` (production build). Broken links fail `npm run build`.

CLI behaviour is documented in [CLI reference](/commands/). Per-format tools and
nested walking: [Formats](/formats/). External binaries: [External tools](/tools/).
Update those pages when adding a format or flag.

See also [CONTRIBUTING.md](https://github.com/ivbeg/filerepack/blob/master/CONTRIBUTING.md)
in the repository root.

## Evidence and specification checks

Run `python dev/check_coverage.py coverage.json` after pytest with
`--cov=filerepack --cov-report=json`. Current minimum line coverage is 90% for
transactions/candidates/destinations, 85% for option validation and reports,
and 70% for the broad verifier module. Raise these floors when the measured
core matrix supports the increase. The verifier target is 90%; optional native
worker tests and independent reader checks remain necessary at any percentage.
Line and branch coverage are collected; isolated child work is not automatically
measured by the parent coverage process.

Run `python dev/check_spec_ownership.py` and
`openspec validate --all --strict --no-interactive` before integrating a change.
Canonical specifications describe verified working-tree contracts. The baseline
audit records historical wording corrections and requirements still pending.
Checklists describe implementation evidence; deployment must be confirmed
separately before archiving a change.

See [quality evidence](/development/quality-evidence) for current qualification
and benchmark limitations.
