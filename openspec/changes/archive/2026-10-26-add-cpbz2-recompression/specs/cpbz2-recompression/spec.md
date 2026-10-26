## MODIFIED Requirements

### Requirement: CPBZ2 Legacy Extension Filter Compatibility
The system SHALL retain case-insensitive `cpbz2` and `bz2` extension filters for bzip2-wrapped CPIO inputs after introducing the preserving CPIO container writer.

#### Scenario: Legacy discovery filter
- **WHEN** `.CPBZ2` is discovered with either `--include-ext cpbz2` or `--include-ext bz2`
- **THEN** the input SHALL remain eligible under the current preserving CPIO policy
