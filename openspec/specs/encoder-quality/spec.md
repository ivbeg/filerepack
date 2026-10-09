# encoder-quality

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Optional jpegtran for Lossless JPEG
The system SHALL register `jpegtran` as an optional tool (`FILEREPACK_JPEGTRAN`). For lossless JPEG (no `--lossy` / `--jpeg-quality`), the packer SHALL try `jpegtran -optimize -progressive` when available, then existing `jpegoptim`. The smallest valid JPEG that passes commit rules SHALL be kept. Missing `jpegtran` SHALL fall back to jpegoptim-only behavior.

#### Scenario: jpegtran shrinks then jpegoptim
- **WHEN** lossless `pack_jpg` runs and both jpegtran and jpegoptim are available
- **THEN** jpegtran is applied
- **AND** jpegoptim may run on that output
- **AND** the smallest valid result is committed

#### Scenario: jpegtran missing
- **WHEN** jpegtran is not available and jpegoptim is
- **THEN** lossless JPEG uses jpegoptim as today

### Requirement: Optional zopflipng on PNG Ultra
The system SHALL register `zopflipng` as an optional tool (`FILEREPACK_ZOPFLIPNG`). Lossless PNG SHALL keep oxipng/optipng as the default. When `--ultra` is set and `zopflipng` is available, the packer SHALL also try zopflipng and keep the smallest valid PNG.

#### Scenario: ultra PNG with zopflipng
- **WHEN** lossless `pack_png` runs with `ultra=True` and zopflipng is available
- **THEN** zopflipng is tried in addition to oxipng/optipng
- **AND** the smallest valid PNG is committed

#### Scenario: ultra without zopflipng
- **WHEN** `--ultra` is set and zopflipng is missing
- **THEN** lossless PNG still uses oxipng/optipng

### Requirement: Encoder Tool Discovery
The system SHALL list `jpegtran` and `zopflipng` in `filerepack doctor` as optional tools with OS install hints when a package mapping exists. Their absence SHALL NOT make `doctor` exit 1.

#### Scenario: doctor lists new encoders
- **WHEN** the user runs `filerepack doctor`
- **THEN** the table includes jpegtran and zopflipng
- **AND** a missing required archiver is still the only exit-1 condition

### Requirement: Keep Metadata Flag

RepackOptions.keep_meta and --keep-meta SHALL remain available with default false for incidental JPEG/PNG metadata. Critical orientation, color/profile, and other presentation metadata SHALL be retained or losslessly normalized under a verified policy regardless of incidental stripping. With keep_meta true, all supported requested metadata SHALL be retained and unavailable retention SHALL be reported. Tools SHALL NOT be invoked with indiscriminate strip behavior that changes the required presentation contract.

#### Scenario: Default incidental stripping

- **WHEN** lossless JPEG/PNG processing runs with keep_meta false
- **THEN** eligible incidental metadata MAY be stripped while critical presentation information SHALL remain preserved

#### Scenario: Keep metadata requested

- **WHEN** --keep-meta or RepackOptions(keep_meta=True) is supplied
- **THEN** all supported requested metadata SHALL be retained and incapable backends SHALL report unavailable preservation

#### Scenario: Inherited library option

- **WHEN** the library processes nested JPEG/PNG assets with keep_meta true
- **THEN** the nested encoders SHALL receive the effective retention policy
