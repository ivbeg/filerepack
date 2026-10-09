## 1. Implementation

- [x] 1.1 Reproduce collection errors from an extracted sdist outside the checkout.
- [x] 1.2 Define complete source inclusion for test package/helpers/configuration.
- [x] 1.3 Build and install the wheel in isolation and test root exports/CLI help.
- [x] 1.4 Collect and run appropriate tests from the extracted sdist with no checkout import fallback.
- [x] 1.5 Update BSD-3-Clause metadata and compatible backend constraints; add artifact CI gates.

## 2. Verification and documentation

- [x] 2.1 Assert test helper files are present in the sdist and absent from the runtime wheel.
- [x] 2.2 Run artifact validation using fresh temporary environments with required test dependencies.
- [x] 2.3 Run the focused test suite and applicable lint/type/build checks; update affected documentation and changelog with actual behavior.
- [x] 2.4 Validate this change with `openspec validate fix-distribution-test-support --strict`.

## 3. Integration and rollout

- [x] 3.1 Reconcile the implemented canonical baseline through `update-quality-and-specification-gates` before integrating/archiving the delta; record remote CI, release and deployment status separately.

Local verification on 2026-10-03: the original extracted sdist failed collection
with five import errors, omitting `test/__init__.py`, `conftest.py`, `helpers.py`,
`dicom_fixtures.py` and `package_fixtures.py`. Explicit source inclusion now retains
the complete test/support tree, coverage configuration and validation script;
the runtime wheel contains only application modules and distribution metadata.

Fresh artifact pipelines on macOS/Python **3.9 and 3.13** each passed **40 installed
wheel API/CLI/progress tests**, source collection and **653 installed-sdist tests,
38 explicit skips**. Both environments install only the declared development
extra; missing Parquet/DICOM integrations account for the optional skips. Runtime
imports resolve to fresh artifact installations and test support resolves to the
copied extracted suite, with no checkout fallback. Public exports, module/console
CLI help, dry-run and source preservation were verified for both artifact types.

Python 3.9/setuptools **77.0.3** builds passed source/wheel contents, version,
entry-point and BSD-3-Clause metadata checks. License bytes remain unchanged.
Real artifact fault checks rejected a missing helper, a test module leaking into
the wheel and an incorrect license expression. Primary full checks passed
**718 tests, 1 skipped** with DICOM extras, or **682 passed, 37 skipped** in the
existing base environment. Ruff, mypy (runtime/tests/validator), all **25** strict
OpenSpec validations, documentation and isolated distribution builds passed.
CI artifact jobs are configured for Ubuntu Python 3.9 and 3.13; no remote run or
release has been performed. Broader platform/extra coverage remains C2 work.

## Current reconciliation — 2026-10-07

Checked items refer to verified implementation or recorded configuration within
the documented fixture/profile scope. Open items retain their full corpus,
reader, platform or resource requirements. Current evidence and the remaining
gates are recorded in [the completion audit](../../../dev/quality/completion-2026-10-07.md).
Deployment is not confirmed; this change has not been archived.
