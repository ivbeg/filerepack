## ADDED Requirements

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

### Requirement: Keep Metadata Flag
The system SHALL add `RepackOptions.keep_meta` (default false) and CLI `--keep-meta`. When false, lossless JPEG/PNG stripping stays as today (`jpegoptim --strip-all`, oxipng `--strip safe`). When true, JPEG SHALL use jpegtran `-copy all` and jpegoptim without `--strip-all`, and PNG SHALL not pass oxipng `--strip`. Default CLI behavior without the flag SHALL not change.

#### Scenario: default still strips JPEG
- **WHEN** `pack_jpg` runs lossless without `keep_meta`
- **THEN** jpegoptim is invoked with `--strip-all` (when jpegoptim runs)

#### Scenario: --keep-meta
- **WHEN** the user passes `--keep-meta`
- **THEN** JPEG strip-all is not used
- **AND** jpegtran is invoked with `-copy all` when jpegtran runs
- **AND** oxipng is invoked without `--strip`

#### Scenario: library option
- **WHEN** `RepackOptions(keep_meta=True)` is passed to `FileRepacker.repack`
- **THEN** the JPEG/PNG packers receive `keep_meta=True`

### Requirement: Encoder Tool Discovery
The system SHALL list `jpegtran` and `zopflipng` in `filerepack doctor` as optional tools with OS install hints when a package mapping exists. Their absence SHALL NOT make `doctor` exit 1.

#### Scenario: doctor lists new encoders
- **WHEN** the user runs `filerepack doctor`
- **THEN** the table includes jpegtran and zopflipng
- **AND** a missing required archiver is still the only exit-1 condition
