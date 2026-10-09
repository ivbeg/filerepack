## Context

An ODT rewrite moved mimetype away from the first entry. Broad ZIP aliases and the attempted CAB writer are not evidence of complete container preservation.

This design covers R09, R14, A6, B2, C1 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add ODF/EPUB entry-order, compression, and header policies.
- Goal: Separate generic ZIP routing from wrappers, integrity manifests, and signatures.
- Goal: Gate each advertised container writer on proven round-trip capability.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Deliver ODF/EPUB mimetype preservation first, then audit package aliases with format-specific fixtures.
2. Signed inputs default to unchanged; checksummed formats require explicit supported manifest updates and validation before member edits.
3. Treat CAB as unavailable unless the selected backend can create and verify CAB. Do not silently convert it to another family.
4. USDZ and executable/application aliases need their own format rules; do not inherit generic compressed-ZIP guarantees.

## Risks / Trade-offs

- Capability probes and validators can be unavailable on some platforms; advertise unavailable/experimental status rather than a successful no-op.

## Migration Plan

1. Keep recognizable extensions for discovery while distinguishing read capability from safe rewrite support.
2. Document unsupported/protected aliases and preserve original bytes instead of promising every alias works.

## Verification

- Verify ODF/EPUB requirements with package-level assertions and representative application fixtures.
- Probe actual available writer commands; a backend E_NOTIMPL must never be called successful repacking.

## Early A6 implementation notes (2026-10-03)

A package policy is inspected before extraction or nested edits. ODF/EPUB input
requires a first stored `mimetype`, at offset zero, with no local extra field;
source central extra fields on that member are conservatively unsupported too.
The existing manifest-preserving ZIP writer explicitly stores `mimetype`, even
if the selected backend compressed it. Final verification checks layout and
required references again, as well as hashes of all protected control members.

ODF checks its root MIME declaration, canonical/unique manifest paths and existing
members. EPUB checks container rootfiles, publication manifests and spine identity
references inside the archive. `mimetype`, `META-INF/*` and EPUB publication
control documents bypass deep walking and retain exact bytes. Signed, encrypted,
rights-managed or malformed packages, ODF checksums/unknown manifest records,
remote EPUB references and control files above 4 MiB skip before extraction.
Other aliases retain their existing behavior pending the separate audit.

The policy follows the layout rules in [ODF 1.3 packages](https://docs.oasis-open.org/office/OpenDocument/v1.3/OpenDocument-v1.3-part2-packages.html)
and [EPUB 3.3 OCF ZIP containers](https://www.w3.org/TR/epub-33/#sec-zip-container).
The current standards-shaped fixtures and native package/reference checks do not
establish full conformance or application rendering. Application-produced corpus
checks, CAB/WIM capability gates, registry support tables and other protected
container formats remain separate tasks.
