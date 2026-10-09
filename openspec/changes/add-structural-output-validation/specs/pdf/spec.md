## MODIFIED Requirements

### Requirement: Whole File PDF Protection Gate

Signed, encrypted, or uncertain-protection PDFs SHALL remain byte-for-byte unchanged under the default policy. Protection SHALL be checked before any pikepdf, qpdf, or Ghostscript rewrite. The system SHALL report the protection reason; lossy/profile/quality flags SHALL NOT bypass the gate.

#### Scenario: Protected PDF with lossy flags

- **WHEN** a signed or encrypted PDF is requested with lossy/profile settings
- **THEN** no rewriting path SHALL run and source bytes SHALL remain unchanged

#### Scenario: Protection cannot be determined

- **WHEN** available inspection cannot establish that a PDF is unprotected
- **THEN** the operation SHALL fail closed without rewriting
