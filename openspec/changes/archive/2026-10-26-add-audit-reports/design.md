## Context

Console summaries and current JSON/CSV output do not provide a durable explanation of every skipped, failed, nested, or interrupted operation. A local report should let users trace what was attempted, why publication happened, and which tools and policies were used.

This design covers N02 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add `--report FILE` with JSON and streaming JSONL formats for repack and bulk.
- Goal: Persist versioned terminal outcomes and nested member records with settings, tools, validators, timing, source/destination identity, and actual versus predicted sizes.
- Goal: Record partial/aborted completion with bounded memory and explicit local path disclosure and write failure behavior.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Reuse typed outcome events from `update-repack-outcomes`; do not infer statuses from missing PackResult objects. Include run ID, schema version, stable item/member IDs, normalized effective settings, tool versions, validation level/results, elapsed time, and publication state.
2. Use `--report-format json|jsonl`, inferred from `.jsonl` when omitted and JSON otherwise. A JSONL report contains a run header, complete item/member records, and a final completion/abort summary; flush at item boundaries. A truncated final line after a crash is detectable and earlier complete lines remain readable.
3. For JSON, spool event records with bounded memory and atomically publish a complete envelope on orderly completion or cancellation. Preserve a clearly named partial spool if finalization fails; never mislabel it a complete report.
4. Resolve report paths before processing; refuse pre-existing targets by default, input/output/backup aliases, and conflicts with reserved destinations. Exclude report files/spools from discovery.
5. Reports stay local and contain source paths and member names by default. Document disclosure and offer `--report-paths absolute|relative|redacted`; relative paths are scoped to an explicit run root, and redacted records use opaque IDs without path-bearing diagnostic text. A redacted report is not a resume manifest.
6. A requested report write/finalization failure makes the invocation unsuccessful and emits stderr diagnostics while preserving actual processing outcomes. This does not roll back already safely published files. Structured stdout remains independent and parseable.

## Risks / Trade-offs

- Member paths can contain private information; use an explicit documented path policy and scrub free-text errors in redacted mode.
- A process killed during a JSONL write can leave a partial trailing line; readers must distinguish recoverable complete records from a completed job.
- Large jobs require bounded spool/storage and honest report failure outcomes; never conceal disk-full errors behind a successful summary.

## Migration Plan

1. Add schema version 1 and fixtures/readability documentation before exposing flags.
2. Wire single-file and coordinator-owned bulk events through one report sink, keeping existing stdout formats compatible.
3. Document partial report recovery, path disclosure, collision handling, and the effect of report failure on exit codes.

## Verification

- Parse JSON and JSONL reports for all typed statuses, nested members, dry-run predictions, and serial/parallel jobs.
- Inject interruption, process termination/truncated line, disk-full, and final replacement failure; verify partial versus complete state and non-success exit.
- Check bounded report memory across many records and clean machine-readable stdout alongside stderr diagnostics.
- Verify occupied paths, source/target aliases, report discovery exclusion, and redaction of names and path-bearing errors.
