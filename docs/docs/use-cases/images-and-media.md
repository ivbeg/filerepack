---
title: "Images and media"
description: "Lossless and opt-in lossy images, video, audio, and cover art"
---
# Images and media

`--no-images` skips this category (including cover art). JPEG and PNG default to
**lossless** tools and retain required orientation and color-profile information.
`--keep-meta` also requests incidental metadata retention. The current JPEG/PNG
adapters conservatively retain all metadata when presentation fields are present.
Install `filerepack[validation]` for the required raster decoder.

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

Video defaults to stream-copy remuxing. Use `--video-mode lossless` (or the
compatibility alias `--wmv-lossless`) for lossless re-encoding. Lossy encoding
requires `--video-mode lossy --lossy`. Needs both `ffmpeg` and `ffprobe`; stream
inventories and content checks must pass before publication.

## Audio and cover art

```bash
pip install 'filerepack[media]'
filerepack repack album.mp3
filerepack repack concert.flac
```

Cover art inside MP3/FLAC/M4A/Ogg/APE is optimized when `filerepack[media]` is
installed. MP3 uses `mp3packer` (not packaged; see [tools](/tools/)). `--ultra`
passes `mp3packer -z`.

Ogg Vorbis uses [OptiVorbis](https://github.com/OptiVorbis/OptiVorbis), whose
official CLI optimizes Vorbis audio. The registered Opus route uses the same
adapter but has no qualified OptiVorbis Opus codec optimization; cover-art
changes may still produce savings when the media extra is installed.

## DICOM

Lossless JPEG-LS only (`gdcmconv` or `dcmcjpls`). `--lossy` does not apply.

```bash
pip install 'filerepack[dicom]'
filerepack bulk ./dicom --include-ext dcm --progress
```

See [Formats](/formats/) for the image/video/audio tables.
