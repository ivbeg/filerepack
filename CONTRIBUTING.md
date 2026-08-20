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

The documentation site is Docusaurus under [`docs/`](docs/). Source pages live in [`docs/docs/`](docs/docs/).

```bash
cd docs
npm install
npm start          # local preview
npm run build      # production build (broken links fail)
```

From the repository root you can also run `make docs-serve` or `make docs`.

CLI behaviour is documented in [docs/docs/commands/](docs/docs/commands/). Per-format tools and nested walking: [docs/docs/formats/](docs/docs/formats/). External binaries: [docs/docs/tools/](docs/docs/tools/). Update those pages when adding a format or flag.
