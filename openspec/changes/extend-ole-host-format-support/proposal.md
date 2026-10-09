# Change: Add qualified strict compaction profiles for more OLE applications

## Why

The CFB backend could reclaim allocation space for other applications, but dispatch
and eligibility currently cover legacy Word/Excel/PowerPoint only. Adding filename
extensions without version, structure and protection qualification would not prove
compatibility or preservation.

## What Changes

- Add separately qualified CFB v3 host profiles for Outlook MSG, binary Visio VSD,
  Publisher PUB, Project MPP, Windows Installer MSI and Hancom HWP 5.
- Detect each profile from file/container/host structures, not extension alone.
- Audit per-host protection, signatures, compressed/embedded object markers and
  native writer/directory constraints before enabling that profile.
- Reuse strict byte-identical stream/metadata verification and existing candidate
  transactions, root limits, diagnostics and archive-member behavior.
- Publish a version/feature matrix; unsupported variants remain explicit skips.

## Impact

- New capability: ole-host-profiles; reuses ole-compaction without changing the
  original Office profile definitions.
- Affected code: host inspection adapters, extension/format dispatch, native
  capability negotiation, verification, tool hints and documentation/fixtures.
- Priority: P2. Prerequisite: [strict compaction](../add-ole-container-compaction/proposal.md).
- CFB v4, OFT/VSS/VST/MPT templates, MSP/MST/MSM installer variants, Works/CAD,
  HWPX and host payload rewriting are outside this proposal.
- Status: approved by the user on 2026-10-04: “Реализуй все предложения”.

## Validation

For each host, acquire licensed real eligible and unsupported/protected samples;
independently compare complete logical manifests and exercise the relevant
reader/application behavior. Measure actual compaction on originals separately
from synthetic free-sector controls. No row can claim all versions or a savings
percentage from format membership alone.
