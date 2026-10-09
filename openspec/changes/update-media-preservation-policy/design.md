## Context

Default MP4 commands use CRF 18 even with lossy false, and automatic FFmpeg selection does not retain every track/attachment. Image aliases and metadata stripping need a presentation/fidelity contract.

This design covers R08, B6 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Add explicit remux/lossless/lossy video modes and migrate default behavior safely.
- Goal: Probe and explicitly map streams, chapters, dispositions, tags, and covers.
- Goal: Preserve image frame counts, bit depth, transparency, color/presentation, and cursor semantics.
- Goal: Propagate parent image/quality/metadata settings to embedded assets.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Default video performs supported stream-copy remuxing or remains unchanged; --video-mode selects remux/lossless/lossy. --lossy grants lossy permission, and --wmv-lossless remains a compatibility alias for lossless. Conflicting modes fail before writes.
2. Probe streams structurally and explicitly map all supported content; if the destination cannot represent a required stream, decline instead of dropping it.
3. Lossless image/media claims include frame/sample equality and required presentation metadata. Incidental metadata may follow keep-meta, but orientation/color semantics cannot silently change.
4. CUR/APNG/high-bit-depth aliases preserve their own semantics; a generic ICO/PNG backend is used only when verified for that input.
5. Nested XML/SVGZ/PDF/audio covers inherit effective categories, metadata, quality, and resource context rather than hardcoding pack_images true.

## Risks / Trade-offs

- Lossless remuxing may save little and explicit lossy permission changes established video behavior; explain the migration and compare corpus results.
- Some metadata/streams cannot be preserved by available tools; a visible unsupported outcome is preferable to silent loss.

## Migration Plan

1. Document new default and video-mode precedence; retain old public helper aliases and explicit lossless controls.
2. Replace Keep Metadata Flag with the complete critical/incidental policy; keep keep_meta false as the default incidental-metadata choice.

## Verification

- Use independent probes/decoders for stream inventories and frame/sample equality.
- Assert omitted critical content rejects publication and default video never selects lossy encoding implicitly.
