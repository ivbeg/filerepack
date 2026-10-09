## MODIFIED Requirements

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
