# -*- coding: utf-8 -*-

"""JSON/XML minification and data-URI image extraction."""

import base64
import json
import os
import re
from typing import Any, Optional, cast
from xml.etree import ElementTree as ET

from .containers import pack_members, staging_dir
from .models import PackResult


_XML_GAP = re.compile(rb'>\s*[\r\n][ \t\r\n]*<')
_DATA_URI = re.compile(
    r'data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=\s]+)',
    re.IGNORECASE,
)
_IMAGE_EXT = {
    'png': '.png', 'jpeg': '.jpg', 'jpg': '.jpg',
    'gif': '.gif', 'webp': '.webp',
}


def _r() -> Any:
    from . import repack as r
    return r


def _et() -> Any:
    try:
        import defusedxml.ElementTree as det  # type: ignore
        return det
    except ImportError:
        return ET


def pack_json(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    r = _r()
    try:
        with open(filepath, 'rb') as fh:
            raw = fh.read()
        obj = json.loads(raw.decode('utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None
    compact = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
    payload = compact.encode('utf-8')
    insize = len(raw)
    out_temp = r._make_temp('.json')
    try:
        with open(out_temp, 'wb') as fh:
            fh.write(payload)
        return cast(
            Optional[PackResult],
            r._commit_output(
                out_temp, filepath, insize, verify='json',
                **r._commit_kwargs(**commit),
            ),
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None


def minify_xml_bytes(data: bytes) -> Optional[bytes]:
    """Drop pretty-print gaps between tags; keep text-node bytes intact."""
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        return None
    parser = _et()
    try:
        parser.fromstring(text)
    except (ET.ParseError, SyntaxError, ValueError):
        return None
    compacted = _XML_GAP.sub(b'><', text.encode('utf-8'))
    return compacted


def _pack_image_bytes(
    data: bytes, ext: str, options: Optional[dict],
) -> Optional[bytes]:
    with staging_dir() as tmp:
        path = os.path.join(tmp, 'embed' + ext)
        with open(path, 'wb') as fh:
            fh.write(data)
        result = pack_members({'img': path}, options).get('img')
        if result is None or not result.shrank:
            return None
        with open(result.path, 'rb') as fh:
            return fh.read()


def rewrite_data_uris(text: str, options: Optional[dict] = None) -> str:
    """Replace image data URIs with packed payloads when they shrink."""

    def _repl(match: re.Match[str]) -> str:
        original = str(match.group(0))
        subtype = match.group(1).lower()
        ext = _IMAGE_EXT.get(subtype)
        if ext is None:
            return original
        try:
            raw = base64.b64decode(match.group(2), validate=False)
        except (ValueError, TypeError):
            return original
        packed = _pack_image_bytes(raw, ext, options)
        if packed is None or len(packed) >= len(raw):
            return original
        mime = 'jpeg' if subtype in ('jpg', 'jpeg') else subtype
        b64 = base64.b64encode(packed).decode('ascii')
        return f'data:image/{mime};base64,{b64}'

    return _DATA_URI.sub(_repl, text)


def pack_xml(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    r = _r()
    try:
        with open(filepath, 'rb') as fh:
            raw = fh.read()
    except OSError:
        return None
    compacted = minify_xml_bytes(raw)
    if compacted is None:
        return None
    try:
        text = compacted.decode('utf-8')
    except UnicodeError:
        return None
    options = {
        'debug': debug, 'quiet': quiet, 'pack_images': True,
        'lossy': bool(commit.get('lossy', False)),
        'keep_meta': bool(commit.get('keep_meta', False)),
        'jpeg_quality': commit.get('jpeg_quality'),
        'png_quality': commit.get('png_quality'),
        'ultra': bool(commit.get('ultra', False)),
    }
    rewritten = rewrite_data_uris(text, options)
    payload = rewritten.encode('utf-8')
    insize = len(raw)
    out_temp = r._make_temp('.xml')
    try:
        with open(out_temp, 'wb') as fh:
            fh.write(payload)
        return cast(
            Optional[PackResult],
            r._commit_output(
                out_temp, filepath, insize, verify='xml',
                **r._commit_kwargs(**commit),
            ),
        )
    except Exception:
        r._remove_quietly(out_temp)
        return None
