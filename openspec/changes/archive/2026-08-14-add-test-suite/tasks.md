## 1. Setup
- [ ] 1.1 Add `pytest` and `pytest-cov` to dev dependencies
- [ ] 1.2 Create `test/__init__.py` and `test/conftest.py`
- [ ] 1.3 Add `pytest.ini` or configure `[tool.pytest]` in project config
- [ ] 1.4 Create `test/fixtures/` directory with small sample files

## 2. Unit Tests — utils.py
- [ ] 2.1 Test `parse_size()` with various inputs ("1MB", "500KB", "2GB", raw bytes)
- [ ] 2.2 Test `format_size()` with various byte values
- [ ] 2.3 Test `parse_extensions()` with comma-separated and edge cases
- [ ] 2.4 Test `should_process_file()` with size/extension filtering
- [ ] 2.5 Test `create_backup()` creates correct `.bak` file
- [ ] 2.6 Test `output_json()` and `output_csv()` produce valid output

## 3. Unit Tests — consts.py
- [ ] 3.1 Test `SUPPORTED_EXTS` contains expected extensions
- [ ] 3.2 Test `EXT_IMAGE_MAP` covers all OOXML formats

## 4. CLI Integration Tests
- [ ] 4.1 Test `--help` output for both `repack` and `bulk` commands
- [ ] 4.2 Test `repack --dryrun` on a sample file
- [ ] 4.3 Test `bulk --dryrun` on a sample directory
- [ ] 4.4 Test invalid file path error handling

## 5. End-to-End Tests (Optional — requires external tools)
- [ ] 5.1 Test compression of a sample JPEG (requires jpegoptim)
- [ ] 5.2 Test compression of a sample ZIP archive
- [ ] 5.3 Test compression of a sample OOXML document

## 6. Validation
- [ ] 6.1 Run `pytest --cov=filerepack` and verify coverage reports work
- [ ] 6.2 Fix `.coveragerc` source name (currently `filesrepack`, should be `filerepack`)
- [ ] 6.3 All tests pass with zero failures
