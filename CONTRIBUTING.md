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

CLI behaviour is documented in [docs/cli.md](docs/cli.md).
