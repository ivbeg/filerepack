# -*- coding: utf-8 -*-

"""Extract and recompress attached pictures in audio tags."""

import os
from typing import Any, Callable, List, Optional, Tuple

from .containers import pack_members, staging_dir


_MIME_EXT = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
}


def mutagen_available() -> bool:
    try:
        import mutagen  # noqa: F401
        return True
    except ImportError:
        return False


def _pack_picture(
    data: bytes, mime: str, options: Optional[dict],
) -> Optional[bytes]:
    ext = _MIME_EXT.get((mime or '').split(';', 1)[0].strip().lower())
    if ext is None or not data:
        return None
    with staging_dir() as tmp:
        path = os.path.join(tmp, 'cover' + ext)
        with open(path, 'wb') as fh:
            fh.write(data)
        result = pack_members({'cover': path}, options).get('cover')
        if result is None or not result.shrank:
            return None
        with open(result.path, 'rb') as fh:
            return fh.read()


def _mp3_covers(path: str, options: Optional[dict]) -> bool:
    from mutagen.id3 import ID3, APIC, ID3NoHeaderError

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return False
    changed = False
    for frame in tags.getall('APIC'):
        if not isinstance(frame, APIC):
            continue
        packed = _pack_picture(bytes(frame.data), str(frame.mime), options)
        if packed is None:
            continue
        frame.data = packed
        changed = True
    if changed:
        tags.save(path)
    return changed


def _flac_covers(path: str, options: Optional[dict]) -> bool:
    from mutagen.flac import FLAC

    audio = FLAC(path)
    pictures = list(audio.pictures)
    if not pictures:
        return False
    changed = False
    rebuilt = []
    for pic in pictures:
        packed = _pack_picture(bytes(pic.data), str(pic.mime), options)
        if packed is not None:
            pic.data = packed
            changed = True
        rebuilt.append(pic)
    if not changed:
        return False
    audio.clear_pictures()
    for pic in rebuilt:
        audio.add_picture(pic)
    audio.save()
    return True


def _mp4_covers(path: str, options: Optional[dict]) -> bool:
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(path)
    covers = list(audio.get('covr') or [])
    if not covers:
        return False
    changed = False
    rebuilt: List[Any] = []
    for cover in covers:
        fmt = getattr(cover, 'imageformat', MP4Cover.FORMAT_JPEG)
        mime = 'image/png' if fmt == MP4Cover.FORMAT_PNG else 'image/jpeg'
        packed = _pack_picture(bytes(cover), mime, options)
        if packed is None:
            rebuilt.append(cover)
            continue
        rebuilt.append(MP4Cover(packed, imageformat=fmt))
        changed = True
    if not changed:
        return False
    audio['covr'] = rebuilt
    audio.save()
    return True


def _ogg_covers(path: str, options: Optional[dict]) -> bool:
    import base64
    from mutagen.flac import Picture
    from mutagen.oggvorbis import OggVorbis
    try:
        from mutagen.oggopus import OggOpus
    except ImportError:
        OggOpus = None  # type: ignore

    audio = None
    for cls in (OggVorbis, OggOpus):
        if cls is None:
            continue
        try:
            audio = cls(path)
            break
        except Exception:
            continue
    if audio is None:
        return False
    blocks = audio.get('metadata_block_picture') or []
    if not blocks:
        return False
    changed = False
    rebuilt = []
    for item in blocks:
        try:
            pic = Picture(base64.b64decode(item))
        except Exception:
            rebuilt.append(item)
            continue
        packed = _pack_picture(bytes(pic.data), str(pic.mime), options)
        if packed is None:
            rebuilt.append(item)
            continue
        pic.data = packed
        rebuilt.append(base64.b64encode(pic.write()).decode('ascii'))
        changed = True
    if not changed:
        return False
    audio['metadata_block_picture'] = rebuilt
    audio.save()
    return True


def _ape_covers(path: str, options: Optional[dict]) -> bool:
    from mutagen.apev2 import APEv2, APENoHeaderError

    try:
        tags = APEv2(path)
    except APENoHeaderError:
        return False
    changed = False
    for key in list(tags.keys()):
        if not key.lower().startswith('cover art'):
            continue
        value = tags[key].value
        if not isinstance(value, (bytes, bytearray)):
            continue
        raw = bytes(value)
        split_at = raw.find(b'\x00')
        if split_at < 0:
            continue
        name, blob = raw[:split_at], raw[split_at + 1:]
        mime = 'image/png' if blob[:8] == b'\x89PNG\r\n\x1a\n' else 'image/jpeg'
        packed = _pack_picture(blob, mime, options)
        if packed is None:
            continue
        tags[key] = name + b'\x00' + packed
        changed = True
    if changed:
        tags.save(path)
    return changed


_HANDLERS: Tuple[Callable[[str, Optional[dict]], bool], ...] = (
    _mp3_covers, _flac_covers, _mp4_covers, _ogg_covers, _ape_covers,
)


def optimize_embedded_covers(
    filepath: str, options: Optional[dict] = None,
) -> bool:
    """Rewrite attached pictures in *filepath* in place. Return True if changed."""
    if not mutagen_available():
        return False
    if options and not options.get('pack_images', True):
        return False
    for handler in _HANDLERS:
        try:
            if handler(filepath, options):
                return True
        except Exception:
            continue
    return False
