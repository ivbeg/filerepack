## Context

The built source distribution includes tests but omits conftest, package initialization, DICOM fixtures, and the new local helper. Collection fails although the wheel/sdist build succeeds.

This design covers R15, A7 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Include all supporting test modules and configuration in source artifacts.
- Goal: Add build/extract/collection and installed-wheel smoke checks.
- Goal: Align license metadata with BSD-3-Clause using a compatible backend.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Keep tests out of the runtime wheel, but package the complete test suite and support modules in the sdist.
2. Build and test outside the repository import path so the checkout cannot mask missing support files.
3. Use an explicit source inclusion policy and a verified backend supporting the SPDX license expression while retaining supported Python versions.

## Risks / Trade-offs

- Local untracked helpers are not released automatically; ensure intended support files are tracked when implementing the release change.

## Migration Plan

1. Retain package name, entry point, optional-extra names, and supported Python range.
2. Do not publish a release as part of this proposal's validation.

## Verification

- Assert test helper files are present in the sdist and absent from the runtime wheel.
- Run artifact validation using fresh temporary environments with required test dependencies.

## Implementation notes (2026-10-03)

`MANIFEST.in` grafts the complete `test/` tree, includes `.coveragerc` and the
artifact validator, changelog and contribution guide, and excludes bytecode/OS metadata. Package discovery still
selects `filerepack*`, so test/development support is not installed in the runtime
wheel. This explicit inclusion avoids relying on setuptools' automatic
`test/test*.py` glob, which omitted the supporting modules; see the
[setuptools source-file rules](https://setuptools.pypa.io/en/latest/userguide/miscellaneous.html).

`dev/validate_distribution.py` builds a wheel from the sdist using isolated
PEP 517 builds, validates archive contents, license bytes/metadata and the console
entry point, then installs wheel and sdist separately into fresh virtual
environments. Runtime smoke checks use Python isolated mode and assert that
imports resolve beneath the environment prefix. Source tests/configuration are
copied into a separate directory with no application source; tests therefore use
the installed runtime and extracted support modules. Both API/CLI/progress wheel
tests and the complete available sdist suite are executed, with explicit optional
integration skips. Artifact inspection occurs before installation, and source
extraction rejects absolute/traversal paths and non-regular member types; native
tar data filters are used where available, with validated extraction on Python 3.9.

SPDX `license = "BSD-3-Clause"` and explicit `license-files = ["LICENSE"]` replace
the deprecated license table/classifier. The backend minimum is setuptools
77.0.3, verified on Python 3.9; support for these fields was introduced in
[setuptools 77](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).
`__license__` uses the same identifier, and the existing license text is unchanged.

CI adds separate artifact jobs on Python 3.9 and 3.13. Local macOS checks passed
both interpreter versions, including fresh installs with current resolver-selected
dependencies. Broader platforms/optional extras, actual remote CI execution,
canonical integration and publishing remain separate work. The validator is
available as `make check-dist` and ships in the source distribution, so downstream
source users can repeat the check without this repository's working tree.
