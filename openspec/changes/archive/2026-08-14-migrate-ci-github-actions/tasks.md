## 1. Implementation
- [ ] 1.1 Create `.github/workflows/ci.yml` with GitHub Actions workflow
- [ ] 1.2 Configure trigger on `push` and `pull_request` to `master`
- [ ] 1.3 Add Python version matrix (3.9, 3.10, 3.11, 3.12)
- [ ] 4.4 Add steps: checkout, setup-python, install dependencies
- [ ] 1.5 Add step to run `pytest --cov=filerepack`
- [ ] 1.6 Add step to run `flake8` (or `ruff`) for linting
- [ ] 1.7 Add step to run `mypy filerepack/` for type checking
- [ ] 1.8 Remove `.travis.yml`
- [ ] 1.9 Update `CONTRIBUTING.rst` if it references Travis CI

## 2. Validation
- [ ] 2.1 Push to a test branch and verify GitHub Actions workflow runs
- [ ] 2.2 Verify matrix jobs run for all Python versions
- [ ] 2.3 Verify workflow passes (fix any failures)
- [ ] 2.4 Confirm `.travis.yml` is removed and no longer referenced
