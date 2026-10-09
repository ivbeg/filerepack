"""Whole-file PDF protection and lossless object/decoded-stream comparison."""

import base64
import hashlib
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List

from .commands import capture_bytes, check_command
from .tools import resolve_tool
from .raster_layout import _jpx_layout, _jpeg_layout
from .verification import MAX_DECODE_BYTES, VerificationUnavailable


@dataclass(frozen=True)
class PdfInspection:
    valid: bool
    protected: bool
    reason: str = ''
    linearized: bool = False

    @property
    def rewritable(self) -> bool:
        return self.valid and not self.protected


def _protected(value: object, depth: int = 0) -> bool:
    if depth > 200:
        raise VerificationUnavailable('PDF protection graph exceeds supported depth')
    if isinstance(value, dict):
        if any(key in value for key in ('/Encrypt', '/Perms', '/ByteRange')):
            return True
        if value.get('/Type') in ('/Sig', '/DocTimeStamp') or value.get('/FT') == '/Sig':
            return True
        if '/SigFlags' in value and value['/SigFlags'] != 0:
            return True
        return any(_protected(child, depth + 1) for child in value.values())
    if isinstance(value, list):
        return any(_protected(child, depth + 1) for child in value)
    return False


def _qpdf_json(path: str, *, streams: bool = False) -> Dict[str, Any]:
    tool = resolve_tool('qpdf')
    if tool is None:
        raise VerificationUnavailable('qpdf 11+ is required for PDF object comparison')
    if not check_command([tool, '--check', path]):
        raise ValueError('PDF structure/stream check failed, warned or timed out')
    command = [tool, '--json=2', '--decode-level=generalized',
               '--json-stream-data=' + ('inline' if streams else 'none'), path]
    output = capture_bytes(command)
    if output is None:
        raise VerificationUnavailable('PDF inspection failed or exceeded its time/output bound')
    value = json.loads(output, parse_float=Decimal)
    if (not isinstance(value, dict) or value.get('version') != 2
            or not isinstance(value.get('qpdf'), list) or len(value['qpdf']) != 2
            or not isinstance(value['qpdf'][1], dict)):
        raise ValueError('Unsupported PDF inspection representation')
    return value


def inspect_pdf(path: str) -> PdfInspection:
    """Unknown protection is never permission to run a rewriting path."""
    try:
        if resolve_tool('qpdf'):
            value = _qpdf_json(path)
            if not isinstance(value.get('encrypt', {}).get('encrypted'), bool):
                raise ValueError('Missing PDF encryption inspection')
            objects = value['qpdf'][1]
            protected = value['encrypt']['encrypted'] or _protected(objects)
            linearized = any('/Linearized' in item['value']
                             for item in objects.values() if isinstance(item, dict)
                             and isinstance(item.get('value'), dict))
        else:
            import pikepdf
            with pikepdf.open(path, attempt_recovery=False) as pdf:
                if pdf.check_pdf_syntax():
                    raise ValueError('PDF parser reported structural warnings')
                if len(pdf.objects) > 100000:
                    raise VerificationUnavailable('PDF object count exceeds supported bounds')
                protected = bool(pdf.is_encrypted) or _protected(
                    json.loads(pdf.trailer.to_json(dereference=True)),
                )
                for obj in pdf.objects:
                    if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                        protected = protected or _protected(
                            json.loads(obj.to_json(dereference=True)),
                        )
                linearized = bool(pdf.is_linearized)
        reason = ('PDF is signed, encrypted or has protection markers'
                  if protected else '')
        return PdfInspection(True, bool(protected), reason, linearized)
    except Exception as exc:
        reason = 'PDF protection inspection unavailable/failed: ' + str(exc)
        return PdfInspection(False, True, reason)


def _image_hash(data: bytes, attributes: Dict[str, Any]) -> str:
    try:
        from PIL import Image, ImageFile
    except ImportError as exc:
        raise VerificationUnavailable('Pillow is required for PDF image comparison') from exc
    if ImageFile.LOAD_TRUNCATED_IMAGES or attributes.get('/BitsPerComponent', 8) != 8:
        raise VerificationUnavailable('Unsupported PDF image sample depth/decoder policy')
    with Image.open(io.BytesIO(data)) as image:
        if image.format == 'JPEG2000':
            layout = _jpx_layout(data)
            components = len(layout[1])
        elif image.format == 'JPEG':
            layout = _jpeg_layout(data)
            components = layout[1]
        else:
            raise VerificationUnavailable('Unsupported PDF image encoding')
        if image.mode not in ('L', 'RGB', 'RGBA', 'CMYK') or len(image.getbands()) != components:
            raise VerificationUnavailable('Unsupported PDF image decoded component layout')
        if image.size != layout[0] or any(
            field in attributes and int(attributes[field]) != actual
            for field, actual in (('/Width', image.width), ('/Height', image.height))
        ):
            raise ValueError('PDF image dimensions disagree with encoded samples')
        from .format_support import current_budget
        budget = current_budget()
        if budget:
            budget.memory(image.width * image.height * 16)
            budget.consume(decoded=image.width * image.height * len(image.getbands()))
        if image.width * image.height > MAX_DECODE_BYTES // 8:
            raise VerificationUnavailable('PDF image exceeds supported decode bounds')
        image.load()
        # Keep modes (including CMYK) and all host stream attributes separately.
        digest = hashlib.sha256(repr((image.mode, layout, image.info.get('icc_profile'))).encode())
        digest.update(image.tobytes())
        return digest.hexdigest()


def pdf_fingerprint(path: str) -> object:
    value = _qpdf_json(path, streams=True)
    if value.get('encrypt', {}).get('encrypted') or _protected(value['qpdf'][1]):
        raise ValueError('Protected PDF cannot participate in lossless rewriting')
    objects = value['qpdf'][1]
    visited: Dict[str, int] = {}
    nodes: List[object] = []

    def normalize(item: Any, depth: int = 0) -> object:
        if depth > 200:
            raise VerificationUnavailable('PDF content graph exceeds supported depth')
        if isinstance(item, str) and re.fullmatch(r'\d+ \d+ R', item):
            if item not in visited:
                if len(visited) >= 100000:
                    raise VerificationUnavailable('PDF content object limit exceeded')
                visited[item] = len(nodes)
                nodes.append(None)
                representation = objects.get('obj:' + item)
                if representation is None:
                    raise ValueError('Unresolved PDF object reference')
                nodes[visited[item]] = normalize(representation, depth + 1)
            return ('reference', visited[item])
        if isinstance(item, dict):
            if 'stream' in item:
                stream = item['stream']
                data = base64.b64decode(stream['data'], validate=True)
                attributes = stream['dict']
                encoding = attributes.get('/Filter')
                if encoding in ('/DCTDecode', '/JPXDecode'):
                    checksum = _image_hash(data, attributes)
                elif encoding:
                    raise VerificationUnavailable('Unsupported PDF stream filter for comparison')
                else:
                    checksum = hashlib.sha256(data).hexdigest()
                return ('stream', normalize(attributes, depth + 1), checksum)
            return tuple((key, normalize(child, depth + 1))
                         for key, child in sorted(item.items()))
        if isinstance(item, list):
            return tuple(normalize(child, depth + 1) for child in item)
        return item

    trailer = objects['trailer']['value']
    # Xref layout, object IDs, linearization hints and volatile trailer IDs are
    # encoding artifacts. Preserve the reachable document and information graph.
    layout_keys = {'/Size', '/Prev', '/XRefStm', '/ID'}
    if trailer.get('/Type') == '/XRef':
        layout_keys.update(('/Type', '/W', '/Index', '/Filter', '/Length', '/DecodeParms'))
    document = normalize({key: child for key, child in trailer.items()
                          if key not in layout_keys})
    return document, tuple(nodes)
