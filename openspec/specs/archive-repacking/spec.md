# archive-repacking

## Purpose
Describe the verified current working-tree contract reconciled on 2026-10-07.
Qualification scope and historical corrections are recorded in `openspec/baseline-audit.json` and `dev/quality/completion-2026-10-07.md`. This baseline does not assert release or deployment.

## Requirements

### Requirement: Complete Archive Member Enumeration

Archive writers SHALL enumerate every intended member, including root dotfiles, hidden directories, and empty directories. Member names SHALL be passed using a tool-specific interface that cannot reinterpret them as options.

#### Scenario: Root dotfile alongside visible file

- **WHEN** an archive contains `.hidden` and `visible.txt` and is rewritten
- **THEN** both entries SHALL be present in the candidate

#### Scenario: Option-like member name

- **WHEN** an archive contains a member whose name resembles a writer option
- **THEN** the member SHALL be preserved as a path or the operation SHALL skip without publishing

### Requirement: Archive Member Manifest Preservation

Before publishing a rebuilt archive, the system SHALL compare its member identities, entry types, unchanged payloads, and supported preservation metadata with the intended output manifest. Missing, unexpected, or unsupported ambiguous members SHALL prevent publication.

#### Scenario: Incomplete writer output

- **WHEN** a writer exits successfully but omits an intended member
- **THEN** validation SHALL reject the candidate and preserve the source bytes

#### Scenario: Unsupported duplicate identity

- **WHEN** the selected writer cannot distinguish duplicate or case-colliding member identities
- **THEN** the system SHALL report an unsupported preservation case without replacing the source

#### Scenario: Authorized nested replacement

- **WHEN** a nested packer produces an accepted replacement for a member
- **THEN** the candidate SHALL match the recorded intended replacement while retaining all other members

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
