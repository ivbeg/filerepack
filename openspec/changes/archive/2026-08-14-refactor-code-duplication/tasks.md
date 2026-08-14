## 1. Extract Common Patterns
- [ ] 1.1 Create `_pack_file(filepath, pack_fn, *args)` helper for dryrun/non-dryrun + size tracking
- [ ] 1.2 Create `_dispatch_packer(ext, filepath)` function to replace repeated dispatch blocks
- [ ] 1.3 Extract OS quiet suffix to module constant `QUIET_SUFFIX`
- [ ] 1.4 Extract size calculation to `_calc_savings(insize, outsize)` helper

## 2. Remove Dead Code
- [ ] 2.1 Remove duplicate `pack_jpg_re()` definition (keep first occurrence)
- [ ] 2.2 Remove unused `random.seed()` and `random.randint()` calls
- [ ] 2.3 Remove unnecessary `.encode('utf8')` on file paths in logging calls
- [ ] 2.4 Remove `random` import if no longer needed

## 3. Refactor Packer Functions
- [ ] 3.1 Refactor `pack_jpg()` to use helpers
- [ ] 3.2 Refactor `pack_png()` to use helpers
- [ ] 3.3 Refactor `pack_pdf()` to use helpers
- [ ] 3.4 Refactor `pack_gif()` to use helpers
- [ ] 3.5 Refactor `pack_webp()` to use helpers
- [ ] 3.6 Refactor `pack_svg()` to use helpers
- [ ] 3.7 Refactor `pack_tif()` to use helpers
- [ ] 3.8 Refactor video packers (`pack_wmv`, `pack_mp4`, `pack_avi`, `pack_asf`) to use helpers
- [ ] 3.9 Refactor compression packers (`pack_gzip`, `pack_xz`, `pack_bz2`, `pack_parquet`) to use helpers

## 4. Refactor repack_zip_file()
- [ ] 4.1 Replace 5 repeated dispatch blocks with calls to `_dispatch_packer()`
- [ ] 4.2 Ensure all paths use the new `_run_command()` from shell injection fix

## 5. Validation
- [ ] 5.1 Verify line count reduced by at least 40%
- [ ] 5.2 Run full test suite and confirm all pass
- [ ] 5.3 Verify no `os.system()`, `os.chdir()`, or duplicate dispatch blocks remain
