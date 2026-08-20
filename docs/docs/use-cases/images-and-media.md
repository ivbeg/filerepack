---
title: "Images and media"
description: "Lossless and opt-in lossy images, video, audio, and cover art"
---
# Images and media

`--no-images` skips this category (including cover art). JPEG and PNG default to
**lossless** tools. Lossless JPEG/PNG strip EXIF/ICC unless `--keep-meta`.

## Photos

```bash
filerepack repack photo.jpg
filerepack repack photo.jpg --keep-meta
filerepack bulk ./photos --include-ext jpg,png,webp,avif,jxl --progress
```

`--include-ext jpg` also matches aliases (`.jpeg`, `.thm`, …).

Lossy when you opt in:

```bash
filerepack bulk ./photos --include-ext jpg,png --lossy --progress
filerepack repack shot.png --png-quality medium
filerepack repack shot.jpg --jpeg-quality 75
```

`--ultra` adds a `zopflipng` pass for PNG.

## Video

WMV/AVI/ASF/3GP/MPEG-TS convert to MP4 unless `--no-convert-container`.
MKV/WebM/MOV/M4V keep their container.

```bash
filerepack bulk ./video --include-ext mp4,mkv,webm,mov --progress
filerepack bulk ./video --include-ext mp4,mkv,webm,mov --wmv-lossless
```

Needs `ffmpeg`.

## Audio and cover art

```bash
pip install 'filerepack[media]'
filerepack repack album.mp3
filerepack repack concert.flac
```

Cover art inside MP3/FLAC/M4A/Ogg/APE is optimized when `filerepack[media]` is
installed. MP3 uses `mp3packer` (not packaged; see [tools](/tools/)). `--ultra`
passes `mp3packer -z`.

## DICOM

Lossless JPEG-LS only (`gdcmconv` or `dcmcjpls`). `--lossy` does not apply.

```bash
filerepack bulk ./dicom --include-ext dcm --progress
```

See [Formats](/formats/) for the image/video/audio tables.
