## ADDED Requirements
### Requirement: Type Annotations
All functions and methods in the `filerepack` package SHALL have type annotations on all parameters and return values.

#### Scenario: pack_jpg function
- **WHEN** reviewing the `pack_jpg()` function signature
- **THEN** it specifies types for all parameters (e.g., `filepath: str`, `quality: int`)
- **AND** the return type is annotated (e.g., `-> Tuple[str, int, int, float]`)

#### Scenario: FileRepacker class
- **WHEN** reviewing the `FileRepacker` class
- **THEN** all instance attributes have type annotations
- **AND** all method parameters and return types are annotated

### Requirement: Static Type Checking
The project SHALL run `mypy` as part of the CI pipeline to enforce type correctness.

#### Scenario: Type error detection
- **WHEN** a type error is introduced (e.g., passing `str` where `int` is expected)
- **THEN** `mypy` reports the error before the code is merged

#### Scenario: CI pipeline
- **WHEN** a pull request is opened
- **THEN** the CI runs `mypy filerepack/` and fails on any type errors
