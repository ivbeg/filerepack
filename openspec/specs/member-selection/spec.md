# member-selection

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Normalized Member Exclusion Patterns

The system SHALL provide repeatable `--exclude-member PATTERN` exclusions matched case-sensitively against normalized POSIX logical names relative to each archive root. `*` SHALL match within a segment, `**` across segments, and `?` one non-separator character; whole paths SHALL be matched and trailing-slash patterns SHALL exclude the directory subtree. Patterns SHALL apply at every nested archive root without depending on extraction paths.

#### Scenario: Recursive directory exclusion

- **WHEN** a quoted `assets/**` pattern matches members at an archive root and a nested archive root
- **THEN** matching members are excluded from optimization with stable logical identities

#### Scenario: Platform-independent names

- **WHEN** archives contain hidden, Unicode, option-like names or literal ZIP backslash characters
- **THEN** matching follows the documented logical naming rules across platforms
- **AND** unsafe extraction ambiguity is reported instead of silently renaming a member

### Requirement: Excluded Member Payload Preservation

Excluded members SHALL retain their decoded payload bytes and required member metadata. Safe outer storage recompression MAY proceed, but all manifest, specialized layout, protection, checksum and validation rules SHALL remain mandatory. A writer unable to preserve excluded payloads SHALL skip the rewrite.

#### Scenario: Outer archive still shrinks

- **WHEN** an archive has excluded members and other eligible compression work
- **THEN** the rebuilt candidate may be accepted only when excluded payload hashes/required metadata are unchanged and the full manifest validates

#### Scenario: Protected package is selected

- **WHEN** selection requests work inside a signed or integrity-protected package
- **THEN** selection does not bypass protection policy or authorize an invalid package

### Requirement: Independent Category and Optimization Depth Policy

The system SHALL provide allow/skip selection for image, audio, video, document and data families with explicit denial taking precedence, and a maximum optimization depth where the root is depth 0. Legacy `--no-images`/`pack_images=false` SHALL continue disabling image/audio/video work and embedded image processing. Selection SHALL propagate to archive and virtual nested assets and SHALL NOT relax security extraction/decode/depth limits.

#### Scenario: Disable only video

- **WHEN** a user skips the video category without the legacy broad no-images flag
- **THEN** image and audio processing remain eligible while video receives a selection-skip outcome

#### Scenario: Legacy flag overrides allowlist

- **WHEN** a user allows the image category but also uses no-images
- **THEN** image/cover/data-URI/PDF-image processing remains disabled

#### Scenario: Depth boundary restricts walking

- **WHEN** max-depth is 1 for a root archive containing a nested archive
- **THEN** direct members may be optimized but descendants inside that nested archive are not optimized
- **AND** all validation and resource/security depth checks still run

#### Scenario: Embedded asset policy is inherited

- **WHEN** an audio/XML/PDF host is eligible but embedded images are excluded by category or depth
- **THEN** the codec may perform permitted work while excluded images remain untouched and reasons use stable member identities
