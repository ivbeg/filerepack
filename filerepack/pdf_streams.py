# -*- coding: utf-8 -*-

"""Lossless PDF image-stream walking via pikepdf."""

import os
from typing import Any, Optional

from .containers import pack_members, staging_dir


def pikepdf_available() -> bool:
    try:
        import pikepdf  # noqa: F401
        return True
    except ImportError:
        return False


def _pdf_is_locked(pdf: Any) -> bool:
    if getattr(pdf, 'is_encrypted', False):
        return True
    root = pdf.Root
    if '/Encrypt' in pdf.trailer:
        return True
    if '/Perms' in root:
        return True
    form = root.get('/AcroForm')
    if form is None:
        return False
    flags = form.get('/SigFlags')
    try:
        if flags is not None and int(flags) & 1:
            return True
    except (TypeError, ValueError):
        return True
    return False


def _filter_name(obj: Any) -> str:
    filt = obj.get('/Filter')
    if filt is None:
        return ''
    try:
        from pikepdf import Array, Name
    except ImportError:
        return str(filt)
    if isinstance(filt, Array):
        if len(filt) != 1:
            return ''
        filt = filt[0]
    if isinstance(filt, Name):
        return str(filt)
    return str(filt)


def _pack_stream_bytes(
    data: bytes, ext: str, options: Optional[dict],
) -> Optional[bytes]:
    with staging_dir() as tmp:
        path = os.path.join(tmp, 'stream' + ext)
        with open(path, 'wb') as fh:
            fh.write(data)
        result = pack_members({'img': path}, options).get('img')
        if result is None or not result.shrank:
            return None
        with open(result.path, 'rb') as fh:
            return fh.read()


def rebuild_pdf_images(
    src: str, dest: str, options: Optional[dict] = None,
) -> bool:
    """Copy *src* to *dest* with packed image streams. False if nothing changed."""
    try:
        import pikepdf
        from pikepdf import Name
    except ImportError:
        return False
    try:
        with pikepdf.open(src) as pdf:
            if _pdf_is_locked(pdf):
                return False
            changed = False
            for page in pdf.pages:
                try:
                    images = page.images
                except Exception:
                    continue
                for _name, obj in images.items():
                    filt = _filter_name(obj)
                    if filt == '/DCTDecode':
                        ext, filt_name = '.jpg', Name.DCTDecode
                    elif filt == '/JPXDecode':
                        ext, filt_name = '.jp2', Name.JPXDecode
                    else:
                        continue
                    try:
                        raw = obj.read_raw_bytes()
                    except Exception:
                        continue
                    packed = _pack_stream_bytes(raw, ext, options)
                    if packed is None:
                        continue
                    try:
                        obj.write(packed, filter=filt_name)
                        changed = True
                    except Exception:
                        continue
            if not changed:
                return False
            pdf.save(dest)
            return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception:
        return False
