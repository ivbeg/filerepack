## MODIFIED Requirements

### Requirement: Qualified DOC PNG refiltering
The system SHALL qualify static, noninterlaced 8-bit PNGs in audited inline and
floating DOC pictures for filter selection using exact unfiltered samples. It
SHALL preserve all non-IDAT chunks, IHDR, palette/index identity, alpha and
invisible colors, complete Word formatting/references and unselected picture
bytes. It SHALL reuse bounded optional encoder execution and independent final
host verification. Sequential compact identities SHALL reserve five decode
passes per selected sample workload and retain the existing DOC 64 MiB aggregate
bound and unchanged root resource limits. Other PNG layouts and XLS SHALL retain
their existing exact-filtered contract.

#### Scenario: Qualified Word picture uses better row filters
- **WHEN** ole_recompress selects a qualified inline or floating Word PNG
- **THEN** a smaller refiltered candidate MAY be accepted only after exact sample,
  metadata and whole-host verification
- **AND** all consumers SHALL resolve to the same picture and formatting.

#### Scenario: Optional encoder changes a hidden sample or metadata
- **WHEN** an encoder changes a sample, IHDR, palette or source metadata
- **THEN** changed samples/header SHALL reject its candidate and only validated
  IDAT MAY be used with restored exact source metadata
- **AND** verified earlier representations SHALL remain available.

#### Scenario: Optional encoder is absent or reaches its local ceiling
- **WHEN** qualified oxipng is absent, invalid or reaches its optional trial ceiling
- **THEN** earlier verified encodings SHALL remain usable with a diagnostic
- **AND** actual root exhaustion or cancellation SHALL still refuse publication.

#### Scenario: Word picture workload exceeds its reservation
- **WHEN** a PNG exceeds the deterministic aggregate/root selection allowance
- **THEN** its encoded bytes SHALL remain exact
- **AND** every actual decode and process SHALL retain the root resource guards.
