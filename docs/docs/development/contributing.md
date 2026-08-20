---
title: "Contributing"
description: "Development setup, tests, and documentation updates"
---
# Contributing

Python 3.9+ is required.

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
- Do not unlink user files before a successful rewrite; packers must write to a temp path and `os.replace`.
- New formats go through the `_PACKERS` registry and `STANDALONE_EXTS` (or `ARCHIVE_EXTS`).

## Documentation

The site is Docusaurus under [`docs/`](https://github.com/ivbeg/filerepack/tree/master/docs).
Source pages live in `docs/docs/`.

```bash
cd docs
npm install
npm start
```

From the repository root: `make docs-serve` (dev server) or `make docs` (production build). Broken links fail `npm run build`.

CLI behaviour is documented in [CLI reference](/commands/). Per-format tools and
nested walking: [Formats](/formats/). External binaries: [External tools](/tools/).
Update those pages when adding a format or flag.

See also [CONTRIBUTING.md](https://github.com/ivbeg/filerepack/blob/master/CONTRIBUTING.md)
in the repository root.
