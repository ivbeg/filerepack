# nested-assets

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Virtual Nested Asset Containers
The system SHALL extract nested assets from host files that are not ZIP/7z/tar archives (audio tags, XML data URIs, PDF streams) into a temporary directory using the asset’s real extension, dispatch existing packers on those files, and reinsert any strictly smaller valid output into a rebuilt host file. If no nested asset shrinks, or the extra/library required to extract is missing, the host file SHALL be left unchanged (codec-only packers may still run). Temp directories SHALL be removed after success or failure.

#### Scenario: Nested image is packed with existing JPEG packer
- **WHEN** a container yields `cover.jpg` and jpegoptim/jpegtran is available
- **THEN** the file is dispatched through the existing JPEG packer
- **AND** a smaller JPEG is reinserted into the host

#### Scenario: Nothing smaller
- **WHEN** every extracted asset is unchanged or larger
- **THEN** the host file is not replaced by the container rebuild

#### Scenario: Missing extra
- **WHEN** the Python extra required to parse the host is not installed
- **THEN** extraction is skipped
- **AND** the host file is unchanged by this step

### Requirement: Audio Cover Art Extraction
The system SHALL, when `mutagen` is importable (`filerepack[media]`), extract attached pictures from MP3, FLAC, Ogg, M4A/MP4, and APE, optimize them with image packers, and write the pictures back into the same tag slot. Other audio metadata frames SHALL be preserved. `--no-images` SHALL skip cover-art extraction. Codec packers (mp3packer, flac, alac, mac) SHALL still run according to existing rules. A single commit SHALL replace the original file.

#### Scenario: MP3 cover shrinks
- **WHEN** `pack_mp3` is given an MP3 with an APIC JPEG and mutagen plus a JPEG tool are available
- **THEN** the cover is optimized
- **AND** the rebuilt MP3 still contains the other ID3 frames
- **AND** a smaller file is committed

#### Scenario: mutagen missing
- **WHEN** mutagen cannot be imported
- **THEN** cover extraction is skipped
- **AND** mp3packer/flac/alac still run if their tools exist

#### Scenario: --no-images skips covers
- **WHEN** `pack_images` is false
- **THEN** cover pictures are not extracted or rewritten

### Requirement: XML Data URI Extraction
The system SHALL extract `data:` URI images from XML/SVG into temporary files, pack them, and write compact data URIs back. Invalid or non-image data URIs SHALL be left as-is.

#### Scenario: SVG with embedded PNG
- **WHEN** an SVG contains a `data:image/png;base64,...` image and a PNG packer is available
- **THEN** the decoded PNG is packed
- **AND** the SVG is rewritten with a smaller data URI when the PNG shrank

#### Scenario: Unknown data URI
- **WHEN** a data URI is not a supported image type
- **THEN** it is not modified

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

### Requirement: Extended Lossless PDF Resource Traversal

On eligible lossless PDFs, the system SHALL discover supported image streams in page resources and recursively referenced Form XObject resources. Traversal SHALL detect cycles, respect shared root budgets and keep all resource references intact. Protected or protection-uncertain PDFs SHALL be skipped according to the whole-file gate before any transformation.

#### Scenario: Image inside a nested form

- **WHEN** an unprotected lossless PDF references an eligible image through nested Form XObjects
- **THEN** the image is discovered and may be optimized while page/form references remain valid

#### Scenario: Cyclic form graph

- **WHEN** form resource references contain a cycle or exceed the traversal budget
- **THEN** walking terminates within limits with an explicit outcome and no invalid candidate publication

#### Scenario: Protected document reaches the extended walker

- **WHEN** a PDF is signed, encrypted or cannot be confidently checked for protection
- **THEN** neither image rewriting nor a fallback transformation bypasses the whole-file protection gate

### Requirement: PDF Flate Image Semantic Preservation

The lossless walker SHALL support explicitly eligible Flate/PNG-predictor sample layouts using PDF-compatible stream encoding. Accepted candidates SHALL preserve exact decoded samples, dimensions, bit depth, color-space/ICC/indexed semantics, Decode/DecodeParms interpretation, masks and transparency. Unsupported filter chains or ambiguous image semantics SHALL remain unchanged with an explicit reason.

#### Scenario: Eligible predictor image

- **WHEN** a supported Flate image uses a known PNG predictor and color layout
- **THEN** the replacement decodes to identical samples and retains its masks/color semantics
- **AND** filter and decode parameters match the newly encoded PDF stream rather than a complete PNG container

#### Scenario: Unsupported image layout

- **WHEN** an image has an unsupported filter chain or ambiguous predictor/color/mask semantics
- **THEN** its stream remains unchanged and the unsupported reason is reported

#### Scenario: Semantic or render validation fails

- **WHEN** a smaller candidate changes decoded samples or rendered output
- **THEN** the candidate is rejected and the source is not replaced

### Requirement: Shared PDF Image Optimization and Final Acceptance

Each shared PDF image object SHALL be optimized at most once per document and retain all references. Work accounting SHALL distinguish unique-object savings from whole-document savings. Rebuilt candidates SHALL satisfy structural validation, lossless image checks, representative pinned-renderer preservation tests, and the shared smallest-valid-candidate/minimum-savings publication policy.

#### Scenario: Multiple pages share one image

- **WHEN** several pages/forms reference the same indirect image object
- **THEN** one optimization attempt is made and every reference still resolves
- **AND** reporting does not multiply that object's savings by reference count

#### Scenario: Smaller stream yields larger document

- **WHEN** image streams shrink but the serialized PDF is larger than an eligible original/qpdf alternative
- **THEN** the larger rebuild is not preferred and the smallest valid eligible candidate determines publication
