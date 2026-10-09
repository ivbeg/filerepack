## Context

One `.mat` extension covers incompatible storage models. Compression is available
in v7; v7.3 uses HDF5. The observed Level-5 header does not by itself distinguish
every MATLAB release or validate the full file.

## Goals / Non-Goals

- Goals: preserve matrix representations and dialect while optimizing existing compression.
- Non-goals: load/save through dataframe or MATLAB object conversion, introduce compressed
  elements into formerly uncompressed files, or treat every MAT file as generic HDF5.

## Decisions

1. Use bounded signature/header and element traversal. Parse normal and small-data
   tags, endianness, compressed framing, element sizes and format-specific padding.
   Reject inconsistent/truncated records, invalid zlib streams, ambiguous trailing
   bytes, and initially unsupported nonzero subsystem offsets. Do not assume every
   compressed element has ordinary eight-byte padding; test the format's rules.
2. Preserve the 128-byte Level-5 header and raw unaffected elements. Recompress only
   existing `miCOMPRESSED` streams, updating their encoded sizes and required framing.
   Compare decoded element bytes in order, including array flags, names, dimensions,
   sparse indexes, real/imaginary payloads, cell/struct content and opaque object records.
   Unsupported inner structures are skipped unless the passive validator can establish
   complete framing without executing class constructors.
3. Do not use `scipy.io.loadmat` followed by `savemat` as the production transformation:
   object conversion is unnecessary for changing a zlib envelope. SciPy can serve as
   an additional reader for its supported fixture subset, not a universal MATLAB oracle.
4. v7.3 is a separately enabled profile. Preserve the MATLAB user block byte-for-byte,
   HDF5 object and region references, dimensions, MATLAB attributes and object aliases.
   Generic `h5repack` success is insufficient. Require the HDF5 semantic verifier plus
   trusted MATLAB read-back evidence for the advertised subset.
5. v4 and Level-5 files without supported compressed elements return unchanged with a
   specific no-compatible-recompression reason. Do not increase the reader floor by
   inserting new `miCOMPRESSED` elements or selecting `-v7.3` implicitly.

## Risks / Trade-offs

- The survey has only two content probes from one project; acquire more origins before
  interpreting gains. Report unsuccessful/unchanged files with successful candidates.
- Class-specific objects and subsystem offsets complicate framing and offsets; preserve
  opaque bytes only when structural validation proves their placement remains valid.
- MATLAB is not a routine CI dependency; retain reproducible trusted fixture manifests,
  commands and independently recorded native-reader results with explicit coverage gaps.

## Migration Plan

Deliver Level-5 existing-compressed-element support first. Enable v7.3 separately
after the hierarchical-data change passes its gates. Missing validators leave the
source unchanged; rollback removes the affected profile registration.


## Implementation note — 2026-10-04

The implemented profile and deliberate coverage limits are recorded in
[validation.md](validation.md). Native operations run in an owned supervised worker,
and verification consumes the same root-operation budget as candidate generation.
This is a scoped implementation of the format guarantees; the separate generic
resource-budget roadmap is not declared complete.
