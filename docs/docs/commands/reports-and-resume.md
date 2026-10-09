---
sidebar_position: 5
---

# Reports and resume

```bash
filerepack repack capture.warc.gz --report run.jsonl
filerepack bulk ./input --jobs 2 --report run.json --report-paths relative
filerepack bulk ./input --manifest run.manifest
filerepack bulk ./input --manifest run.manifest --resume
```

Reports are local version 1 documents independent of stdout `--json` and `--csv`.
`--report-format json|jsonl` defaults to JSONL for `.jsonl`, JSON otherwise. The
parent directory must exist; existing report files and aliases to inputs,
outputs, backups or logs are refused. Report files and their spools are excluded
from input discovery.

JSONL contains a run header, terminal item and member events, and a completion
summary. Item details include bounded tool/worker evidence and structural or
preservation checks, including rejected checks. Known executed tools receive
read-only version probes after processing, cached by executable generation; an
unavailable or unidentified version is explicitly null. Isolated workers record
loaded library versions. Arguments and input paths are not collected as command
evidence. More than 128 distinct evidence events is marked truncated.
Each event is flushed separately. A crash may truncate the final line;
complete earlier lines remain recoverable. JSON spools the same events with
bounded memory and publishes `{"schema_version":1,"events":[...]}` atomically.
A failed finalization retains a `.partial-UUID.jsonl` spool. `complete` describes
whether scheduling finished; item statuses still identify individual failures.

Statuses are `replaced`, `unchanged`, `skipped`, `unsupported`, `failed`,
`predicted`, and `cancelled`. Events distinguish actual publication from staged
archive-member edits and dry-run predictions. A rejected outer candidate does
not claim that its staged member savings were published.

Reports disclose absolute local paths by default. `--report-paths relative`
uses the input directory (or single file's parent). `redacted` replaces path and
member identities with run-specific opaque identifiers, removes detailed
diagnostics and path-bearing settings, and retains reason codes. Relative paths
can disclose locations outside the run root. A redacted report is not a resume
manifest. Report write failures cause a non-success exit; already published
files retain their actual outcomes.

`--manifest` maintains a separate private checkpoint. Its version 1 format is
JSONL: a header, completion entries and a footer containing entry count and a
SHA-256 checksum. A coordinator lock prevents simultaneous writers. Checkpoints
are atomically replaced on the manifest filesystem. Malformed, incomplete or
incompatible checkpoints are refused before dispatch.

`--resume` verifies streaming SHA-256 identities of current sources and outputs,
effective settings, destinations, package/policy versions, toolchain identities,
Python version and optional-library versions/absence. Installing or updating a
reader/encoder extra invalidates a previous completion. In-place entries compare against post-publication source bytes.
Distinct outputs require both source and output to match. Timestamps and sizes
alone never authorize reuse. Invalidated entries return to normal destination
safety rules; a stale output is not overwritten without `--overwrite`.

Only completed `replaced` and `unchanged` outcomes can be reused. Reports mark
reused completion with `reused: true`, `published: false`, and zero new savings.
Failed, cancelled, predicted, unsupported and skipped items are processed again.
Dry-run can read a checkpoint and never persists new completion. A publication
may finish before a checkpoint failure: the previous complete checkpoint stays
valid, and a later invocation safely re-plans missing completion entries.

Converted in-place inputs can be reused through their discovered output filename
only when the historical source is still absent and the output digest and
execution fingerprint match. A recreated source invalidates that completion.
Current discovery and size/extension filters are applied before reuse.

After a hard process crash, a manifest lock can remain. Confirm that its owning
process has ended before removing that lock; preserve the last complete manifest.
Do not promote a partial checkpoint or infer completion from a published output.

If the result spool cannot persist another row, bulk stops submitting work and
drains the bounded outstanding jobs into an emergency in-memory tail. Prior
complete spool rows and those terminal outcomes remain available; the invocation
exits unsuccessfully. Disk-backed checkpoint updates currently rewrite the
complete checkpoint, so very large runs can have substantial checkpoint I/O.

Single-file exit codes are 0 for accepted/unchanged/intentional-skipped work,
1 for failed/unsupported work or application validation failures, and 130 for
interruption. Bulk exits 1 for fatal, fail-fast or persistence failure; a batch
that continues after item failures exits 2. Argument-parser usage errors also
exit 2. Dry-run predicts acceptance and records `published: false`.
