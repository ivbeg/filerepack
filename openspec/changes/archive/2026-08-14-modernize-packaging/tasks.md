## 1. Implementation
- [ ] 1.1 Create `pyproject.toml` with `[build-system]` section (setuptools + wheel)
- [ ] 1.2 Add `[project]` section with name, version, description, authors, license
- [ ] 1.3 Add `[project.dependencies]` listing `typer>=0.9.0`
- [ ] 1.4 Add `[project.optional-dependencies]` for `parquet` and `dev`
- [ ] 1.5 Add `[project.scripts]` entry point for the CLI
- [ ] 1.6 Add `[tool.pytest.ini_options]` configuration
- [ ] 1.7 Add `[tool.mypy]` configuration
- [ ] 1.8 Add `[tool.ruff]` or keep flake8 config in `setup.cfg`
- [ ] 1.9 Simplify `setup.py` to minimal shim or remove entirely
- [ ] 1.10 Update `Makefile` if it references `setup.py` directly

## 2. Validation
- [ ] 2.1 Run `pip install -e .` in a clean virtualenv — verify package installs
- [ ] 2.2 Run `pip install -e ".[dev]"` — verify dev dependencies install
- [ ] 2.3 Run `pip install -e ".[parquet]"` — verify optional dependency installs
- [ ] 2.4 Verify `filerepack` CLI command works after installation
- [ ] 2.5 Run `python -m build` — verify wheel and sdist build successfully
