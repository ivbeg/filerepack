"""Bounded Telegram animation recompression preserving exact Lottie JSON bytes."""

import gzip
import json
import logging
import zlib
from typing import Any, Optional

from . import candidates as tx
from .markup import minify_json_bytes
from .models import PackResult
from .transactions import guard_packer

MAX_TGS_BYTES = 4 * 1024 * 1024
MAX_ZOPFLI_BYTES = 1024 * 1024


def decode_tgs(data: bytes) -> bytes:
    if len(data) > MAX_TGS_BYTES:
        raise ValueError('TGS exceeds supported input bounds')
    decoder = zlib.decompressobj(31)
    raw = decoder.decompress(data, MAX_TGS_BYTES + 1)
    if (len(raw) > MAX_TGS_BYTES or not decoder.eof or decoder.unused_data
            or decoder.unconsumed_tail or minify_json_bytes(raw) is None):
        raise ValueError('Invalid, oversized or multi-member TGS gzip/JSON')
    document = json.loads(raw)
    if (not isinstance(document, dict) or document.get('tgs') != 1
            or not isinstance(document.get('v'), str)
            or not isinstance(document.get('layers'), list)):
        raise ValueError('Unsupported TGS Lottie document')
    return raw


def compress_tgs(raw: bytes) -> bytes:
    fallback = gzip.compress(raw, compresslevel=9, mtime=0)
    if len(raw) <= MAX_ZOPFLI_BYTES:
        try:
            from zopfli.gzip import compress
        except ImportError:
            return fallback
        optimized = bytes(compress(raw, numiterations=5))
        return optimized if len(optimized) < len(fallback) else fallback
    return fallback


@guard_packer
def pack_tgs(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    temporary = tx.make_temp('.tgs')
    try:
        with open(filepath, 'rb') as source:
            original = source.read(MAX_TGS_BYTES + 1)
        raw = decode_tgs(original)
        with open(temporary, 'wb') as target:
            target.write(compress_tgs(raw))
        return tx.commit_output(
            temporary, filepath, len(original), verify='tgs', lossless=True,
            **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError, zlib.error) as error:
        logging.debug('TGS optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(temporary)
