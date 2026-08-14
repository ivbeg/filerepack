## 1. Implementation
- [ ] 1.1 Create `filerepack/models.py` with `PackResult` and `RepackSummary` dataclasses
- [ ] 1.2 Export new dataclasses from `filerepack/__init__.py`
- [ ] 1.3 Update all `pack_*()` functions to return `PackResult` instead of `[str, int, int, float]`
- [ ] 1.4 Update `repack_zip_file()` to build and return `RepackSummary`
- [ ] 1.5 Update `process_single_file()` to return `PackResult`
- [ ] 1.6 Update CLI output formatting to access dataclass attributes instead of dict keys/indices
- [ ] 1.7 Add unit tests for dataclass construction and field access

## 2. Validation
- [ ] 2.1 Run full test suite — verify all return value consumers updated
- [ ] 2.2 Verify JSON/CSV output is unchanged (field names preserved)
- [ ] 2.3 Verify no `KeyError` or `IndexError` at runtime
