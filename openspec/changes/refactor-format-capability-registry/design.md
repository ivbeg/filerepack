## Context

Extension, alias, packer, tool, validator, and documentation tables are separate. Doctor accepts nonexistent overrides as ok and does not reveal write support or Python extras; old Python can silently ignore TOML.

This design covers R14, R15, C1, C5 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Use typed format records for aliases, families, fidelity, required tools/extras, validators, output policy, and tested support.
- Goal: Validate configured executables and expose tool versions plus per-format read/write capability.
- Goal: Generate capability documentation and consistency checks from registry metadata.
- Goal: Make Python 3.9/3.10 TOML fallback a declared tested dependency.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Start with consistency tests then migrate existing tables to typed records; maintain legacy exported constants as derived views.
2. Resolve env/config/PATH precedence as today, but verify executable identity, probe supported versions/capabilities under deadlines, and distinguish extraction from safe writing.
3. Keep plain doctor's required-archiver exit behavior; per-format diagnostics additionally expose unmet extras/validation/writer support without making every optional absence fatal.
4. Declare tomli conditionally for Python below 3.11, or explicitly propose changing supported versions; this proposal retains 3.9+.
5. Doctor diagnostics show optional modules even when tools exist; compatibility version policy is tested, not guessed from tool presence.

## Risks / Trade-offs

- Probes vary by tool/platform; cache only with executable/config fingerprints and avoid stale positive capability results.
- Generated docs must represent experimental/unverified cases explicitly.

## Migration Plan

1. Keep existing environment variable names, extra names, extension filters, install hints, and required-tool semantics.
2. Do not introduce arbitrary third-party plugins or a new loader.

## Verification

- Nonexistent overrides must never report ok; unsupported CAB writers remain unavailable.
- Compare derived aliases/filters with current compatibility fixtures and generated docs.
