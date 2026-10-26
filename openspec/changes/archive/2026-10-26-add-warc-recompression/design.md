## Research

`warcio.recompressor.Recompressor.load_and_write` iterates `ArchiveIterator` and
writes every record through `WARCWriter(gzip=True)`. If that raises, its fallback
decodes all gzip members into a temporary file and retries the iterator.
`GzippingWrapper` creates a fresh `zlib.compressobj(9, DEFLATED, 31)` for each
record. The writer can reserialize WARC/HTTP headers, compute missing digests,
recalculate Content-Length and convert ARC to WARC.

Primary sources inspected on 2026-10-05:
- https://github.com/webrecorder/warcio/blob/master/warcio/recompressor.py
- https://github.com/webrecorder/warcio/blob/master/warcio/warcwriter.py
- https://github.com/webrecorder/warcio/blob/master/warcio/archiveiterator.py
- https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/

## Decisions

Filerepack adopts record-level gzip compression, but independently implements
the framing parser so the decoded input bytes remain exact. Headers are bounded,
Content-Length determines opaque payload boundaries, and CRLF framing is strict.
Supported records have WARC 1.0/1.1 versions, valid field names, and unique,
nonempty WARC-Type, WARC-Record-ID, WARC-Date and Content-Length fields. Unknown
fields and record types remain opaque. Folded headers are preserved.

Source gzip decoding supports concatenated members and whole-file compression.
A streaming zlib decoder validates trailers and rejects truncation or trailing
garbage. Candidate verification additionally requires exactly one complete WARC
record per member. SHA-256 covers the complete decoded stream and record count.
The writer never alters payloads or digest headers, including revisit records.

Format budgets account cumulatively for parsing, writing and verification, with
bounded chunks, capped headers and cooperative timeout/cancellation checks. The
ordinary transaction layer handles source snapshots, metadata, backups, dry-run,
output collisions and minimum savings. Plain conversion uses destination planning;
nested plain files retain their name and bytes instead of changing member types.

Adjacent indexes are detected using full filename, `.warc` stem and basename
variants, including compressed `.cdx.gz`/`.cdxj.gz`. A distinct output can be
created while retaining an indexed source, provided the output is not indexed.
Indexes in other directories or remote catalogues cannot be discovered; users
must rebuild those themselves. Automatic index mutation and Zstandard are outside
this change.

## Qualification evidence

Local Python 3.13 verification on 2026-10-05 used warcio 1.8.1 as an independent
reader. `warcio` is a development-only dependency so CI runs the interoperability
test; WARC recompression itself has no optional runtime dependency.

Four real upstream samples from
https://github.com/webrecorder/warcio/tree/master/test/data were downloaded into
a temporary directory, rewritten, parsed with `ArchiveIterator`, and compared
by the fully validated decoded-stream SHA-256 and record count:

| Sample | Source bytes | Result bytes | Records |
| --- | ---: | ---: | ---: |
| `example-iana.org-chunked.warc` | 8,831 | 3,255 | 3 |
| `example.warc.gz` | 3,816 | 3,816 | 6 |
| `example-resource.warc.gz` | 1,779 | 1,779 | 3 |
| `example-bad-non-chunked.warc.gz` | 2,113 | 3,649 | 6 |

Every output retained exact decoded bytes and was readable by warcio. Upstream
`Recompressor.load_and_write` produced 3,341 bytes for the first sample; the
preserving writer retained the original headers rather than normalizing them.
The compressed examples were measured with growth enabled: default savings
policy retains optimized or smaller whole-file gzip sources. These small
examples establish interoperability, not a general savings estimate.

- 58 WARC tests cover framing, payload preservation, member seeking, generic
  gzip routing, conversion/collisions, nested handling, indexes, dry-run,
  savings, metadata, resource budgets and cancellation during verification.
- Focused integration suite: 535 passed, 5 skipped.
- Full suite: 1,900 passed, 159 skipped.
- Global Ruff and mypy checks passed; the documentation site builds successfully.
