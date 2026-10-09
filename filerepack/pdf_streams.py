# -*- coding: utf-8 -*-

"""Lossless PDF image-stream walking via pikepdf."""

import os
import logging
import json
import zlib
from typing import Any, Optional, Iterator, Dict

from .containers import pack_members, staging_dir
from .pdf_verify import inspect_pdf, pdf_fingerprint, _image_hash, _protected
from .format_support import Budget, FormatLimits, current_budget, inflate, FormatLimit
from .outcomes import record


def pikepdf_available() -> bool:
    try:
        import pikepdf  # noqa: F401
        return True
    except ImportError:
        return False


def _pdf_is_locked(pdf: Any) -> bool:
    if getattr(pdf, 'is_encrypted', False):
        return True
    try:
        for obj in [pdf.trailer, pdf.Root, *getattr(pdf, 'objects', ())]:
            if hasattr(obj, 'to_json'):
                value = json.loads(obj.to_json(dereference=True))
            else:
                value = obj
            if _protected(value):
                return True
        return False
    except Exception:
        # Failure to inspect the opened graph cannot authorize stream mutation.
        return True


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


def _images(resources: Any, visited: set, budget: Budget, depth: int = 0,
            base: int = 0) -> Iterator[Any]:
    budget.depth(base + depth + 1)
    if depth > 16:
        raise FormatLimit('PDF resource graph depth exceeds 16')
    if resources is None:
        return
    for obj in resources.get('/XObject', {}).values():
        budget.consume(nodes=1)
        identity = tuple(obj.objgen) if tuple(obj.objgen) != (0, 0) else ('direct', id(obj))
        if identity in visited:
            continue
        visited.add(identity)
        subtype = obj.get('/Subtype')
        if subtype == '/Image':
            yield obj
        elif subtype == '/Form':
            yield from _images(obj.get('/Resources'), visited, budget, depth + 1, base)


def _flate_parameters(obj: Any) -> int:
    width, height = int(obj['/Width']), int(obj['/Height'])
    bits = int(obj.get('/BitsPerComponent', 1 if obj.get('/ImageMask', False) else 0))
    color = obj.get('/ColorSpace')
    colors = {'/DeviceGray': 1, '/DeviceRGB': 3, '/DeviceCMYK': 4}
    components = colors.get(str(color), 0)
    if obj.get('/ImageMask', False):
        components = 1
    elif not components and color is not None and len(color) >= 2:
        if str(color[0]) == '/ICCBased':
            components = int(color[1].get('/N', 0))
        elif str(color[0]) == '/Indexed':
            components = 1
    parameters = obj.get('/DecodeParms') or {}
    predictor = int(parameters.get('/Predictor', 1))
    if (width < 1 or height < 1 or bits not in (1, 2, 4, 8, 16) or
            components not in (1, 3, 4) or predictor not in (1, 2, 10, 11, 12, 13, 14, 15)):
        raise ValueError('unsupported Flate image sample/predictor profile')
    if predictor != 1 and (
        int(parameters.get('/Colors', 1)) != components or
        int(parameters.get('/Columns', 1)) != width or
        int(parameters.get('/BitsPerComponent', 8)) != bits
    ):
        raise ValueError('Flate predictor parameters disagree with image samples')
    return height * (((width * bits * components + 7) // 8) + 1)


def _rebuild_image(obj: Any, options: Optional[dict], budget: Budget) -> int:
    from pikepdf import Name
    filt = _filter_name(obj)
    budget.memory(int(obj.get('/Length', 0)) * 8)
    raw = obj.read_raw_bytes()
    if filt == '/FlateDecode':
        maximum = _flate_parameters(obj)
        budget.memory(maximum * 4 + len(raw))
        decoded = inflate(raw, budget, maximum=maximum)
        packed = zlib.compress(decoded, 9)
        if zlib.decompress(packed) != decoded:
            raise ValueError('Flate image round-trip failed')
        budget.consume(decoded=len(decoded))
    elif filt in ('/DCTDecode', '/JPXDecode'):
        alternative = _pack_stream_bytes(raw, '.jpg' if filt == '/DCTDecode' else '.jp2', options)
        if alternative is None:
            return 0
        packed = alternative
        attributes = {key: obj.get(key) for key in ('/Width', '/Height')}
        attributes['/BitsPerComponent'] = obj.get('/BitsPerComponent', 8)
        if _image_hash(raw, attributes) != _image_hash(packed, attributes):
            raise ValueError('decoded PDF image pixels changed')
    else:
        raise ValueError('unsupported PDF image filter chain')
    if len(packed) >= len(raw):
        return 0
    obj.write(packed, filter=Name(filt), decode_parms=obj.get('/DecodeParms'))
    budget.consume(written=len(packed))
    return len(raw) - len(packed)


def rebuild_pdf_images(
    src: str, dest: str, options: Optional[dict] = None,
) -> bool:
    """Copy *src* to *dest* with packed image streams. False if nothing changed."""
    try:
        import pikepdf
    except ImportError:
        return False
    inspection = inspect_pdf(src)
    if options is not None and not options.get('pack_images', True):
        return False
    if not inspection.rewritable:
        logging.warning('PDF stream walking skipped: %s', inspection.reason)
        return False
    try:
        expected = pdf_fingerprint(src)
        with pikepdf.open(src, attempt_recovery=False) as pdf:
            if _pdf_is_locked(pdf):
                return False
            budget = current_budget() or Budget(FormatLimits())
            visited: set = set()
            work: Dict[str, int] = {'images': 0, 'changed': 0,
                                    'stream_bytes_saved': 0, 'skipped': 0}
            for page in pdf.pages:
                for obj in _images(page.obj.get('/Resources'), visited, budget,
                                   base=(options or {}).get('_optimization_depth', 0)):
                    work['images'] += 1
                    try:
                        saved = _rebuild_image(obj, options, budget)
                        work['changed'] += int(saved > 0)
                        work['stream_bytes_saved'] += saved
                    except FormatLimit:
                        raise
                    except (ValueError, TypeError, KeyError) as exc:
                        work['skipped'] += 1
                        record('skipped', 'pdf_image_unsupported', str(exc))
            if options is not None:
                options['_pdf_work'] = work
            if not work['changed']:
                return False
            pdf.save(dest)
            return (os.path.exists(dest) and inspect_pdf(dest).rewritable
                    and pdf_fingerprint(dest) == expected)
    except FormatLimit as exc:
        record('skipped', 'resource_limit', str(exc))
        return False
    except Exception:
        return False


def operate(kind: str, action: str, source: str, candidate: Optional[str],
            options: dict, budget: Budget) -> dict:
    if action == 'rewrite':
        assert candidate is not None
        changed = rebuild_pdf_images(source, candidate, options)
        return {'changed': changed, 'details': options.get('_pdf_work', {})}
    if action == 'compare':
        assert candidate is not None
        return {'equal': pdf_fingerprint(source) == pdf_fingerprint(candidate)}
    return {'details': {'rewritable': inspect_pdf(source).rewritable}}
