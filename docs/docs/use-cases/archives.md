---
title: "Archives"
description: "Walk ZIP, 7z, RAR, and tarballs, then rewrite the container"
---
# Archives

With `--deep` (default), archives are extracted, each inner file is packed, then
the container is rewritten.

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

`.tar.gz` and friends are unpacked so nested files can be optimized, then the
tarball is rewritten. A compressed stream whose payload is a tar (`.gz`,
`.zst`, …) is detected by peeking the first 512 decompressed bytes.

```bash
filerepack repack photos.tar.gz
filerepack bulk ./archives --include-ext tar.gz --progress
```

`--include-ext tar.gz` matches compound names. `--include-ext gz` matches them
too.

## What is not rewritten

Signed installers (`deb`, `rpm`, `pkg`, `dmg`) and ISO/CPIO/AR stay untouched.

See [Safety](/getting-started/safety) and [Formats](/formats/).
