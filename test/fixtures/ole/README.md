# Real legacy Office fixtures

Copied from Apache POI at the exact commit recorded in provenance.json. That file
records each source URL, SHA-256, byte count and Apache-2.0 license. LICENSE and
NOTICE come from the pinned repository's legal directory. Files retain their
original bytes, including malformed/unsupported/protected regression samples.

Only qualified unprotected profiles reach the writer. Canonical unsigned VBA
projects in SimpleMacro.doc, SimpleMacro.xls and external_name.xls are preserved
opaquely. HeaderWithMacros.doc has no VBA project storage. SquareMacro.xls is
skipped for unsupported root metadata. SimpleMacro.ppt now qualifies as one
single-edit presentation with a canonical unsigned compressed VBA project;
controlled variants retain the same project bytes in an uncompressed wrapper.
Tests inspect protected samples without executing macros or activating embedded
objects. Renderer qualification uses a private profile with macro security level 3
and only eligible fixtures. The earlier 23-file corpus has 15 eligible profiles and eight
protected/unsupported samples; host-signature regressions additionally use
controlled property indices and Word StwUser tables.

Record recompression qualification adds two real PPT embedding variants at the
same pinned commit: `testPPT_oleWorkbook.ppt` qualifies for ordinary compaction but
its record type 1058 is outside the rewriting allowlist; `ppt_with_embeded.ppt`
has unqualified VBA flags and is skipped. `ole2-embedding-2003.ppt` qualifies for
the initial macro-free trailing-storage rewrite profile. Controlled zlib level
0/1 wrappers change only the encoding of its two embedded storages. They exercise
compression opportunity and do not represent savings on additional real files.

OfficeArt feasibility adds `vector_image.doc` and `SimpleWithImages.xls` from the
same pinned Apache POI commit. The current corpus contains 25 real files, 17 of
which qualify for ordinary compaction. These new fixtures contain one EMF and
WMF/EMF plus unchanged JPEG/PNG, respectively. The development-only experiment
also uses the existing `word_with_embeded.doc` and `ole2-embedding-2003.ppt`.
Its controlled wrappers are derived encodings, not extra real corpus members.
The experiment does not enable DOC/XLS content recompression in the CLI.
