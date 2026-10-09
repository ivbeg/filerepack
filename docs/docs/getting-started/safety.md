---
title: "Safety"
description: "In-place rewrites, backups, size limits, and files that are never touched"
---
# Safety

filerepack is designed to leave the source file untouched until a candidate is
verified and actually smaller.

## Write path

Encoders write in scratch space. A verified candidate is copied and checked into
a private file beside the destination, then published with `os.replace` for an
existing destination or a no-clobber link for a new one. Direct `pack_*` helpers
use the same publication boundary. Scratch can be on another filesystem; an
`EXDEV` failure never falls back to copying over the original.
A missing `7zz`/`7z` leaves the source archive untouched. Packers must not
unlink user files before a successful rewrite.

Candidates, extraction directories and tool-generated auxiliary outputs belong
to the current operation. Cleanup runs on rejection, dry-run and encoder or
validator exceptions. A pre-existing derived sidecar is refused without being
deleted. This cleanup policy does not establish stronger format preservation:
the remaining data/media preservation work is tracked separately.

## Candidate verification

Every writer must name a structural validator. Unknown keys, missing parsers or
decoders, warnings from the PDF structural checker, failed subprocesses and
truncated candidates refuse publication and log a reason. A recognizable header
is insufficient. Raster validation needs `filerepack[validation]` (Pillow);
media validation needs both `ffprobe` container inspection and complete ffmpeg
video/audio decoding. ZIP reads every member through its CRC check, tar checks
complete blocks and payloads, and other archives use their integrity tester.
Data formats need their respective Python parsers to read the candidate.

Separate source comparisons are enforced for decoded compressed-stream bytes,
JPEG/PNG/GIF/WebP/TIFF decoded frames, Arrow/Feather/ORC schemas, metadata and
ordered values, and lossless PDF objects and streams. Existing archive-manifest,
Parquet, DICOM and native-format checks also remain in use. This does not establish
complete preservation for every other data/image/audio/video writer; their
remaining metadata, stream and frame contracts are still tracked separately.
Unsupported raster decoders (including HEIC/JXL/EXR in a standard Pillow build),
unknown ICNS resources and unsupported high-depth raster modes fail closed.

Some validators cap parser input at 256 MiB, decoded output at 512 MiB and raster
frame count at 4096. Verifier processes have a 120-second timeout and capped
captured output; PDF JSON comparison is capped at 16 MiB. Exceeding these bounds
refuses the candidate. These are local verifier bounds, not a shared operation
budget or a bound on every parser's internal memory allocation.

## PDF protection and candidate policy

Protection inspection runs before image walking, qpdf and Ghostscript, including
PDF-based Illustrator files. Encryption, signature fields, signature/protection
markers anywhere in the object table, and uncertain inspection leave the source
bytes untouched even when lossy options are requested. This inspection detects
protection markers; it does not authenticate a cryptographic signature.

An available qpdf performs structural checks and inspects all PDF objects. With
qpdf absent, pikepdf can inspect protection; lossless publication additionally
requires qpdf 11+ JSON object/stream comparison. Missing verification refuses
rewriting. The source document graph, metadata and decoded streams must match;
object numbers, xref layout, compression and volatile trailer IDs are excluded.
Unsupported stream filters or excessive inspection output refuse acceptance.
JPEG/JPX image replacements also compare decoded sample size, mode and pixels.

Compression evaluates the original, a verified image-walk candidate, and qpdf
results from the original and walked files. It selects the smallest valid result;
an unsuccessful or larger qpdf candidate does not discard a valid walked one.
The original wins ties and larger compression results, including `--allow-grow`.

`--pdf-linearize` adds an explicit linearization constraint. Use `--allow-grow`
if a required linearized result is larger; ordinary savings thresholds still
apply. The flag also applies to a Ghostscript result, with the subsequent qpdf
stage required to preserve that explicitly lossy result. Linearization is never
forced by ordinary PDF compression.

## Discard if not smaller

Output that is not smaller than the original is discarded unless `--allow-grow`.
`--min-savings PCT` keeps the result only if savings are at least that percent.

## Backups and output directory

```bash
filerepack repack contract.docx --backup
filerepack repack contract.docx --backup --backup-dir ./backups
filerepack repack contract.docx --output-dir ./out
filerepack repack contract.docx --output-dir ./out --overwrite
```

`--output-dir` preserves the source. When no candidate passes the savings and
validation checks, the destination receives a copy checked for byte identity
with the source. This does not establish that an already malformed source is
a valid format.

Different existing output/conversion targets are refused unless `--overwrite`
is explicit. This includes the `.mp4` target of video conversion and `.7z` when
RAR writing is unavailable. A required backup is never overwritten, and failure
to create it stops processing. Existing `.bak` files cause a conflict; a custom
backup directory uses fresh names for repeated backups. `--backup-dir` alone
does not enable backups.

Options, path aliases and conflicts are checked before copying or encoding.
Concurrent filerepack operations reserve source/output/backup identities;
another active owner causes a clear conflict. New output files are published
without replacing a file that appears after preflight. Publication uses a
candidate in the destination filesystem; unsupported publication operations
fail while retaining the source.

Source bytes, file identity, link count, mode, mtime and ctime are checked again
after staging and immediately before publication. An existing output must also
remain unchanged even when `--overwrite` is authorized. A concurrent writer
causes a conflict. These checks cannot remove the short race between the final
check and rename/unlink, or coordinate applications that ignore filerepack
reservations. Conversion cleanup rechecks the source before deleting it. If the
source changes after the converted output is published, that output remains
and a cleanup conflict retains the new source bytes.

## Filesystem attributes and links

Published files and backups retain the source's permission mode and mtime.
Extended attributes exposed by the Linux or macOS native APIs are copied and
verified, including binary values and macOS resource forks. Metadata application
or verification failure refuses publication and logs the reason. The default
policy covers the supported attributes; platforms without an xattr API do not
provide an xattr preservation guarantee. `keep_meta` controls format metadata
such as EXIF/ICC separately.

On macOS, a new staging file can receive a protected `com.apple.provenance`
attribute from the system. When the source has no such attribute, publication
retains the exact value observed immediately after staging-file creation. All
source attributes still have to match byte for byte. A provenance attribute
added later, a changed creation-time value, or a different source provenance
value does not receive an exception to verification.

Ownership, native ACLs, birth time, filesystem flags and Windows alternate data
streams are outside this policy. Source reads may update atime. In-place file
symlinks and sources with multiple hard links are refused, including aliases
that resolve to an in-place request. A distinct output can read a linked source
without replacing it. Directory symlink aliases remain supported.

Publication provides atomic visibility when the destination filesystem supports
replace/link. It does not guarantee persistence after a power loss: no file or
directory fsync contract is implemented. The library's `durability="atomic"`
is the only supported guarantee; stronger requests raise `ValueError` before
creating scratch, output or backup artifacts. Network and unusual filesystems
must provide the required publication primitives or the operation fails.

`--dryrun` measures savings in scratch space, leaving source, output and backup
files unchanged and creating no output or backup directories. Scratch space
also holds a private source copy during normal processing, so account for that
additional disk use with large inputs.

## Archive extract limits

`--max-extract-size` skips archive extract if uncompressed size exceeds the
limit (`0` disables). The default is 8 GB, and also 100× the archive size, so
a tiny zip bomb is not fully expanded.

## Files that stay untouched

These are never extracted and rewritten:

- Signed installers: `deb`, `rpm`, `pkg`, `dmg`
- Disc/library archives 7-Zip cannot create: `iso`, `cpio`, `ar` / `a` / `lib`
- OpenType `.otf` fonts (ZIP ODF templates with that extension are packed)
- Encrypted or digitally signed PDFs skip every rewriting path, including qpdf, pikepdf and Ghostscript
- DICOM instances that are signed, non-image, or already compressed

## Related docs

- [Troubleshooting](/getting-started/troubleshooting)
- [Formats](/formats/)
- [CLI shared options](/commands/shared-options)
