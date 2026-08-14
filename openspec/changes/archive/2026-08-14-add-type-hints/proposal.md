# Change: Add Type Hints to repack.py

## Why
The `utils.py` module has complete type hints but `repack.py` (the core module at 2,156 lines) has zero type annotations. This makes the code harder to understand, prevents static analysis tools from catching bugs, and increases the learning curve for new contributors.

## What Changes
- Add type hints to all function signatures in `repack.py`
- Add type hints to the `FileRepacker` class methods and attributes
- Use `typing` module for complex types (e.g., `List`, `Dict`, `Optional`, `Callable`)
- Run `mypy` as part of CI to enforce type correctness going forward

## Impact
- Affected specs: `code-quality`
- Affected code: `filerepack/repack.py`
- **BREAKING**: None — type hints are purely additive and optional at runtime
