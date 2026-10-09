## MODIFIED Requirements

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
