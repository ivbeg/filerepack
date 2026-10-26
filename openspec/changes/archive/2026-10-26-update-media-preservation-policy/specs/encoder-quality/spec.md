## MODIFIED Requirements

### Requirement: Keep Metadata Flag

RepackOptions.keep_meta and --keep-meta SHALL remain available with default false for incidental JPEG/PNG metadata. Critical orientation, color/profile, and other presentation metadata SHALL be retained or losslessly normalized under a verified policy regardless of incidental stripping. With keep_meta true, all supported requested metadata SHALL be retained and unavailable retention SHALL be reported. Tools SHALL NOT be invoked with indiscriminate strip behavior that changes the required presentation contract.

#### Scenario: Default incidental stripping

- **WHEN** lossless JPEG/PNG processing runs with keep_meta false
- **THEN** eligible incidental metadata MAY be stripped while critical presentation information SHALL remain preserved

#### Scenario: Keep metadata requested

- **WHEN** --keep-meta or RepackOptions(keep_meta=True) is supplied
- **THEN** all supported requested metadata SHALL be retained and incapable backends SHALL report unavailable preservation

#### Scenario: Inherited library option

- **WHEN** the library processes nested JPEG/PNG assets with keep_meta true
- **THEN** the nested encoders SHALL receive the effective retention policy
