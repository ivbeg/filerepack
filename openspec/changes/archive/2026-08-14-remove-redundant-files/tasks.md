## 1. Implementation
- [ ] 1.1 Remove `bin/filerepack.py`
- [ ] 1.2 Remove `bin/` directory if empty
- [ ] 1.3 Remove `README.rst`
- [ ] 1.4 Remove or `.gitignore` the `build/` directory
- [ ] 1.5 Verify `console_scripts` entrypoint still works after removing `bin/`
- [ ] 1.6 Verify `setup.py` doesn't reference `bin/filerepack.py`

## 2. Validation
- [ ] 2.1 Confirm `filerepack` CLI command still works after removal
- [ ] 2.2 Confirm README.md is the only README format remaining
- [ ] 2.3 Confirm no broken imports or references
