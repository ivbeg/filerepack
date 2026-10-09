# Change: Investigate and add compatible PyTorch checkpoint recompression

## Why

The survey found 1,189 PT files with 1,424,884,122,248 declared bytes across
11 projects and ten accounts. Three bounded samples contained modern checkpoint
ZIP layouts with 21, eight and six members, all STORED, including `data.pkl`.
No tensors were loaded and no checkpoint compression/read-back was measured.
This is a high-volume experiment candidate, not proof that arbitrary ZIP DEFLATE
is accepted by PyTorch or remains compatible with mmap.

## What Changes

- Add passive classification of verified modern `torch.save` ZIP/ZIP64 checkpoints.
- Establish a reader/ZIP-method/layout matrix before enabling any writer profile.
- Default to `checkpoint_compatibility=preserve-mmap`; retain uncompressed storage
  and supported alignment/layout properties, optimizing only eligible other records.
- Permit storage compression only in an explicitly selected, proven `load-only`
  profile through `--checkpoint-compatibility` and the corresponding library option.
- Preserve pickle and storage bytes exactly without loading user objects.
- If no compatible beneficial writer exists, deliver inspection evidence and skips,
  without registering an advertised checkpoint compression capability.

## Impact

- Affected specs: `pytorch-checkpoint-recompression`.
- Affected code: dedicated checkpoint inspector/packer, protected container policy,
  optional test-only Torch integrations, format registry and CLI option validation.
- Uses archive-member preservation, structural validation, transactions and budgets.
- Initial aliases are `.pt`/`.pth` only with content confirmation; this does not
  register TorchScript, legacy pickle/tar, `.ckpt`, distributed checkpoints or generic `.bin`.
- Status: approved for implementation by the user on 2026-10-04, with a blocking feasibility gate; implementation breadth depends on its result.

## Evidence

- [Survey and checkpoint central-directory probes](../../../dev/format_survey/multisource/report-2026-10-04.md).
- [PyTorch serialization semantics](https://docs.pytorch.org/docs/2.14/notes/serialization.html).

## Current implementation status — 2026-10-07

The user authorized continuing and completing these tasks. Current implemented
scope and remaining qualification are recorded in [tasks.md](tasks.md) and the
[completion audit](../../../dev/quality/completion-2026-10-07.md). Earlier
proposal-stage status text is historical; deployment remains unconfirmed.
