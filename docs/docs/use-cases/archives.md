---
title: "Archives"
description: "Walk ZIP, 7z, RAR, and tarballs, then rewrite the container"
---
# Archives

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten.

Before replacing an archive, filerepack verifies the intended member names,
types, unchanged payloads and supported metadata. Root dotfiles, hidden
directories and empty directories are included. A missing, unexpected or
unverified member rejects the candidate, including during dry-run measurement.
Ambiguous names and unsupported links/types leave the archive unchanged.

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

## 7z, RAR, CAB, WIM

```bash
filerepack repack backup.7z
filerepack repack archive.rar          # becomes .7z if `rar` is missing
```

RAR extract needs `unrar`. Rewrite as RAR needs `rar`.

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

## bzip2-compressed CPIO

`.cpbz2` uses the bzip2 stream recompressor at level 9. The complete decoded
CPIO archive remains byte-identical, including member order, headers, links,
permissions, timestamps and padding. Members are not extracted or optimized,
even with `--deep`. The original filename and extension are retained.
The same outer-stream behavior applies to `.cpio.bz2`.

```bash
filerepack repack backup.cpbz2
filerepack bulk ./archives --include-ext cpbz2 --progress
```

`--include-ext bz2` also matches `.cpbz2`. The external `bzip2` executable is
optional: the standard-library encoder is used when it is unavailable.
Complete stream validation and decoded SHA-256 comparison precede publication.
Dry-run and minimum-savings policies apply; without sufficient savings the
original is retained.

## What is not rewritten

Signed installers (`deb`, `rpm`, `pkg`, `dmg`) and ISO/raw CPIO/AR stay untouched.

See [Safety](/getting-started/safety) and [Formats](/formats/).
