## ADDED Requirements
### Requirement: Immutable Default Arguments
Python functions SHALL NOT use mutable objects (dict, list, set) as default argument values. Defaults SHALL be `None` with initialization inside the function body.

#### Scenario: pack_images with no options
- **WHEN** `pack_images()` is called without the `options` parameter
- **THEN** a fresh `{'debug': False}` dict is created for each call
- **AND** modifications in one call do not affect subsequent calls

#### Scenario: pack_images with explicit options
- **WHEN** `pack_images()` is called with an explicit `options` dict
- **THEN** the provided dict is used directly
- **AND** the default is never created or shared
