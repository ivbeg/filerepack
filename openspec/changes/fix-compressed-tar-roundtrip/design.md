## Context

The installed 7zz reproduced a tar.gz rewrite containing `bundle.tar` instead of the original `document.txt`. Extraction currently decodes a wrapper into a tar file and then re-tars that file.

This design covers R02, A2 from the repository review. Dependencies and affected capabilities are listed in [proposal.md](proposal.md).

## Goals / Non-Goals

- Goal: Represent decode, tar extraction, member optimization, tar rebuild, and stream encoding as explicit stages.
- Goal: Preserve tar member layout in both deep modes.
- Goal: Audit compound suffixes and aliases against their actual wrapper structure.
- Non-goal: implement unrelated roadmap changes or introduce a hosted service/plugin framework.

## Decisions

1. Keep wrapper decoding separate from member extraction; the archive family records the payload type and outer codec.
2. Retain `--no-deep` as disabling nested optimization, never as changing archive layout.
3. Use family-specific fixtures to determine gem/crate/unitypackage routing rather than blindly treating each as gzip-wrapped tar.
4. Decode gzip/bzip2/xz/LZMA with streamed standard-library readers and optional wrappers with their decoder executables. Decode Unix compress through stdin so aliases such as .taz do not depend on a .Z input filename. Verify the final encoded stream by decoding it and comparing the resulting tar's full intended manifest before publication.
5. A RubyGems-built fixture confirms that .gem is plain tar; leave its checksummed inner payload bytes untouched during outer rewriting. Crate/unitypackage fixtures cover their gzip/tar member layout, not application-level package integrity. Unix-compress .taz and all advertised compound wrapper stages have round-trip coverage with explicit optional-tool skips.

## Risks / Trade-offs

- An alias correction may reveal unsupported writers; report the limitation and preserve the source.

## Migration Plan

1. Keep compound suffix filters and public packer calls compatible.
2. Adopt shared manifests once fix-archive-member-preservation is available; validate this staged path independently.

## Verification

- Compare decoded member names, types, links, and preserved payloads before and after each wrapper.
- Explicitly skip optional-codec tests when tools are absent.
