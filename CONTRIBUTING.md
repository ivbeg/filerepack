# Contributing

The CI qualification matrix covers Python 3.9–3.13. Newer versions require
core, installed-artifact and representative-reader results before being
advertised as tested.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
make lint
```

- Tests live in `test/` and run with pytest.
- ruff: max line length 100, max complexity 15 (`make lint`).
- mypy is run on `filerepack/` and `test/`.
- Do not unlink user files before a successful rewrite. Use the shared candidate lifecycle for user-visible publication.
- New formats go through `dispatch.py:_PACKERS` and `STANDALONE_EXTS` (or `ARCHIVE_EXTS`).

## Packer architecture

`repack.py` coordinates options, destinations, private source copies, nested
walking and progress. `archives.py` owns container extraction, manifests and
writers. Standalone helpers live in `streams.py`, `images.py`, `media.py`,
`documents.py`, `data.py`, `medical.py` and `markup.py`. Existing imports from
`repack.py` and `codecs.py` remain compatibility exports.

Decorate standalone `pack_*` functions with `transactions.guard_packer`, allocate
scratch through `candidates.make_temp`/`make_temp_dir`, and register derived
outputs with `candidates.own_sidecar` before launching a tool. A tool that can
create unpredictable auxiliary files needs an owned directory. Archive work
joins `transactions.candidate_scope`. Cleanup is scoped to allocated paths;
never claim or remove a pre-existing sidecar.

Use typed argv runners in `commands.py`. `capture_command` retains unsuccessful
probe diagnostics; `run_command` accepts only a successful encoder result.
Pass candidates through `candidates.commit_output`, which applies verification,
savings/dry-run policy and destination-local publication. Keep format-specific
preservation checks before that shared acceptance step. Do not import the
orchestrator from a codec. `containers.pack_members` lazily imports the typed
dispatcher to avoid an import cycle.

Keep public keyword/default compatibility in `test/packer_api.json`; change that
snapshot only alongside an explicitly reviewed API change. Fault tests must
patch the implementation module, since compatibility exports bind the same
callable but do not proxy module-level dependencies. Worker payloads/results use
`jobs.JobRequest`/`JobResult`, and callbacks use `models.ProgressHook`; legacy
option mappings are accepted and validated at the API boundary.

## Release artifact checks

Run the artifact validation before treating a build as release-ready:

```bash
python dev/validate_distribution.py
# Or validate one existing sdist and wheel in a directory:
python dev/validate_distribution.py --artifacts dist
```

The `dev` extra includes the build frontend. The validator builds a source
archive and a wheel from that source archive using isolated PEP 517 builds,
checks source support files, runtime-wheel contents, entry points and
BSD-3-Clause license metadata, then installs each artifact into a fresh virtual
environment. It checks public exports, module/console CLI help, dry-run and
source preservation. Tests use support files/configuration copied from the
extracted sdist and runtime code from the artifact installation; the checkout
cannot supply missing imports. The sdist installation runs the full available
suite; the wheel installation runs API/CLI/progress and packer compatibility/fault tests.
Missing optional
Python packages or system tools are reported as explicit skips.

`MANIFEST.in` includes the complete `test/` tree, `.coveragerc`, changelog and
contribution guide in the sdist;
bytecode and OS metadata are excluded. Keep new fixtures/support files under
`test/` and include intended release files in version control. Tests and the
validation script stay outside the runtime wheel. The validator creates temporary
environments, installs declared dependencies and removes its temporary files on
exit. CI runs it on Python 3.9 and 3.13; broader platform/extra coverage is tracked
separately in OpenSpec.

## Documentation

The documentation site is Docusaurus under [`docs/`](docs/). Source pages live in [`docs/docs/`](docs/docs/).

```bash
cd docs
npm install
npm start          # local preview
npm run build      # production build (broken links fail)
```

From the repository root you can also run `make docs-serve` or `make docs`.

CLI behaviour is documented in [docs/docs/commands/](docs/docs/commands/). Per-format tools and nested walking: [docs/docs/formats/](docs/docs/formats/). External binaries: [docs/docs/tools/](docs/docs/tools/). Update those pages when adding a format or flag.

## Coverage, corpus and specification gates

From a repository checkout, run `python dev/check_coverage.py coverage.json`
after `pytest --cov=filerepack --cov-report=json`. Shared transaction/candidate/
destination floors are 90% line coverage, options/report floors are 85%, and
the broad verifier floor is 70% with a future 90% target. Optional subprocess
reader work is not automatically included in parent line/branch coverage.
Preservation assertions and explicit reader qualification remain mandatory.

Run `python dev/check_spec_ownership.py` and strict OpenSpec validation. The
canonical baseline is reviewed working-tree behavior; baseline-audit.json
records historical wording corrections and pending broader requirements.
Confirm deployment separately before archiving. Current fixture, benchmark and
remaining-gate evidence is in `dev/quality/completion-2026-10-07.md`.
