## 1. Implementation
- [ ] 1.1 Identify all `os.chdir()` call sites in `repack_zip_file()`
- [ ] 1.2 Replace each `os.chdir(dir)` + `command` + `os.chdir(self.currpath)` pattern with `subprocess.run(args, cwd=dir)`
- [ ] 1.3 Verify temporary file creation uses absolute paths (not relative to chdir)
- [ ] 1.4 Remove `self.currpath` if no longer needed (or keep for other uses)
- [ ] 1.5 Test parallel processing with `--jobs 2` to confirm thread-safety

## 2. Validation
- [ ] 2.1 Verify no `os.chdir()` calls remain in the production code path
- [ ] 2.2 Run bulk processing on a directory with multiple archives
- [ ] 2.3 Confirm `--jobs` flag works without race conditions
