# Change: Recompress qualified embedded OLE records in legacy PPT

## Why

The implemented OLE compactor preserves every live stream byte, so it cannot
improve DEFLATE data inside PowerPoint's compressed embedded-object records.
A measured experiment on `ole2-embedding-2003.ppt` saves another 512 bytes with
Zopfli after ordinary container compaction; its embedded DOC/XLS bytes and
rendered slide remain identical. This is evidence for a narrow capability,
not a representative compression ratio.

## What Changes

- Add an explicit `--ole-recompress` / library `ole_recompress=False` option for
  eligible PPT/POT/PPS. The default retains the existing stream-byte contract.
- Initially support macro-free, unsigned, unencrypted, single-edit files whose
  uniquely referenced embedded DOC/XLS storage atoms form the final object block
  immediately before their persist directory and user edit. Qualify standard
  record/extension variants before accepting them; skip unknown layouts.
- Re-encode RFC1950 DEFLATE without changing a single decoded embedded-storage
  byte. Retain an original wrapper when no encoder improves it. Nested CFB
  compaction, linked objects, ActiveX, VBA recompression and history removal are
  outside this change.
- Update the selected record lengths, affected persist offsets, the user edit's
  persist-directory offset and Current User's current-edit offset. Retain every
  other record, stream, object identity and directory field.
- Add a separate preservation verifier for this mode, leaving the strict `ole`
  verifier intact. Reject reader disagreement, incomplete reference accounting,
  unintended changes, malformed wrappers and operation-budget violations.
- Extend the optional native writer with two explicitly named PPT stream
  replacements, produced in private scratch space. Require independently checked
  intent and candidate manifests before the shared transaction can publish.
- Use zlib level 9 as the portable baseline and a qualified optional Zopfli
  pass for stronger compression, bounded in a killable worker. Preserve Python
  3.9+ support; the measured Zopfli 0.4.3 binding itself requires Python 3.10+.
- Apply the existing dry-run, savings, output, backup, archive-member and
  filesystem-metadata policies to the fully verified candidate.

## Impact

- Affected specs: new `ppt-ole-recompression`; preserves the pending
  `ole-compaction` contract and coordinates with shared verification, budget,
  CLI/worker and archive-member propagation.
- Expected code: `filerepack/ole.py`, a dedicated PPT transformation/verifier,
  verification registration, `tools/ole-compactor`, option propagation, tests,
  optional dependency metadata and Office documentation.
- Pre-approval work is limited to specification research and the fixture-bound
  development experiment in `dev/ole/ppt_record_pilot.py`. It has no dispatch,
  publication or runtime integration. Results are in
  `dev/ole/qualification-ppt-records.json`; see `design.md` for the exact contract.
- Approval status: approved by the user's “Подтверждаю” on 2026-10-04. The
  compaction design deferred record-level rewriting to this separate change;
  runtime implementation is now authorized under `openspec/AGENTS.md`.
