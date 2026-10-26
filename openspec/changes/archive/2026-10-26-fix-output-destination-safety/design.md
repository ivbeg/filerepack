## Context

The CLI overwrites outputs before rejecting invalid options; conversions can overwrite unrelated targets, and the standalone library ignores `outfile` and modifies its source.

This design covers R04, R07, R15, A4 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Validate and normalize options and identities before backups, copies, or encoding.
- Goal: Centralize CLI/library output and conversion destinations with default collision refusal.
- Goal: Reserve backup/output paths; requested-backup failure prevents destructive work.
- Goal: Define outfile, unchanged-copy, and dry-run behavior.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. A distinct output receives a verified unchanged copy when no improvement is accepted; dry-run creates no output artifacts.
2. Default collisions fail closed; explicit overwrite applies only to requested destinations, never a required backup.
3. Normalize paths and compare filesystem identities, not strings.
4. Validate compression 1–9, JPEG quality 1–100, PNG enum, PDF profile, finite savings 0–100, positive jobs, and nonnegative size/extraction limits. Recognize K/M/G/T with or without B.

### Implemented policy (2026-10-03)

- `validation.py` supplies shared validation for `RepackOptions`, dictionary library requests, CLI preparation and bulk workers. Logging starts after validation and checks that its file does not alias a source/output/backup target.
- `destinations.py` resolves parent-directory aliases, compares existing filesystem identities, plans both the unchanged-copy and converted paths, and reserves source/output/conversion/backup paths before processing. Exclusive-create lock files coordinate processes; path claims use conservative NFC/case folding and existing inode claims cover hardlink aliases. Normal exit releases claims. Abnormal process death can leave stale claims; this implementation fails closed rather than guessing that an owner is dead.
- Required backups are byte-verified copies published without replacement. Default `.bak` collisions refuse processing; custom backup directories choose fresh names. An output/backup identity conflict is rejected before either is created.
- `FileRepacker` processes a private source copy for both standalone and archive inputs. Accepted candidates are copied and verified in the destination filesystem before publication. New destinations use atomic no-replace hardlink publication; unsupported filesystems fail closed. Explicit overwrite/in-place publication uses replacement, with an existing-identity check. Private processing adds scratch disk/I/O; cumulative resource budgets and complete concurrent-source/metadata policy remain separate transaction/resource work.
- No accepted improvement publishes an exact unchanged copy only for a distinct output. Dry-run stages and measures candidates but publishes neither output nor backup artifacts. Accepted conversions report the effective suffix and remove an in-place source only after successful output publication. Distinct outputs retain the source.
- JSON/stream/archive outfile paths are tested directly and via CLI. Video and RAR publication boundaries use controlled codec fixtures; these tests do not establish media/real-RAR codec fidelity.

## Risks / Trade-offs

- Collision refusal changes permissive behavior; provide migration examples and clear conflict messages.

## Migration Plan

1. Keep `outfile`, `--output-dir`, and in-place default behavior.
2. Keep `--backup-dir` as a directory selector requiring `--backup`; correct misleading examples.
3. Introduce reservation primitives here; bulk lifecycle work centralizes worker ownership.

## Verification

- Verify hashes on invalid options, collisions, and backup failure.
- Exercise JSON/stream/archive outfile directly and through the CLI.
