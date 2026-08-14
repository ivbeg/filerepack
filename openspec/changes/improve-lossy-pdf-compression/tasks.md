## 1. Packer
- [x] 1.1 Add `PDF_PROFILES` and `DEFAULT_LOSSY_PDF_PROFILE = ebook` in `consts.py`
- [x] 1.2 Add `build_gs_pdf_cmd` / `jpeg_quality_to_qfactor` / `normalize_pdf_profile` helpers
- [x] 1.3 `pack_pdf`: lossless still qpdf; Ghostscript when `lossy`, `pdf_profile`, or `jpeg_quality` is set; default profile `ebook`; invalid profile returns `None`
- [x] 1.4 Pass `pdf_profile` and `jpeg_quality` through `_PACKERS` for `pdf` and `ai`
- [x] 1.5 `pack_ai` forwards the new kwargs to `pack_pdf`

## 2. CLI and library
- [x] 2.1 Add `RepackOptions.pdf_profile`
- [x] 2.2 Add `--pdf-profile` to `repack` and `bulk`; reject unknown values at startup
- [x] 2.3 Thread the option through `_build_options`, bulk `job_base`, and `jobs.py`

## 3. Docs and tests
- [x] 3.1 README, `docs/cli.md`, `docs/library.md`, `docs/tools.md`, CHANGELOG
- [x] 3.2 Tests: command flags, default `/ebook`, explicit profiles, jpeg QFactor, CLI validation, dispatch, `pack_ai` forward
- [x] 3.3 `make test` and `make lint`
