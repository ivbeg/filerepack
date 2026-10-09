## MODIFIED Requirements

### Requirement: Versioned OLE maximum effort mapping
The system SHALL preserve current default OLE codec effort and use existing ultra
selection for a documented versioned stronger mapping. Version 1 SHALL retain
original/zlib9/Zopfli15 trials with the existing 1 MiB Zopfli15 cutoff and add a
qualified Zopfli50 trial up to 2 MiB. Hard root/payload limits SHALL NOT increase.

#### Scenario: Ultra on an eligible metafile
- **WHEN** ole_recompress and ultra are true for a qualified payload within the maximum cutoff
- **THEN** the additional bounded trial is considered and effective mapping/version are reported.

#### Scenario: Ultra without a content mode
- **WHEN** ultra is selected without enabling OLE content recompression
- **THEN** no payload transformation is activated and strict compaction behavior remains unchanged.

### Requirement: Best verified OLE trial retention
The system SHALL retain original and best default representations while trying
maximum effort, independently verify each new result and select the smallest
fully verified physical candidate. More iterations SHALL NOT be assumed to
produce a smaller representation or justify discarding an earlier result.

#### Scenario: Stronger trial is larger
- **WHEN** a Zopfli50 result is larger than the retained default result
- **THEN** the default result remains available and the larger result is not selected.

#### Scenario: Extra encoded saving has no physical effect
- **WHEN** a stronger stream result produces the same allocated file size
- **THEN** no extra file saving is claimed and the existing best baseline is retained.

### Requirement: Effort compatibility and cumulative bounds
The system SHALL propagate resolved effort through existing caller/worker paths,
keep optional encoders optional, and charge all trials to one root budget. It
SHALL NOT enable loss, change image quality or apply mappings to unqualified
framing/codecs. Timeouts/cancellation SHALL retain the existing no-publication
root policy and report incomplete effort accurately.

#### Scenario: Optional Zopfli is absent
- **WHEN** ultra is requested without a qualified binding
- **THEN** original/zlib9 processing remains available and diagnostics state that the stronger trial was unavailable.

#### Scenario: Maximum trial exceeds the root deadline
- **WHEN** cumulative trial work exhausts the deadline
- **THEN** owned work stops, scratch is cleaned and no interrupted maximum result is published.

### Requirement: Measured maximum effort evidence
The system SHALL report mapping/encoder versions, eligible/completed/skipped
counts, wall time, memory, accepted-candidate rate and physical gains on the same
pinned real corpus against default and strict compaction. Synthetic weak encodings
SHALL be separated and no unmeasured savings percentage SHALL be promised.

#### Scenario: Maximum effort documentation is published
- **WHEN** users are advised to enable ultra for OLE
- **THEN** guidance includes measured costs/gains and codec/dependency/size limits.
