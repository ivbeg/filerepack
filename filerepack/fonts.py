"""Bounded WOFF table/metadata preservation inside the isolated format worker."""

import hashlib
import os
import struct
from typing import Any, Dict, Optional

from .format_support import Budget, UnsupportedFormat, read_small


def _header(path: str, budget: Budget) -> bytes:
    data = read_small(path, budget)
    if len(data) < 44 or data[:4] not in (b'wOFF', b'wOF2'):
        raise ValueError('Not a complete WOFF/WOFF2 font')
    length, count, reserved, decoded = struct.unpack_from('>IHHI', data, 8)
    if length != len(data) or not count or reserved:
        raise ValueError('Invalid WOFF length/table count/reserved field')
    budget.memory(decoded * 4)
    budget.consume(nodes=count)
    return data


def _layout(data: bytes, reader: Any) -> None:
    ranges = []
    if data[:4] == b'wOFF':
        ranges.append((0, 44 + reader.numTables * 20))
        ranges.extend((entry.offset, entry.offset + entry.length)
                      for entry in reader.tables.values())
    else:
        # The native parser has read exactly the directory and compressed body.
        from fontTools.ttLib.woff2 import WOFF2DirectoryEntry
        import io
        source = io.BytesIO(data)
        source.seek(48)
        for _ in range(reader.numTables):
            WOFF2DirectoryEntry().fromFile(source)
        ranges.append((0, source.tell() + reader.totalCompressedSize))
    for start, size in ((reader.metaOffset, reader.metaLength),
                        (reader.privOffset, reader.privLength)):
        if bool(start) != bool(size):
            raise ValueError('Invalid optional WOFF block range')
        if size:
            ranges.append((start, start + size))
    end = 0
    for start, stop in sorted(ranges):
        if start < end or stop > len(data) or stop <= start:
            raise ValueError('Overlapping or out-of-bounds WOFF block')
        if start - end > 3 or any(data[end:start]):
            raise UnsupportedFormat('Unclassified WOFF data outside declared blocks')
        end = stop
    if len(data) - end > 3 or any(data[end:]):
        raise UnsupportedFormat('Unclassified WOFF trailer')


def fingerprint(path: str, budget: Budget) -> str:
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.sfnt import calcChecksum
    data = _header(path, budget)
    version = 20 if data[:4] == b'wOFF' else 24
    checksum = hashlib.sha256(data[:8] + data[version:version + 4])
    with TTFont(path, lazy=False, checkChecksums=2, recalcTimestamp=False,
                recalcBBoxes=False) as font:
        _layout(data, font.reader)
        if 'DSIG' in font:
            raise UnsupportedFormat('Signed WOFF fonts are protected')
        for tag, entry in font.reader.tables.items():
            raw = font.reader[tag]
            font[tag]  # Require complete native table decoding.
            budget.consume(decoded=len(raw))
            if tag == 'head':
                raw = raw[:8] + b'\0' * 4 + raw[12:]
            if font.flavor == 'woff' and calcChecksum(raw) != entry.checkSum:
                raise ValueError('Invalid WOFF table checksum')
            checksum.update(str(tag).encode() + struct.pack('>Q', len(raw)) + raw)
        for raw in (font.flavorData.metaData or b'', font.flavorData.privData or b''):
            budget.consume(decoded=len(raw))
            checksum.update(struct.pack('>Q', len(raw)) + raw)
    return checksum.hexdigest()


def operate(kind: str, action: str, source: str, candidate: Optional[str],
            options: Dict[str, Any], budget: Budget) -> Dict[str, Any]:
    del kind, options
    original = fingerprint(source, budget)
    if action == 'inspect':
        return {'details': {'strategy': 'woff-preserving', 'table_metadata_verified': True}}
    assert candidate is not None
    if action == 'compare':
        return {'equal': original == fingerprint(candidate, budget)}
    from fontTools.ttLib import TTFont
    with TTFont(source, recalcTimestamp=False, recalcBBoxes=False) as font:
        font.save(candidate, reorderTables=False)
    budget.consume(written=os.path.getsize(candidate))
    if original != fingerprint(candidate, budget):
        raise UnsupportedFormat('WOFF rewrite changes decoded tables or metadata')
    return {'changed': os.path.getsize(candidate) < os.path.getsize(source),
            'details': {'strategy': 'woff-preserving', 'table_metadata_verified': True}}
