"""Passive, bounded recompression of archived Unified Log LZ4 chunksets."""

import hashlib
import os
import struct
from typing import Any, Dict, List, Optional, Tuple

from .format_support import Budget, UnsupportedFormat, pack_format, read_small, write_bytes
from .models import PackResult

ACTIVE_STORES = ('/private/var/db/diagnostics', '/var/db/diagnostics')
_HEADER = struct.Struct('<IIQ')


def active_store(path: str) -> bool:
    path = os.path.realpath(os.path.abspath(path))
    return any(os.path.commonpath((path, os.path.realpath(root))) == os.path.realpath(root)
               for root in ACTIVE_STORES)


def destination_refusal(source: str, output: str, backup: Optional[str]) -> Optional[str]:
    if active_store(output) or (backup and active_store(backup)):
        return 'Writing into an active Unified Log store is unsupported'
    return None


def _take(data: bytes, start: int, size: int) -> bytes:
    if size < 0 or start < 0 or start + size > len(data):
        raise ValueError('truncated tracev3 block or chunk')
    return data[start:start + size]


def _blocks(data: bytes, budget: Budget, level: Optional[int]) -> Tuple[bytes, List[Any], int]:
    import lz4.block

    offset, changed, dictionary = 0, 0, b''
    output = bytearray()
    identities: List[Any] = []
    while offset < len(data):
        budget.consume(nodes=1)
        marker = _take(data, offset, 4)
        if marker == b'bv4$':
            if offset + 4 != len(data):
                raise UnsupportedFormat('bytes after tracev3 LZ4 end marker')
            output.extend(marker)
            return bytes(output), identities, changed
        if marker not in (b'bv41', b'bv4-'):
            raise UnsupportedFormat('unknown tracev3 LZ4 block marker')
        raw_size = struct.unpack('<I', _take(data, offset + 4, 4))[0]
        if not raw_size:
            raise UnsupportedFormat('empty tracev3 LZ4 block')
        budget.memory(raw_size * 6 + len(data) * 2)
        if marker == b'bv41':
            size = struct.unpack('<I', _take(data, offset + 8, 4))[0]
            encoded = _take(data, offset + 12, size)
            raw = lz4.block.decompress(encoded, uncompressed_size=raw_size, dict=dictionary)
            end = offset + 12 + size
        else:
            raw = _take(data, offset + 8, raw_size)
            end = offset + 8 + raw_size
        if len(raw) != raw_size:
            raise ValueError('tracev3 LZ4 decoded length mismatch')
        budget.consume(decoded=raw_size)
        original = data[offset:end]
        selected = original
        if level is not None:
            encoded = lz4.block.compress(raw, mode='high_compression', compression=level,
                                         store_size=False, dict=dictionary)
            replacement = b'bv41' + struct.pack('<II', raw_size, len(encoded)) + encoded
            if len(replacement) < len(original):
                check = lz4.block.decompress(encoded, uncompressed_size=raw_size, dict=dictionary)
                budget.consume(decoded=len(check))
                if check != raw:
                    raise ValueError('tracev3 LZ4 round-trip mismatch')
                selected, changed = replacement, changed + 1
        output.extend(selected)
        identities.append((raw_size, hashlib.sha256(raw).hexdigest()))
        dictionary = (dictionary + raw)[-65536:]
        offset = end
    raise ValueError('missing tracev3 LZ4 end marker')


def _parse(data: bytes, budget: Budget,
           level: Optional[int] = None) -> Tuple[bytes, List[Any], int]:
    if len(data) < 224 or _HEADER.unpack_from(data) != (0x1000, 0x11, 208):
        raise UnsupportedFormat('unsupported tracev3 header profile')
    output = bytearray()
    identities: List[Any] = []
    offset, changed, catalog_seen = 0, 0, False
    while offset < len(data):
        budget.consume(nodes=1)
        tag, subtag, size = _HEADER.unpack(_take(data, offset, 16))
        body = _take(data, offset + 16, size)
        end = offset + 16 + size
        aligned = (end + 7) & ~7
        padding = _take(data, end, aligned - end)
        original = data[offset:aligned]
        if tag == 0x600b:
            catalog_seen = True
        if tag == 0x600d:
            if not catalog_seen or any(padding):
                raise UnsupportedFormat('unsupported tracev3 chunkset layout or padding')
            rewritten, blocks, count = _blocks(body, budget, level)
            identities.append((tag, subtag, blocks))
            if len(rewritten) < len(body):
                output.extend(_HEADER.pack(tag, subtag, len(rewritten)) + rewritten)
                output.extend(bytes((-len(output)) % 8))
                changed += count
            else:
                output.extend(original)
        else:
            # Unknown non-target chunks are opaque and retained byte for byte.
            identities.append(hashlib.sha256(original).hexdigest())
            output.extend(original)
        offset = aligned
    return bytes(output), identities, changed


def operate(kind: str, action: str, source: str, candidate: Optional[str],
            options: Dict[str, Any], budget: Budget) -> Dict[str, Any]:
    data = read_small(source, budget)
    level = min(12, int(options.get('compression_level', 9))) if action == 'rewrite' else None
    output, identity, changed = _parse(data, budget, level)
    details = {'format': 'tracev3', 'profile': 'chunksets-lz4-v1', 'blocks_recompressed': changed}
    if action == 'compare':
        assert candidate is not None
        return {'equal': identity == _parse(read_small(candidate, budget), budget)[1]}
    if action == 'rewrite' and changed:
        assert candidate is not None
        write_bytes(candidate, output, budget)
    return {'changed': bool(changed), 'details': details}


def pack_tracev3(filepath: str, **options: Any) -> PackResult:
    return pack_format('tracev3', filepath, options)
