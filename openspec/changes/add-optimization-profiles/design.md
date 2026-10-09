## Context

Users currently combine compression level, ultra, metadata, quality, worker and extraction settings manually. Named profiles should resolve to reproducible effective options, make effort/time trade-offs understandable, and keep costly inputs within shared budgets without implicitly enabling loss.

This design covers N04 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add `--profile fast|balanced|maximum|preserve` and equivalent library selection with versioned definitions.
- Goal: Resolve profile defaults before explicitly supplied CLI/library overrides; expose effective options and definition version.
- Goal: Add per-input timeout/temp-space and worker/tool-thread controls integrated with the shared resource context.
- Goal: Benchmark profile trade-offs on a fixed corpus without promising unmeasured savings.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Profile version 1 sets effort defaults: fast => compression level 3, ultra false; balanced => level 6, ultra false; maximum => level 9, ultra true; preserve => level 6, ultra false, keep_meta true. Fast/balanced/maximum leave metadata policy at the shared default. Every profile keeps lossy false and requests no JPEG/PNG/PDF lossy quality. Format adapters map effort only to proven supported lossless settings.
2. Resolve baseline defaults, then profile values, then explicitly supplied overrides, then validate the result. Track option provenance so CLI defaults or default-valued dataclass fields do not accidentally override profile values. Provide a typed explicit override mapping/library builder while keeping legacy unprofiled RepackOptions behavior.
3. No profile selected retains existing effort settings. `--ultra` remains an explicit effort override; `--pdf-profile` remains the separate explicit PDF quality control subject to approved media/PDF fidelity policy. A general profile never inserts that flag.
4. Expose `--file-timeout`, `--max-temp-bytes`, and `--tool-threads` alongside existing jobs/extraction settings; normalize finite positive limits and explicit unlimited forms before writes. Allocate per-file limits within root/aggregate budgets, counting encoder threads across concurrent workers.
5. Versions change when profile definitions or adapter mapping semantics change. Include the version and resolved options in outcomes/inspection/audit/resume fingerprints when those consumers are available.
6. Establish corpus baseline before suggesting concrete timeout/temp defaults. Profile effort definitions are fixed as above; resource defaults remain shared documented policy until measurements justify a versioned change.

## Risks / Trade-offs

- Existing default-valued options lose provenance; distinguish explicit overrides from implicit defaults at the API boundary rather than silently letting defaults win.
- External tools have different thread/effort controls; unsupported resource controls must be reported and bounded through process scheduling/deadlines where possible.
- Maximum can cost considerably more time for little improvement; publish measured time/memory/scratch/savings and accepted candidate rate.

## Migration Plan

1. Add versioned definitions, resolution/provenance tests and a library profile builder without changing unprofiled callers.
2. Apply resolved options consistently to nested and standalone adapters and shared process budgets.
3. Document profile version 1, explicit overrides, preservation guarantees, resource controls and measured benchmark results.

## Verification

- Check the exact profile version 1 settings and precedence for explicit false/default-valued CLI and library overrides.
- Verify none of the profiles alone selects lossy video/image/PDF paths and preserve retains requested metadata or explicitly skips incapable writers.
- Exercise nested option inheritance and cumulative worker/tool-thread/temp/deadline enforcement.
- Record elapsed time, peak memory/scratch, accepted candidates and final bytes saved for the same corpus/tool versions.
- Ensure changes to profile definitions or adapters invalidate execution fingerprints where resume is available.
