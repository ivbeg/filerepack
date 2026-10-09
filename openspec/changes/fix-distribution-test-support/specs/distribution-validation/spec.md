## MODIFIED Requirements

### Requirement: Complete Source Distribution Test Suite

Source distributions that include tests SHALL include all supporting modules, fixtures, initialization, and test configuration required to collect and execute them without imports from the checkout. Runtime wheels SHALL remain limited to runtime package contents.

#### Scenario: Extracted source artifact

- **WHEN** a source distribution is built and extracted outside the checkout
- **THEN** test collection SHALL succeed with its own fixtures/helpers and declared test dependencies

#### Scenario: Runtime wheel contents

- **WHEN** the runtime wheel is inspected
- **THEN** test-only helper modules SHALL not be installed as runtime package modules

### Requirement: Installed Artifact Smoke Validation

CI SHALL build and validate an installed wheel and extracted source distribution outside the checkout import path before release readiness is asserted. Package exports, CLI entry points, and license metadata SHALL match the declared project contract.

#### Scenario: Checkout masks omissions

- **WHEN** an installed-artifact smoke check runs
- **THEN** imports SHALL resolve to the artifact installation rather than the repository

#### Scenario: License metadata

- **WHEN** the built artifact is inspected
- **THEN** its license declaration SHALL identify BSD-3-Clause using the selected backend's supported metadata format
