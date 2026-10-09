## MODIFIED Requirements

### Requirement: Lossless PDF Stream Walking

For an unprotected PDF on the lossless path (no lossy, PDF profile, or JPEG quality request), available pikepdf support SHALL permit eligible DCT, JPX, and supported Flate/PNG-like image optimization through existing image packers. Rebuilt candidates SHALL preserve decoded image content and required stream attributes and SHALL be evaluated alongside eligible qpdf/original candidates. Missing pikepdf SHALL retain qpdf-only processing for unprotected inputs. Lossy requests SHALL bypass stream walking. Signed, encrypted, or uncertain-protection inputs SHALL skip every rewrite path, including qpdf and Ghostscript.

#### Scenario: Unprotected embedded JPEG

- **WHEN** pikepdf and an image optimizer are available on the lossless path
- **THEN** a valid smaller image/host candidate SHALL be evaluated with qpdf/original alternatives under acceptance rules

#### Scenario: Lossy flags bypass walking

- **WHEN** lossy/profile/JPEG quality selects Ghostscript on an unprotected input
- **THEN** lossless pikepdf walking SHALL not run

#### Scenario: Signed or encrypted input

- **WHEN** PDF protection is detected or cannot be ruled out
- **THEN** stream replacement, qpdf, and Ghostscript SHALL not rewrite the source

#### Scenario: pikepdf unavailable

- **WHEN** pikepdf is absent for an unprotected lossless PDF
- **THEN** eligible qpdf-only processing SHALL remain available
