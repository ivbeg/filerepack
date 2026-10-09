---
title: "Archives"
description: "Walk ZIP, 7z, RAR, tarballs and qualified CPIO members, then rewrite the container"
---
# Archives

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten.

Before replacing an archive, filerepack verifies the intended member names,
types, unchanged payloads and supported metadata. Root dotfiles, hidden
directories and empty directories are included. A missing, unexpected or
unverified member rejects the candidate, including during dry-run measurement.
Ambiguous names and unsupported links/types block generic archive rewriting.
CPIO has a separate preserving path that retains linked and special entries
while optimizing eligible regular members.

## ZIP family

```bash
filerepack repack bundle.zip
filerepack repack book.epub
filerepack repack app.jar
```

ZIP-family aliases include EPUB, JAR, APK, AAB, WAR, nupkg, and many design
packages. See [Formats](/formats/).

`bulk` skips top-level `.zip` by default. Use `--no-skip-zip` to include them:

```bash
filerepack bulk ./archives --no-skip-zip --progress
```

## 7z, RAR and WIM

```bash
filerepack repack backup.7z
filerepack repack archive.rar          # becomes .7z if `rar` is missing
```

RAR extraction prefers `unrar` and falls back to `7zz`/`7z`. Writing RAR needs
`rar`; without it an accepted candidate becomes `.7z`. WIM needs a working backend
writer and successful member/metadata verification. CAB is recognized but has no
qualified writer and remains unchanged.

## Tarballs

`.tar.gz` and friends are decoded to one tar payload, whose members are extracted
and optimized before rebuilding and applying the same outer codec. `--no-deep`
disables inner optimization without adding an extra tar layer. A compressed
stream whose payload is a tar (`.gz`,
`.zst`, …) is detected by peeking the first 512 decompressed bytes.

```bash
filerepack repack photos.tar.gz
filerepack bulk ./archives --include-ext tar.gz --progress
```

`--include-ext tar.gz` matches compound names. `--include-ext gz` matches them
too.

`.crate` and `.unitypackage` follow the gzip/tar stages. `.gem` is plain tar;
its checksummed inner archives are kept byte-for-byte unchanged. `.taz` uses
Unix compress (`.Z`), not gzip. Malformed or mismatched wrappers are skipped.
Optional codecs need their corresponding executable for encoding and decoding.

## CPIO and bzip2-compressed CPIO

Raw `.cpio`, `.cpbz2` and `.cpio.bz2` use a native preserving CPIO writer for
old-binary, odc, newc and CRC-newc profiles. With `--deep` (default), safe regular
single-link members use the usual packers. Names, order, permissions, IDs,
timestamps, device numbers and unrelated payload bytes are retained. Symlinks,
hard-link groups and special entries are preserved without being extracted or
optimized. Changed payloads update only the required size/checksum fields and
alignment. Filenames and the original bzip2 wrapper family are retained.

`--no-deep` on compressed CPIO recompresses the outer stream with exact decoded
CPIO bytes. Unsafe or unsupported member layouts also retain their members and
may use that outer-stream fallback. Raw CPIO without accepted member savings
stays unchanged. A generically named `.bz2` takes the CPIO route only when its
bounded decoded prefix has a supported CPIO magic.

```bash
filerepack repack backup.cpio
filerepack repack backup.cpbz2
filerepack repack backup.cpio.bz2 --no-deep
filerepack bulk ./archives --include-ext cpbz2 --progress
```

`--include-ext cpio` and `--include-ext bz2` also match compressed CPIO aliases.
The external `bzip2` executable is optional: the standard-library encoder is used
when it is unavailable. Independent record/payload comparison and complete
bzip2 integrity validation precede publication. Extraction size/ratio and
member-count limits apply.
Dry-run and minimum-savings policies apply; without sufficient savings the
original is retained.

## What is not rewritten

Signed installers (`deb`, `rpm`, `pkg`, `dmg`), CAB and ISO/AR stay untouched.

See [Safety](/getting-started/safety) and [Formats](/formats/).
