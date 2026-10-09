## MODIFIED Requirements

### Requirement: Single Compressed Tar Payload

A compressed tar operation SHALL decode exactly the declared outer wrapper, extract the tar members, rebuild one tar payload, and encode that payload with the declared codec. It SHALL NOT insert an extra tar member containing the original tar payload.

#### Scenario: Gzip tar round-trip

- **WHEN** `bundle.tar.gz` contains `document.txt` and is accepted for repacking
- **THEN** the tar payload SHALL contain `document.txt` at the same path and no added `bundle.tar` member

#### Scenario: No deep walking

- **WHEN** a compressed tar is repacked with deep walking disabled
- **THEN** its member layout SHALL remain unchanged while only permitted container recompression occurs

### Requirement: Verified Archive Alias Structure

Archive aliases SHALL select a writer only after their payload type and wrapper structure are known to round-trip. Unsupported or mismatched structures and failed decode/extract/write stages SHALL leave source bytes unchanged.

#### Scenario: Alias differs from assumed wrapper

- **WHEN** a supported-looking suffix contains a different wrapper structure
- **THEN** the system SHALL route using its verified structure or report an unsupported case without publication

#### Scenario: Outer encoder failure

- **WHEN** tar rebuilding succeeds but outer stream encoding fails
- **THEN** the source SHALL remain unchanged and all operation-owned scratch files SHALL be cleaned
