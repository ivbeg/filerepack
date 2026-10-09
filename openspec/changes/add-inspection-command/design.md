## Context

Current dry-run performs candidate compression to measure savings. Users need an inexpensive way to learn which operations are eligible, what is missing, and which known protection or destination rules will prevent processing before starting a costly job.

This design covers N01 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add `filerepack inspect PATH --json` for a file or directory with bounded read-only discovery.
- Goal: Describe detected format, available writers/validators, tools/extras, known protection state, destination conflicts, and estimated resource needs.
- Goal: Separate estimates and unknown information from measurements; retain existing dry-run candidate measurement.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Build inspection on the same format registry, normalized options, eligibility policies, destination resolver, and root resource context as repacking. Add a library inspection entry point returning typed records rather than recreating routing in the CLI.
2. Use bounded header/container listing and read-only parser/tool probes; never invoke an encoder, extract a whole payload, or create output/backup/scratch files. A probe requiring extraction is reported as unavailable at inspection depth.
3. Expose detection confidence, protection state (`protected`, `unprotected`, `unknown`), eligibility, blockers, proposed destination, planned operations, and byte/member estimates with provenance. Unknown protection cannot be treated as permission to rewrite.
4. Directory JSON uses a versioned stream of item records and one summary, with bounded discovery and stderr diagnostics. Define and document the envelope before adding fixtures.
5. Inspection exit codes are 0 for a completed inspection even when records describe blocked operations, 1 for invalid invocation or inspection failure, and 130 for interruption. Inspection records do not promise later execution will succeed; revalidate before publication.

## Risks / Trade-offs

- Some formats require full parsing to identify signatures; surface unknown state rather than falsely declaring an input safe.
- Uncompressed size listings may be inaccurate; label estimates and enforce actual budgets during a real operation.
- Inspection may itself encounter malicious compressed headers; bound reading, subprocess output, duration, and recursion.

## Migration Plan

1. Add the command and library result types after the shared capability/outcome/resource contracts exist.
2. Document inspection alongside dry-run with examples showing estimates versus measured candidate savings.
3. Keep existing repack/bulk command names and dry-run semantics; re-check mutable source and destination state during execution.

## Verification

- Use spies and filesystem snapshots to prove inspection starts no encoder and creates no source/output/backup/scratch files.
- Cover known signed/encrypted packages, missing tools/extras, unsupported aliases, ambiguous headers, and pre-existing destination conflicts.
- Validate JSON parsing with diagnostics and interrupted directory discovery; verify bounded reader/probe behavior.
- Compare inspected routing/options against later repack planning without requiring estimated savings to equal measured results.
