## MODIFIED Requirements

### Requirement: Explicit Video Fidelity Modes

Default video processing SHALL use supported stream-copy remuxing or remain unchanged. Lossy encoding SHALL require explicit permission. The system SHALL support explicit remux/lossless/lossy mode selection, retain --wmv-lossless as a lossless compatibility alias, honor container-conversion policy, and reject conflicting modes before mutation.

#### Scenario: Default MP4 processing

- **WHEN** a user requests video optimization without lossy permission
- **THEN** the system SHALL not implicitly use CRF 18 or another lossy encode

#### Scenario: Lossless alias or conflicting settings

- **WHEN** --wmv-lossless selects lossless or incompatible fidelity settings are supplied
- **THEN** the supported lossless contract SHALL apply or validation SHALL fail before writes

### Requirement: Complete Supported Media Inventory

Media rewriting SHALL explicitly preserve all required supported streams, attachments, chapters, dispositions, language tags, metadata, and covers. An incompatible destination or unsupported required stream SHALL prevent publication rather than trigger automatic stream omission.

#### Scenario: Multiple audio tracks and attachment

- **WHEN** a media source has multiple audio tracks, subtitles, and a required attachment
- **THEN** the output SHALL retain their intended inventory or remain unpublished with an unsupported reason

### Requirement: Image and Lossless Media Content Fidelity

Lossless image/media rewrites SHALL preserve decoded pixels/samples, frame count, bit depth, transparency, and critical presentation metadata under the supported format contract. Alias routing SHALL retain cursor hotspots, animation, and format semantics rather than silently converting them.

#### Scenario: APNG or CUR alias

- **WHEN** an animated PNG or cursor is routed through a generic image backend
- **THEN** its frames or cursor semantics SHALL be verified and preserved or the operation SHALL skip

#### Scenario: Changed decoded content

- **WHEN** a structurally valid lossless candidate changes required decoded content or presentation
- **THEN** publication SHALL be rejected

### Requirement: Inherited Embedded Asset Policy

XML/SVGZ/PDF/audio-cover processing SHALL inherit effective category, quality, metadata, and resource settings from the parent operation. Disabled image optimization SHALL not be re-enabled inside a document/audio helper.

#### Scenario: Images disabled in XML or PDF

- **WHEN** parent policy disables images while document processing remains enabled
- **THEN** embedded image encoders SHALL not run

#### Scenario: Requested cover quality or metadata

- **WHEN** parent policy requests quality/ultra/metadata settings for eligible cover images
- **THEN** those settings SHALL reach the nested image adapter
