## 1. Implementation
- [ ] 1.1 Add type hints to `FileRepacker.__init__()` parameters and instance attributes
- [ ] 1.2 Add type hints to all `pack_*()` function signatures (`filepath: str`, return `List]` or `Tuple[int, int, int, float]`)
- [ ] 1.3 Add type hints to `pack_images()` method
- [ ] 1.4 Add type hints to `repack_zip_file()` method (the most complex signature)
- [ ] 1.5 Add `from __future__ import annotations` for forward references
- [ ] 1.6 Add `mypy` to dev dependencies

## 2. Validation
- [ ] 2.1 Run `mypy filerepack/repack.py` with zero errors
- [ ] 2.2 Verify existing tests still pass
- [ ] 2.3 Verify no runtime behavior changes
